"""Fit versioned experimental models from NASA cells for API inference.

Evaluation belongs to validate_nasa_cross_battery_v1.py and
validate_nasa_rul_v2.py. These final artifacts use all eligible NASA cells,
so their outputs are research estimates, not independent validation scores.
All output files are exclusive-create and must not already exist.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.io import loadmat
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parent
BATTERIES = ("B0005", "B0006", "B0007", "B0018")
RUL_ELIGIBLE = ("B0005", "B0006", "B0018")
EOL_AH = 1.4
SOH_FEATURES = [
    "cycle_number", "ambient_temperature_C", "soh_percent",
    "previous_soh_percent", "capacity_change_from_previous_Ah",
]
RUL_FEATURES = [
    "cycle_number", "ambient_temperature_C", "discharge_capacity_Ah",
    "soh_percent", "previous_soh_percent", "capacity_change_from_previous_Ah",
]
MODEL_DIR = ROOT / "models"
OUTPUTS = {
    "soh": MODEL_DIR / "nasa_soh_linear_v2.joblib",
    "rul": MODEL_DIR / "nasa_rul_xgboost_v2.joblib",
    "manifest": MODEL_DIR / "nasa_model_manifest_v2.json",
}


def load_cycles(battery_id: str) -> pd.DataFrame:
    path = ROOT / "data" / "nasa" / f"{battery_id}.mat"
    root = loadmat(path, simplify_cells=True)[battery_id]
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
    frame["soh_percent"] = frame["discharge_capacity_Ah"] / frame[
        "discharge_capacity_Ah"
    ].iloc[0] * 100.0
    frame["previous_soh_percent"] = frame["soh_percent"].shift(1)
    frame["capacity_change_from_previous_Ah"] = frame[
        "discharge_capacity_Ah"
    ].diff()
    frame["target_soh_percent"] = frame["soh_percent"].shift(-1)
    return frame


def main() -> None:
    conflicts = [str(path) for path in OUTPUTS.values() if path.exists()]
    if conflicts:
        raise FileExistsError("Refusing to overwrite model artifacts:\n" + "\n".join(conflicts))

    frames = {battery: load_cycles(battery) for battery in BATTERIES}
    soh_rows = pd.concat(
        [frame.dropna(subset=SOH_FEATURES + ["target_soh_percent"])
         for frame in frames.values()],
        ignore_index=True,
    )
    soh_model = LinearRegression().fit(
        soh_rows[SOH_FEATURES], soh_rows["target_soh_percent"]
    )

    rul_rows = []
    for battery in RUL_ELIGIBLE:
        frame = frames[battery].copy()
        crossing = np.flatnonzero(
            frame["discharge_capacity_Ah"].to_numpy() <= EOL_AH
        )
        if not len(crossing):
            raise ValueError(f"Expected threshold-crossing training cell {battery} to cross {EOL_AH} Ah")
        end = int(crossing[0])
        labeled = frame.iloc[: end + 1].copy()
        labeled["rul_cycles"] = (
            float(labeled["cycle_number"].iloc[-1])
            - labeled["cycle_number"].to_numpy(dtype=float)
        )
        rul_rows.append(labeled.dropna(subset=RUL_FEATURES + ["rul_cycles"]))
    rul_training = pd.concat(rul_rows, ignore_index=True)
    rul_model = XGBRegressor(
        objective="reg:squarederror",
        n_estimators=200,
        max_depth=2,
        learning_rate=0.025,
        subsample=0.9,
        colsample_bytree=1.0,
        reg_lambda=2.0,
        random_state=42,
        n_jobs=1,
    ).fit(rul_training[RUL_FEATURES], rul_training["rul_cycles"])

    manifest = {
        "model_version": "2.0.0-experimental",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "models": {
            "next_cycle_soh": {
                "artifact": OUTPUTS["soh"].name,
                "estimator": "sklearn.linear_model.LinearRegression",
                "feature_order": SOH_FEATURES,
                "target": "next recorded discharge relative SOH percent",
                "training_cells": list(BATTERIES),
                "training_rows": int(len(soh_rows)),
                "cross_battery_comparator": "LOBO MAE 0.5924 SOH percentage points; persistence MAE 0.5574",
            },
            "rul": {
                "artifact": OUTPUTS["rul"].name,
                "estimator": "xgboost.XGBRegressor",
                "feature_order": RUL_FEATURES,
                "target": f"remaining recorded discharges until first capacity <= {EOL_AH} Ah",
                "training_cells": list(RUL_ELIGIBLE),
                "training_rows": int(len(rul_training)),
                "cross_battery_comparator": "Exploratory three-cell LOBO; XGBoost pooled MAE 11.67 cycles across three held-out complete cells",
                "censored_cells_excluded": ["B0007"],
            },
        },
        "provenance": "NASA PCoE accelerated-aging laboratory cells B0005, B0006, B0007 and B0018.",
        "limitations": [
            "Final inference artifacts are fitted on the available eligible cells; validation metrics come only from held-out-cell evaluation and are not these artifacts' out-of-sample performance.",
            "Only four cells are available and only three cross the 1.4 Ah RUL threshold.",
            "B0007 is right-censored; it is excluded from RUL training rather than assigned an invented failure time.",
            "This dataset does not establish vehicle-pack performance or second-life safety.",
        ],
        "second_life_screen": {
            "status": "heuristic_only",
            "thresholds_relative_soh_percent": {"higher_capacity_review": 80.0, "lower_capacity_review": 70.0},
            "disclaimer": "Project screening assumptions, not universal industry cutoffs, certification criteria, or a safety determination.",
        },
    }

    with OUTPUTS["soh"].open("xb") as file:
        joblib.dump(soh_model, file)
    with OUTPUTS["rul"].open("xb") as file:
        joblib.dump(rul_model, file)
    with OUTPUTS["manifest"].open("x", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)
    print(json.dumps({"saved": [str(p) for p in OUTPUTS.values()], "manifest": manifest}, indent=2))


if __name__ == "__main__":
    main()
