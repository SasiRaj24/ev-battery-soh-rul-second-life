"""Exploratory leave-one-cell-out RUL evaluation at NASA's 1.4 Ah EOL rule.

The script writes only to a new versioned output directory and refuses to
overwrite it. B0007 remains right-censored if its recorded trajectory never
crosses the configured threshold; it is not assigned a fabricated failure date.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parent
BATTERIES = ("B0005", "B0006", "B0007", "B0018")
EOL_CAPACITY_AH = 1.4
FEATURES = [
    "cycle_number",
    "ambient_temperature_C",
    "discharge_capacity_Ah",
    "soh_percent",
    "previous_soh_percent",
    "capacity_change_from_previous_Ah",
]
OUTPUT_DIR = ROOT / "data" / "processed" / "nasa_rul_v2"
OUTPUT_FILES = (
    "nasa_rul_v2_predictions.csv",
    "nasa_rul_v2_fold_metrics.csv",
    "nasa_rul_v2_summary.json",
)


def load_battery(battery_id: str) -> pd.DataFrame:
    source = ROOT / "data" / "nasa" / f"{battery_id}.mat"
    if not source.is_file():
        raise FileNotFoundError(f"Required NASA source is missing: {source}")
    root = loadmat(source, simplify_cells=True)[battery_id]
    events = np.atleast_1d(root["cycle"])
    rows = []
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
        rows.append({
            "battery_id": battery_id,
            "event_number": event_number,
            "cycle_number": len(rows) + 1,
            "ambient_temperature_C": float(event.get("ambient_temperature", np.nan)),
            "discharge_capacity_Ah": capacity,
        })
    frame = pd.DataFrame(rows)
    if len(frame) < 3:
        raise ValueError(f"{battery_id} has too few valid discharge records")
    frame["soh_percent"] = frame["discharge_capacity_Ah"] / frame[
        "discharge_capacity_Ah"
    ].iloc[0] * 100.0
    frame["previous_soh_percent"] = frame["soh_percent"].shift(1)
    frame["capacity_change_from_previous_Ah"] = frame[
        "discharge_capacity_Ah"
    ].diff()
    return frame


def score(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae_cycles": float(mean_absolute_error(y_true, y_pred)),
        "rmse_cycles": float(np.sqrt(mean_squared_error(y_true, y_pred))),
    }


def trend_prediction(frame: pd.DataFrame, position: int) -> float:
    start = max(0, position - 9)
    window = frame.iloc[start : position + 1]
    if len(window) < 3:
        return float("nan")
    slope = float(np.polyfit(
        window["cycle_number"].to_numpy(dtype=float),
        window["discharge_capacity_Ah"].to_numpy(dtype=float),
        deg=1,
    )[0])
    if not np.isfinite(slope) or slope >= 0:
        return float("nan")
    current_capacity = float(frame["discharge_capacity_Ah"].iloc[position])
    return max(0.0, (current_capacity - EOL_CAPACITY_AH) / -slope)


def main() -> None:
    if OUTPUT_DIR.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {OUTPUT_DIR}")
    batteries = {battery: load_battery(battery) for battery in BATTERIES}

    eol_positions: dict[str, int | None] = {}
    completed: dict[str, pd.DataFrame] = {}
    for battery, frame in batteries.items():
        crossings = np.flatnonzero(
            frame["discharge_capacity_Ah"].to_numpy() <= EOL_CAPACITY_AH
        )
        if len(crossings):
            eol_pos = int(crossings[0])
            eol_positions[battery] = eol_pos + 1
            labeled = frame.iloc[: eol_pos + 1].copy()
            labeled["rul_cycles"] = (
                float(labeled["cycle_number"].iloc[-1])
                - labeled["cycle_number"].to_numpy(dtype=float)
            )
            completed[battery] = labeled.dropna(subset=FEATURES + ["rul_cycles"])
        else:
            eol_positions[battery] = None

    eligible = tuple(b for b in BATTERIES if b in completed)
    if len(eligible) < 3:
        raise ValueError("Need at least three complete threshold-crossing cells for this exploratory LOBO analysis")

    prediction_frames: list[pd.DataFrame] = []
    metric_rows: list[dict[str, object]] = []
    for held_out in eligible:
        training_batteries = [battery for battery in eligible if battery != held_out]
        train = pd.concat([completed[b] for b in training_batteries], ignore_index=True)
        test = completed[held_out].copy().reset_index(drop=True)
        x_train, y_train = train[FEATURES], train["rul_cycles"]
        x_test, y_test = test[FEATURES], test["rul_cycles"].to_numpy(dtype=float)
        estimators = {
            "linear_regression": LinearRegression(),
            "xgboost": XGBRegressor(
                objective="reg:squarederror",
                n_estimators=200,
                max_depth=2,
                learning_rate=0.025,
                subsample=0.9,
                colsample_bytree=1.0,
                reg_lambda=2.0,
                random_state=42,
                n_jobs=1,
            ),
        }
        fold_predictions = {
            "linear_regression": np.maximum(0.0, estimators["linear_regression"].fit(x_train, y_train).predict(x_test)),
            "xgboost": np.maximum(0.0, estimators["xgboost"].fit(x_train, y_train).predict(x_test)),
        }
        fold_predictions["recent_slope_extrapolation"] = np.array([
            trend_prediction(batteries[held_out], int(pos))
            for pos in range(len(test))
        ], dtype=float)
        fold_predictions["cycle_index_oracle_control"] = y_test.copy()

        for model_name, prediction in fold_predictions.items():
            valid = np.isfinite(prediction)
            actual = y_test[valid]
            predicted = prediction[valid]
            record = test.loc[valid, [
                "battery_id", "cycle_number", "discharge_capacity_Ah", "soh_percent",
                "previous_soh_percent", "capacity_change_from_previous_Ah", "rul_cycles",
            ]].copy()
            record["held_out_battery"] = held_out
            record["model"] = model_name
            record["predicted_rul_cycles"] = predicted
            record["absolute_error_cycles"] = np.abs(actual - predicted)
            prediction_frames.append(record)
            metric_rows.append({
                "held_out_battery": held_out,
                "training_batteries": ",".join(training_batteries),
                "model": model_name,
                "training_rows": int(len(train)),
                "testing_rows_scored": int(valid.sum()),
                "testing_rows_total": int(len(test)),
                **score(actual, predicted),
            })

    predictions = pd.concat(prediction_frames, ignore_index=True)
    metrics = pd.DataFrame(metric_rows)
    pooled = {}
    for model_name, group in predictions.groupby("model", sort=True):
        pooled[model_name] = score(
            group["rul_cycles"].to_numpy(dtype=float),
            group["predicted_rul_cycles"].to_numpy(dtype=float),
        )

    battery_status = {}
    for battery, frame in batteries.items():
        eol_cycle = eol_positions[battery]
        battery_status[battery] = {
            "valid_discharge_records": int(len(frame)),
            "first_capacity_Ah": float(frame["discharge_capacity_Ah"].iloc[0]),
            "last_capacity_Ah": float(frame["discharge_capacity_Ah"].iloc[-1]),
            "eol_threshold_crossed": eol_cycle is not None,
            "first_eol_discharge_index": eol_cycle,
            "censoring_note": (
                None if eol_cycle is not None else
                f"Right-censored: did not reach {EOL_CAPACITY_AH:.1f} Ah during {len(frame)} observed discharges; true RUL is unknown and exceeds the observed follow-up."
            ),
        }

    summary = {
        "title": "NASA cell RUL prediction, exploratory v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "task": "Remaining recorded discharge cycles until the first measured capacity at or below 1.4 Ah.",
        "eol_threshold_capacity_Ah": EOL_CAPACITY_AH,
        "validation": "Leave-one-battery-out across threshold-crossing cells only; each fold trains on the other complete trajectories.",
        "batteries": list(BATTERIES),
        "eligible_complete_trajectory_cells": list(eligible),
        "features": FEATURES,
        "pooled_metrics_cycles": pooled,
        "fold_metrics_file": OUTPUT_FILES[1],
        "predictions_file": OUTPUT_FILES[0],
        "battery_status": battery_status,
        "limitations": [
            "Only three cells cross the 1.4 Ah threshold; each fold has two independent training cells, regardless of row count.",
            "B0007 is right-censored and excluded from RUL model scoring and training; its true threshold-crossing RUL is unknown.",
            "The threshold is the dataset's 1.4 Ah / 70% of 2 Ah nominal-capacity criterion, not a universal vehicle or second-life EOL rule.",
            "Discharge cutoff voltages differ among batteries and affect measured capacity.",
            "Row-level scores are correlated within a cell; pooled errors do not represent independent-cell sample size.",
            "The recent-slope estimate is a hand-built baseline and may fail under nonlinear or non-monotonic degradation.",
            "This is cell-level accelerated laboratory research, not EV pack or field validation.",
        ],
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
        print(f"Partial new outputs, if any, remain at {OUTPUT_DIR}; no existing files were removed.")
        raise

    print(json.dumps({"output_dir": str(OUTPUT_DIR), "pooled_metrics_cycles": pooled}, indent=2))
    print("\nFold metrics:")
    print(metrics.to_string(index=False))
    print("\nCell endpoint status:")
    print(json.dumps(battery_status, indent=2))


if __name__ == "__main__":
    main()
