"""Create non-destructive NASA/Oxford extensions and audit CALCE inputs.

This version keeps each dataset family separate. It does not treat the
laboratory cell results as EV-pack validation, and refuses to reuse an output
directory.
"""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "processed" / "additional_datasets_v3_1"
EOL_RELATIVE_SOH = 70.0  # Explicit project comparison assumption, not a universal EOL rule.
SOH_FEATURES = [
    "cycle_number", "ambient_temperature_C", "soh_percent",
    "previous_soh_percent", "capacity_change_from_previous_Ah",
]
RUL_FEATURES = [
    "cycle_number", "ambient_temperature_C", "discharge_capacity_Ah",
    "soh_percent", "previous_soh_percent", "capacity_change_from_previous_Ah",
]


def _number(value, default=np.nan) -> float:
    try:
        array = np.asarray(value).reshape(-1)
        result = float(array[0])
        return result if np.isfinite(result) else default
    except (TypeError, ValueError, IndexError):
        return default


def _features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["soh_percent"] = out["discharge_capacity_Ah"] / out[
        "discharge_capacity_Ah"
    ].iloc[0] * 100.0
    out["previous_soh_percent"] = out["soh_percent"].shift(1)
    out["capacity_change_from_previous_Ah"] = out[
        "discharge_capacity_Ah"
    ].diff()
    out["target_cycle_number"] = out["cycle_number"].shift(-1)
    out["target_soh_percent"] = out["soh_percent"].shift(-1)
    out["target_capacity_Ah"] = out["discharge_capacity_Ah"].shift(-1)
    return out


def load_nasa() -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    traces: dict[str, pd.DataFrame] = {}
    quality: dict[str, dict] = {}
    for source in sorted((ROOT / "data" / "nasa").glob("B*.mat")):
        if not re.fullmatch(r"B\d{4}", source.stem):
            continue
        loaded = loadmat(source, simplify_cells=True)
        if source.stem not in loaded:
            quality[source.stem] = {"status": "skipped", "reason": "Expected battery variable missing"}
            continue
        events = np.atleast_1d(loaded[source.stem].get("cycle", []))
        rows = []
        missing_capacity = 0
        invalid_capacity = 0
        for event_number, event in enumerate(events, start=1):
            if not isinstance(event, dict) or str(event.get("type", "")).strip().lower() != "discharge":
                continue
            data = event.get("data") or {}
            capacity = _number(data.get("Capacity", np.nan)) if isinstance(data, dict) else np.nan
            if not np.isfinite(capacity):
                missing_capacity += 1
                continue
            if capacity <= 0:
                invalid_capacity += 1
                continue
            rows.append({
                "dataset": "NASA_PCoE",
                "battery_id": source.stem,
                "cycle_number": len(rows) + 1,
                "source_event_number": event_number,
                "ambient_temperature_C": _number(event.get("ambient_temperature", np.nan)),
                "discharge_capacity_Ah": capacity,
                "capacity_measurement": "NASA reported discharge Capacity",
                "source_file": str(source.relative_to(ROOT)),
            })
        if rows:
            traces[source.stem] = _features(pd.DataFrame(rows))
        quality[source.stem] = {
            "status": "processed" if rows else "skipped",
            "discharge_events": int(sum(
                1 for event in events
                if isinstance(event, dict) and str(event.get("type", "")).strip().lower() == "discharge"
            )),
            "valid_positive_capacity_records": len(rows),
            "missing_capacity_records": missing_capacity,
            "nonpositive_capacity_records_excluded_from_model_table": invalid_capacity,
        }
    return traces, quality


def load_oxford() -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    source = ROOT / "data" / "oxford" / "Oxford_Battery_Degradation_Dataset_1.mat"
    loaded = loadmat(source, simplify_cells=True)
    traces: dict[str, pd.DataFrame] = {}
    quality: dict[str, dict] = {}
    for index in range(1, 9):
        cell_id = f"Cell{index}"
        cell = loaded.get(cell_id)
        if not isinstance(cell, dict):
            quality[cell_id] = {"status": "skipped", "reason": "Cell structure missing"}
            continue
        rows = []
        for key, checkpoint in cell.items():
            match = re.fullmatch(r"cyc(\d+)", str(key))
            if not match or not isinstance(checkpoint, dict):
                continue
            discharge = checkpoint.get("C1dc")
            if not isinstance(discharge, dict) or "q" not in discharge:
                continue
            q = np.asarray(discharge["q"], dtype=float).reshape(-1)
            q = q[np.isfinite(q)]
            if not q.size:
                continue
            # Oxford readme defines q in mAh; C1dc q is negative during discharge.
            capacity_ah = float(abs(np.min(q)) / 1000.0)
            if capacity_ah <= 0:
                continue
            temperature = np.asarray(discharge.get("T", []), dtype=float).reshape(-1)
            temperature = temperature[np.isfinite(temperature)]
            rows.append({
                "dataset": "Oxford_Battery_Degradation_Dataset_1",
                "battery_id": cell_id,
                "cycle_number": int(match.group(1)),
                "source_event_number": key,
                "ambient_temperature_C": float(np.nanmedian(temperature)) if temperature.size else 40.0,
                "discharge_capacity_Ah": capacity_ah,
                "capacity_measurement": "absolute range of Oxford C1dc q, mAh converted to Ah",
                "source_file": str(source.relative_to(ROOT)),
            })
        frame = pd.DataFrame(rows).sort_values("cycle_number").reset_index(drop=True)
        if len(frame) >= 3:
            traces[cell_id] = _features(frame)
        quality[cell_id] = {
            "status": "processed" if cell_id in traces else "skipped",
            "characterization_checkpoints": len(frame),
            "cycle_spacing": "nominally every 100 drive cycles; missing checkpoints retained as gaps",
        }
    return traces, quality


def _metric(actual: np.ndarray, predicted: np.ndarray, suffix: str) -> dict[str, float]:
    return {
        f"mae_{suffix}": float(mean_absolute_error(actual, predicted)),
        f"rmse_{suffix}": float(np.sqrt(mean_squared_error(actual, predicted))),
        "r2": float(r2_score(actual, predicted)) if len(actual) > 1 else float("nan"),
    }


def validate_soh(dataset: str, traces: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    predictions, metrics = [], []
    eligible = {
        name: frame.dropna(subset=SOH_FEATURES + ["target_soh_percent"]).reset_index(drop=True)
        for name, frame in traces.items()
    }
    eligible = {name: frame for name, frame in eligible.items() if len(frame) >= 2}
    for held_out, test in eligible.items():
        training = pd.concat(
            [frame for name, frame in eligible.items() if name != held_out], ignore_index=True
        ) if len(eligible) > 1 else pd.DataFrame()
        if training.empty:
            continue
        x_train = training[SOH_FEATURES].replace([np.inf, -np.inf], np.nan)
        x_test = test[SOH_FEATURES].replace([np.inf, -np.inf], np.nan)
        medians = x_train.median().fillna(0.0)
        x_train = x_train.fillna(medians)
        x_test = x_test.fillna(medians)
        actual = test["target_soh_percent"].to_numpy(dtype=float)
        model_specs = {
            "persistence": None,
            "linear_regression": LinearRegression(),
            "xgboost": XGBRegressor(
                objective="reg:squarederror", n_estimators=200, max_depth=3,
                learning_rate=0.03, subsample=0.9, colsample_bytree=1.0,
                reg_lambda=1.0, random_state=42, n_jobs=1,
            ),
        }
        for model_name, model in model_specs.items():
            if model is None:
                predicted = test["soh_percent"].to_numpy(dtype=float)
            else:
                model.fit(x_train, training["target_soh_percent"].to_numpy(dtype=float))
                predicted = model.predict(x_test)
            out = test[[
                "battery_id", "cycle_number", "target_cycle_number",
                "discharge_capacity_Ah", "soh_percent", "target_capacity_Ah",
                "target_soh_percent",
            ]].copy()
            out["dataset"] = dataset
            out["held_out_cell"] = held_out
            out["model"] = model_name
            out["predicted_soh_percent"] = predicted
            out["absolute_error_percentage_points"] = np.abs(actual - predicted)
            predictions.append(out)
            metrics.append({
                "dataset": dataset,
                "held_out_cell": held_out,
                "training_cells": ",".join(name for name in eligible if name != held_out),
                "model": model_name,
                "training_rows": len(training),
                "testing_rows": len(test),
                **_metric(actual, predicted, "soh_percentage_points"),
            })
    return (
        pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame(),
        pd.DataFrame(metrics),
    )


def validate_rul(dataset: str, traces: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    eligible: dict[str, pd.DataFrame] = {}
    cell_status = {}
    for name, source_frame in traces.items():
        frame = source_frame.copy().reset_index(drop=True)
        threshold_ah = float(frame["discharge_capacity_Ah"].iloc[0] * EOL_RELATIVE_SOH / 100.0)
        crossings = np.flatnonzero(frame["discharge_capacity_Ah"].to_numpy(dtype=float) <= threshold_ah)
        if not len(crossings):
            cell_status[name] = {
                "status": "right_censored",
                "last_soh_percent": float(frame["soh_percent"].iloc[-1]),
                "threshold_soh_percent": EOL_RELATIVE_SOH,
            }
            continue
        eol_index = int(crossings[0])
        eol_cycle = float(frame["cycle_number"].iloc[eol_index])
        frame = frame.iloc[: eol_index + 1].copy()
        frame["rul_from_70_percent_first_observation_cycles"] = (
            eol_cycle - frame["cycle_number"].to_numpy(dtype=float)
        )
        frame = frame.dropna(subset=RUL_FEATURES + ["rul_from_70_percent_first_observation_cycles"])
        if len(frame) >= 2:
            eligible[name] = frame
        cell_status[name] = {
            "status": "threshold_crossed",
            "first_crossing_cycle": eol_cycle,
            "threshold_capacity_Ah": threshold_ah,
            "threshold_soh_percent": EOL_RELATIVE_SOH,
        }

    prediction_rows, metric_rows = [], []
    for held_out, test in eligible.items():
        training = pd.concat(
            [frame for name, frame in eligible.items() if name != held_out], ignore_index=True
        ) if len(eligible) > 1 else pd.DataFrame()
        if training.empty:
            continue
        x_train = training[RUL_FEATURES].replace([np.inf, -np.inf], np.nan)
        x_test = test[RUL_FEATURES].replace([np.inf, -np.inf], np.nan)
        medians = x_train.median().fillna(0.0)
        x_train, x_test = x_train.fillna(medians), x_test.fillna(medians)
        actual = test["rul_from_70_percent_first_observation_cycles"].to_numpy(dtype=float)
        model = XGBRegressor(
            objective="reg:squarederror", n_estimators=200, max_depth=3,
            learning_rate=0.03, subsample=0.9, colsample_bytree=1.0,
            reg_lambda=1.0, random_state=42, n_jobs=1,
        )
        model.fit(
            x_train,
            training["rul_from_70_percent_first_observation_cycles"].to_numpy(dtype=float),
        )
        predicted = np.maximum(0.0, model.predict(x_test))
        out = test[["battery_id", "cycle_number", "discharge_capacity_Ah", "soh_percent"]].copy()
        out["dataset"] = dataset
        out["held_out_cell"] = held_out
        out["predicted_rul_cycles"] = predicted
        out["actual_rul_cycles"] = actual
        prediction_rows.append(out)
        metric_rows.append({
            "dataset": dataset,
            "held_out_cell": held_out,
            "training_cells": ",".join(name for name in eligible if name != held_out),
            "model": "xgboost",
            "training_rows": len(training),
            "testing_rows": len(test),
            **_metric(actual, predicted, "cycles"),
        })
    return (
        pd.concat(prediction_rows, ignore_index=True) if prediction_rows else pd.DataFrame(),
        pd.DataFrame(metric_rows),
        cell_status,
    )


def audit_calce() -> dict:
    root = ROOT / "data" / "calce"
    cs2_files = sorted((root / "CS2").rglob("*.xlsx"))
    stats_workbooks = 0
    stats_rows = 0
    no_stats_workbooks = 0
    duplicates = 0
    duplicate_dates = 0
    by_cell: dict[str, list[tuple[str, str, int, str, float]]] = {}
    for path in cs2_files:
        try:
            book = pd.ExcelFile(path)
            sheets = [sheet for sheet in book.sheet_names if sheet.lower().startswith("statistics_")]
            if not sheets:
                no_stats_workbooks += 1
                continue
            stats_workbooks += 1
            frame = pd.read_excel(path, sheet_name=sheets[0])
            required = {"Cycle_Index", "Date_Time", "Discharge_Capacity(Ah)"}
            if not required.issubset(frame.columns):
                continue
            frame = frame[["Cycle_Index", "Date_Time", "Discharge_Capacity(Ah)"]].dropna()
            stats_rows += len(frame)
            key = path.parent.name
            by_cell.setdefault(key, []).extend(
                (path.name, str(date_time), int(cycle), key, float(capacity))
                for cycle, date_time, capacity in frame.itertuples(index=False, name=None)
            )
        except Exception:
            no_stats_workbooks += 1
    for entries in by_cell.values():
        timestamps = [entry[1] for entry in entries]
        cycles = [entry[2] for entry in entries]
        duplicates += len(cycles) - len(set(cycles))
        duplicate_dates += len(timestamps) - len(set(timestamps))
    pl_files = [root / "PL" / "PL11.mat", root / "PL" / "PL13.mat"]
    pl_present = [path for path in pl_files if path.is_file()]
    exact_duplicate_copies = 0
    for path in pl_present:
        duplicate_path = root / "PL" / "SOC_0%-100%_HalfC" / path.name
        if duplicate_path.is_file() and path.stat().st_size == duplicate_path.stat().st_size:
            import hashlib
            digest = lambda p: hashlib.sha256(p.read_bytes()).digest()
            if digest(path) == digest(duplicate_path):
                exact_duplicate_copies += 1
    return {
        "cs2_excel_workbooks": len(cs2_files),
        "cs2_identifiers": sorted(path.name for path in (root / "CS2").iterdir() if path.is_dir()),
        "cs2_workbooks_with_statistics_sheets": stats_workbooks,
        "cs2_workbooks_without_statistics_sheets_or_parseable_statistics": no_stats_workbooks,
        "cs2_statistics_rows": stats_rows,
        "naive_duplicate_cycle_index_count_across_workbooks": duplicates,
        "duplicate_timestamp_count_across_workbooks": duplicate_dates,
        "pl_unique_cells": [path.stem for path in pl_present],
        "pl_verified_duplicate_file_copies": exact_duplicate_copies,
        "pl_cycle_data_status": "MATLAB table objects require a table-aware parser; scipy exposes these as opaque table handles.",
        "cs2_status": "Workbook exports overlap and restart Cycle_Index; use Date_Time and session boundaries before forming cell trajectories.",
    }


def _pooled(metrics: pd.DataFrame, metric_col: str) -> dict:
    if metrics.empty:
        return {}
    result = {}
    for model, group in metrics.groupby("model"):
        result[model] = {
            "macro_cell_mae": float(group[metric_col].mean()),
            "held_out_cells": int(group["held_out_cell"].nunique()),
            "folds": int(len(group)),
        }
    return result


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite any existing output: {OUTPUT}")
    nasa, nasa_quality = load_nasa()
    oxford, oxford_quality = load_oxford()

    nasa_soh_predictions, nasa_soh_metrics = validate_soh("NASA_PCoE", nasa)
    oxford_soh_predictions, oxford_soh_metrics = validate_soh("Oxford", oxford)
    nasa_rul_predictions, nasa_rul_metrics, nasa_rul_status = validate_rul("NASA_PCoE", nasa)
    oxford_rul_predictions, oxford_rul_metrics, oxford_rul_status = validate_rul("Oxford", oxford)

    calce = audit_calce()
    catalog = {
        "title": "Local battery datasets and separate cell-held-out validation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "interpretation": "NASA PCoE and Oxford metrics are computed separately. CALCE sources are catalogued but not scored until source sessions can be stitched without ambiguity.",
        "validation_design": "Leave-one-cell-out within each dataset family. SOH features use the current and previous observations and predict the next recorded SOH. SOH is relative to the first valid observation. RUL is cycles/checkpoints to 70% of the first observed capacity, an explicit project comparison assumption; it is not a universal end-of-life rule.",
        "scope": "Accelerated laboratory cells only; not field or EV pack validation.",
        "nasa": {
            "processed_cells": len(nasa),
            "source_quality_by_cell": nasa_quality,
            "soh_pooled_macro_cell_metrics": _pooled(nasa_soh_metrics, "mae_soh_percentage_points"),
            "rul_pooled_macro_cell_metrics": _pooled(nasa_rul_metrics, "mae_cycles"),
            "rul_status_by_cell": nasa_rul_status,
        },
        "oxford": {
            "processed_cells": len(oxford),
            "source_quality_by_cell": oxford_quality,
            "soh_pooled_macro_cell_metrics": _pooled(oxford_soh_metrics, "mae_soh_percentage_points"),
            "rul_pooled_macro_cell_metrics": _pooled(oxford_rul_metrics, "mae_cycles"),
            "rul_status_by_cell": oxford_rul_status,
        },
        "calce": calce,
        "notes": [
            "An earlier development run in additional_datasets_v3 aligned the SOH target to the current row and is invalid due to direct target leakage; only the corrected additional_datasets_v3_1 results should be used.",
            "The existing v2 inference artifacts remain the four-cell NASA models; these additional results are a separate validation extension.",
            "CALCE CS2 Statistics discharge capacity is cumulative in the observed workbooks, and workbook exports overlap with reset cycle indices. No artificial continuity or performance metric is inferred.",
            "CALCE PL11/PL13 are represented by duplicate copies in two folders; duplicates are counted once. Their MATLAB table payloads are opaque to the installed SciPy reader.",
            "Oxford capacity is derived from the magnitude of the minimum C1dc q in mAh, converted to Ah, following the source readme's units.",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=False)
    tables = {
        "nasa_capacity_traces_v3.csv": pd.concat(nasa.values(), ignore_index=True),
        "oxford_capacity_traces_v3.csv": pd.concat(oxford.values(), ignore_index=True),
        "nasa_soh_lobo_predictions_v3.csv": nasa_soh_predictions,
        "nasa_soh_lobo_metrics_v3.csv": nasa_soh_metrics,
        "oxford_soh_lobo_predictions_v3.csv": oxford_soh_predictions,
        "oxford_soh_lobo_metrics_v3.csv": oxford_soh_metrics,
        "nasa_rul_70pct_predictions_v3.csv": nasa_rul_predictions,
        "nasa_rul_70pct_metrics_v3.csv": nasa_rul_metrics,
        "oxford_rul_70pct_predictions_v3.csv": oxford_rul_predictions,
        "oxford_rul_70pct_metrics_v3.csv": oxford_rul_metrics,
    }
    try:
        for filename, frame in tables.items():
            with (OUTPUT / filename).open("x", encoding="utf-8", newline="") as stream:
                frame.to_csv(stream, index=False)
        with (OUTPUT / "dataset_catalog_v3.json").open("x", encoding="utf-8") as stream:
            json.dump(catalog, stream, indent=2, allow_nan=False)
    except Exception:
        print(f"New partial outputs, if any, remain under {OUTPUT}; no source or prior output was changed.")
        raise
    print(json.dumps({
        "output": str(OUTPUT),
        "nasa_cells": len(nasa),
        "oxford_cells": len(oxford),
        "calce": calce,
        "nasa_soh": catalog["nasa"]["soh_pooled_macro_cell_metrics"],
        "oxford_soh": catalog["oxford"]["soh_pooled_macro_cell_metrics"],
        "nasa_rul": catalog["nasa"]["rul_pooled_macro_cell_metrics"],
        "oxford_rul": catalog["oxford"]["rul_pooled_macro_cell_metrics"],
    }, indent=2))


if __name__ == "__main__":
    main()
