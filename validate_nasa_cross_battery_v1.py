"""Run leave-one-battery-out next-discharge SOH validation on NASA cells.

All outputs are new files under data/processed/nasa_cross_battery_v1.
The script fails before doing work if any output already exists.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parent
BATTERIES = ("B0005", "B0006", "B0007", "B0018")
FEATURES = [
    "cycle_number",
    "ambient_temperature_C",
    "soh_percent",
    "previous_soh_percent",
    "capacity_change_from_previous_Ah",
]
OUTPUT_DIR = ROOT / "data" / "processed" / "nasa_cross_battery_v1"
OUTPUT_FILES = (
    "nasa_cross_battery_v1_predictions.csv",
    "nasa_cross_battery_v1_fold_metrics.csv",
    "nasa_cross_battery_v1_summary.json",
)


def load_battery(battery_id: str) -> pd.DataFrame:
    source = ROOT / "data" / "nasa" / f"{battery_id}.mat"
    if not source.is_file():
        raise FileNotFoundError(f"Required NASA source is missing: {source}")

    mat = loadmat(source, simplify_cells=True)
    events = np.atleast_1d(mat[battery_id]["cycle"])
    rows: list[dict[str, float | int | str]] = []
    for event_number, event in enumerate(events, start=1):
        if str(event.get("type", "")).strip().lower() != "discharge":
            continue
        data = event.get("data") or {}
        try:
            capacity = float(np.asarray(data["Capacity"]).reshape(-1)[0])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if not np.isfinite(capacity) or capacity <= 0:
            continue
        temperature = float(event.get("ambient_temperature", np.nan))
        rows.append({
            "battery_id": battery_id,
            "event_number": event_number,
            "discharge_index": len(rows) + 1,
            "ambient_temperature_C": temperature,
            "discharge_capacity_Ah": capacity,
        })

    frame = pd.DataFrame(rows)
    if len(frame) < 3:
        raise ValueError(f"{battery_id} has fewer than three valid discharges")
    frame["soh_percent"] = frame["discharge_capacity_Ah"] / frame[
        "discharge_capacity_Ah"
    ].iloc[0] * 100.0
    frame["previous_soh_percent"] = frame["soh_percent"].shift(1)
    frame["capacity_change_from_previous_Ah"] = frame[
        "discharge_capacity_Ah"
    ].diff()
    frame["cycle_number"] = frame["discharge_index"]
    frame["target_cycle_number"] = frame["discharge_index"].shift(-1)
    frame["target_soh_percent"] = frame["soh_percent"].shift(-1)
    frame["target_capacity_Ah"] = frame["discharge_capacity_Ah"].shift(-1)
    return frame.dropna(subset=FEATURES + ["target_soh_percent"]).reset_index(drop=True)


def metric_record(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae_soh_percentage_points": float(mean_absolute_error(y_true, y_pred)),
        "rmse_soh_percentage_points": float(
            np.sqrt(mean_squared_error(y_true, y_pred))
        ),
        "r2": float(r2_score(y_true, y_pred)),
    }


def main() -> None:
    conflicts = [str(OUTPUT_DIR / name) for name in OUTPUT_FILES if (OUTPUT_DIR / name).exists()]
    if OUTPUT_DIR.exists() or conflicts:
        raise FileExistsError(
            "Refusing to overwrite any existing cross-battery output path: "
            + str(OUTPUT_DIR)
        )

    batteries = {battery: load_battery(battery) for battery in BATTERIES}
    all_predictions: list[pd.DataFrame] = []
    fold_metrics: list[dict[str, object]] = []

    for held_out in BATTERIES:
        train = pd.concat(
            [batteries[name] for name in BATTERIES if name != held_out],
            ignore_index=True,
        )
        test = batteries[held_out].copy()
        if not np.isfinite(train[FEATURES + ["target_soh_percent"]].to_numpy()).all():
            raise ValueError("Non-finite training data detected")
        if not np.isfinite(test[FEATURES + ["target_soh_percent"]].to_numpy()).all():
            raise ValueError("Non-finite holdout data detected")

        models = {
            "persistence": None,
            "linear_regression": LinearRegression(),
            "xgboost": XGBRegressor(
                objective="reg:squarederror",
                n_estimators=200,
                max_depth=3,
                learning_rate=0.03,
                subsample=0.9,
                colsample_bytree=1.0,
                reg_lambda=1.0,
                random_state=42,
                n_jobs=1,
            ),
        }
        actual = test["target_soh_percent"].to_numpy(dtype=float)
        for model_name, model in models.items():
            if model is None:
                predicted = test["soh_percent"].to_numpy(dtype=float)
            else:
                model.fit(train[FEATURES], train["target_soh_percent"])
                predicted = model.predict(test[FEATURES])
            record = test[[
                "battery_id", "discharge_index", "target_cycle_number",
                "discharge_capacity_Ah", "soh_percent", "target_capacity_Ah",
                "target_soh_percent",
            ]].copy()
            record["held_out_battery"] = held_out
            record["model"] = model_name
            record["predicted_soh_percent"] = predicted
            record["absolute_error_percentage_points"] = np.abs(actual - predicted)
            all_predictions.append(record)
            fold_metrics.append({
                "held_out_battery": held_out,
                "training_batteries": ",".join(name for name in BATTERIES if name != held_out),
                "model": model_name,
                "training_rows": int(len(train)),
                "testing_rows": int(len(test)),
                **metric_record(actual, predicted),
            })

    predictions = pd.concat(all_predictions, ignore_index=True)
    metrics = pd.DataFrame(fold_metrics)
    pooled = {}
    for model_name, group in predictions.groupby("model", sort=True):
        pooled[model_name] = metric_record(
            group["target_soh_percent"].to_numpy(dtype=float),
            group["predicted_soh_percent"].to_numpy(dtype=float),
        )

    battery_summary = {}
    for battery_id, frame in batteries.items():
        first_capacity = float(
            frame["discharge_capacity_Ah"].iloc[0]
            / (frame["soh_percent"].iloc[0] / 100.0)
        )
        battery_summary[battery_id] = {
            # Two edge rows are excluded from supervised examples: the first
            # has no previous cycle and the last has no next-cycle target.
            "valid_discharge_records": int(len(frame) + 2),
            "first_discharge_capacity_Ah": first_capacity,
            "last_discharge_capacity_Ah": float(frame["target_capacity_Ah"].iloc[-1]),
            "relative_soh_min_percent": float(
                min(frame["soh_percent"].min(), frame["target_soh_percent"].min())
            ),
            "relative_soh_max_percent": 100.0,
        }

    summary = {
        "title": "NASA cell cross-battery next-discharge SOH prediction",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation": "Leave-one-battery-out; each test battery is excluded entirely from training.",
        "batteries": list(BATTERIES),
        "target": "SOH of the next valid recorded discharge, normalized to that battery's first valid discharge capacity.",
        "features": FEATURES,
        "soh_definition": "Discharge capacity / first valid discharge capacity * 100; baseline is measured initial capacity, not rated capacity.",
        "pooled_metrics": pooled,
        "fold_metrics_file": OUTPUT_FILES[1],
        "predictions_file": OUTPUT_FILES[0],
        "battery_data_summary": battery_summary,
        "limitations": [
            "These are accelerated laboratory cell measurements, not EV battery-pack validation.",
            "The initial discharge capacity for each held-out cell is used to define relative SOH; this assumes that first measurement is available.",
            "NASA discharge cutoff voltage differs among batteries, limiting direct capacity comparability.",
            "Only four cells are included; leave-one-cell-out estimates are small-sample evidence.",
            "Current-cycle measurements are used to forecast the next recorded discharge; the model is not a multi-step RUL estimator.",
        ],
        "interpretation": "All numbers are computed from the included NASA laboratory cell files by this run; assumptions and limitations are listed separately.",
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    try:
        with (OUTPUT_DIR / OUTPUT_FILES[0]).open("x", encoding="utf-8", newline="") as file:
            predictions.to_csv(file, index=False)
        with (OUTPUT_DIR / OUTPUT_FILES[1]).open("x", encoding="utf-8", newline="") as file:
            metrics.to_csv(file, index=False)
        with (OUTPUT_DIR / OUTPUT_FILES[2]).open("x", encoding="utf-8") as file:
            json.dump(summary, file, indent=2)
    except Exception:
        print(f"Some newly created output files may remain in {OUTPUT_DIR}; no existing files were removed.")
        raise

    print(json.dumps({"output_dir": str(OUTPUT_DIR), "pooled_metrics": pooled}, indent=2))
    print("\nFold metrics:")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
