"""Read and validate immutable cross-battery evaluation outputs."""

import json
from pathlib import Path

import pandas as pd
from fastapi import HTTPException


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = PROJECT_ROOT / "data" / "processed" / "nasa_cross_battery_v1"
ALLOWED_BATTERIES = {"B0005", "B0006", "B0007", "B0018"}
ALLOWED_MODELS = {"persistence", "linear_regression", "xgboost"}


def _load_json(filename: str) -> dict:
    path = ARTIFACT_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Validation artifacts are not available")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Validation summary cannot be read") from exc


def get_summary() -> dict:
    summary = _load_json("nasa_cross_battery_v1_summary.json")
    correction_path = ARTIFACT_DIR / "nasa_cross_battery_v1_quality_addendum.json"
    if correction_path.is_file():
        try:
            correction = json.loads(correction_path.read_text(encoding="utf-8"))
            for battery, count in correction["valid_discharge_records_by_battery"].items():
                summary["battery_data_summary"][battery]["valid_discharge_records"] = count
            for battery, capacity in correction["first_discharge_capacity_Ah_by_battery"].items():
                summary["battery_data_summary"][battery]["first_discharge_capacity_Ah"] = capacity
            for battery, max_soh in correction["relative_soh_max_percent_by_battery"].items():
                summary["battery_data_summary"][battery]["relative_soh_max_percent"] = max_soh
            summary["quality_addendum"] = correction["note"]
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=503, detail="Validation correction cannot be read") from exc
    return summary


def get_predictions(battery_id: str, model: str) -> list[dict]:
    battery_id = battery_id.upper()
    if battery_id not in ALLOWED_BATTERIES:
        raise HTTPException(status_code=404, detail="Unknown battery in this study")
    if model not in ALLOWED_MODELS:
        raise HTTPException(status_code=404, detail="Unknown evaluation model")
    path = ARTIFACT_DIR / "nasa_cross_battery_v1_predictions.csv"
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Validation predictions are not available")
    frame = pd.read_csv(path)
    selected = frame[
        (frame["held_out_battery"] == battery_id) & (frame["model"] == model)
    ]
    if selected.empty:
        raise HTTPException(status_code=404, detail="No predictions for this selection")
    return selected.replace({float("nan"): None}).to_dict(orient="records")


def get_fold_metrics() -> list[dict]:
    path = ARTIFACT_DIR / "nasa_cross_battery_v1_fold_metrics.csv"
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Fold metrics are not available")
    return pd.read_csv(path).to_dict(orient="records")
