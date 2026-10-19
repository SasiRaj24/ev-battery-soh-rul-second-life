"""Reproducibly fit a new NASA-cell model release without replacing v2 artifacts.

Usage: .venv/Scripts/python.exe train_nasa_models_v3.py --version 3.0.0
Each version is written only into a new models/releases/<version>/ directory.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
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
RUL_TRAINING_BATTERIES = ("B0005", "B0006", "B0018")
EOL_CAPACITY_AH = 1.4
SOH_FEATURES = [
    "cycle_number", "ambient_temperature_C", "soh_percent",
    "previous_soh_percent", "capacity_change_from_previous_Ah",
]
RUL_FEATURES = [
    "cycle_number", "ambient_temperature_C", "discharge_capacity_Ah",
    "soh_percent", "previous_soh_percent", "capacity_change_from_previous_Ah",
]
RUL_PARAMETERS = {
    "objective": "reg:squarederror", "n_estimators": 200, "max_depth": 2,
    "learning_rate": 0.025, "subsample": 0.9, "colsample_bytree": 1.0,
    "reg_lambda": 2.0, "random_state": 42, "n_jobs": 1,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_cycles(battery_id: str) -> pd.DataFrame:
    source = ROOT / "data" / "nasa" / f"{battery_id}.mat"
    if not source.is_file():
        raise FileNotFoundError(f"Required source is missing: {source}")
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
        raise ValueError(f"Too few valid discharge records in {battery_id}")
    frame["soh_percent"] = frame["discharge_capacity_Ah"] / float(frame["discharge_capacity_Ah"].iloc[0]) * 100.0
    frame["previous_soh_percent"] = frame["soh_percent"].shift(1)
    frame["capacity_change_from_previous_Ah"] = frame["discharge_capacity_Ah"].diff()
    frame["target_soh_percent"] = frame["soh_percent"].shift(-1)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="3.0.0", help="New release directory name (must not already exist).")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", args.version):
        raise ValueError("Version may contain only letters, numbers, dot, underscore, and hyphen")
    release = ROOT / "models" / "releases" / args.version
    if release.exists():
        raise FileExistsError(f"Refusing to overwrite model release: {release}")

    frames = {battery: load_cycles(battery) for battery in BATTERIES}
    soh_rows = pd.concat([
        frame.dropna(subset=SOH_FEATURES + ["target_soh_percent"])
        for frame in frames.values()
    ], ignore_index=True)
    soh_model = LinearRegression().fit(soh_rows[SOH_FEATURES], soh_rows["target_soh_percent"])

    rul_rows = []
    for battery_id in RUL_TRAINING_BATTERIES:
        frame = frames[battery_id]
        crossings = np.flatnonzero(frame["discharge_capacity_Ah"].to_numpy(dtype=float) <= EOL_CAPACITY_AH)
        if not len(crossings):
            raise ValueError(f"Expected RUL training cell {battery_id} to cross {EOL_CAPACITY_AH} Ah")
        end = int(crossings[0])
        labeled = frame.iloc[: end + 1].copy()
        labeled["rul_cycles"] = float(labeled["cycle_number"].iloc[-1]) - labeled["cycle_number"].to_numpy(dtype=float)
        rul_rows.append(labeled.dropna(subset=RUL_FEATURES + ["rul_cycles"]))
    rul_training = pd.concat(rul_rows, ignore_index=True)
    rul_model = XGBRegressor(**RUL_PARAMETERS).fit(rul_training[RUL_FEATURES], rul_training["rul_cycles"])

    release.parent.mkdir(parents=True, exist_ok=True)
    release.mkdir(exist_ok=False)
    artifacts = {
        "soh": release / "nasa_soh_linear.joblib",
        "rul": release / "nasa_rul_xgboost.joblib",
    }
    with artifacts["soh"].open("xb") as stream:
        joblib.dump(soh_model, stream)
    with artifacts["rul"].open("xb") as stream:
        joblib.dump(rul_model, stream)
    manifest = {
        "model_version": args.version,
        "release_status": "experimental_not_default",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_script": Path(__file__).name,
        "training_script_sha256": sha256(Path(__file__)),
        "source_sha256": {
            battery: sha256(ROOT / "data" / "nasa" / f"{battery}.mat")
            for battery in BATTERIES
        },
        "runtime_versions": {
            package: importlib.metadata.version(package)
            for package in ("numpy", "pandas", "scikit-learn", "scipy", "xgboost", "joblib")
        },
        "models": {
            "next_cycle_soh": {
                "artifact": artifacts["soh"].name,
                "sha256": sha256(artifacts["soh"]),
                "estimator": "sklearn.linear_model.LinearRegression",
                "feature_order": SOH_FEATURES,
                "target": "next recorded discharge relative SOH percent, baseline is first valid observed discharge capacity",
                "training_cells": list(BATTERIES),
                "training_rows": int(len(soh_rows)),
            },
            "rul": {
                "artifact": artifacts["rul"].name,
                "sha256": sha256(artifacts["rul"]),
                "estimator": "xgboost.XGBRegressor",
                "parameters": RUL_PARAMETERS,
                "feature_order": RUL_FEATURES,
                "target": f"remaining recorded discharges to first capacity <= {EOL_CAPACITY_AH} Ah",
                "rul_eol_capacity_Ah": EOL_CAPACITY_AH,
                "training_cells": list(RUL_TRAINING_BATTERIES),
                "training_rows": int(len(rul_training)),
                "censored_cells_excluded": ["B0007"],
            },
        },
        "validation_reference": "See data/processed/research_evaluation_v4 and reports/research_evaluation_v4_report.md; final fit artifacts are not the held-out fold estimators.",
        "limitations": [
            "Only four independent SOH cells and three complete RUL cells are available.",
            "B0007 is right-censored for the 1.4 Ah target and excluded from RUL fitting.",
            "NASA cutoff-voltage and test protocol differences limit transfer.",
            "Laboratory-cell results do not validate EV packs, field performance, or second-life safety.",
        ],
        "second_life_screen": {
            "status": "capacity_only_pre_screen",
            "application_recommendation": None,
            "project_assumption_thresholds_relative_soh_percent": {"lower_capacity_review": 70.0, "higher_capacity_review": 80.0},
        },
    }
    with (release / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"release": str(release), "status": manifest["release_status"], "manifest": str(release / "manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
