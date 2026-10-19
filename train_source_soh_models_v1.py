"""Fit versioned exploratory Oxford and CALCE CS2 SOH models.

Inputs are the exclusive cell-holdout comparison traces in v1.3. NASA
artifacts remain the existing, separate v2 models. This script writes a new
release directory and refuses to overwrite it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parent
TRACE_PATH = ROOT / "data/processed/multidataset_comparison_v1_3/harmonized_capacity_traces_v1_3.csv"
COMPARISON_MANIFEST = ROOT / "data/processed/multidataset_comparison_v1_3/comparison_manifest_v1_3.json"
RELEASE = ROOT / "models/releases/4.0.0-multisource-experimental"
FEATURES = [
    "current_soh_percent", "previous_soh_percent",
    "previous_soh_change_pp_per_100_cycles", "previous_gap_cycles",
]
TARGET = "next_soh_change_pp_per_100_cycles"
XGB_PARAMETERS = {
    "objective": "reg:squarederror", "n_estimators": 160, "max_depth": 2,
    "learning_rate": 0.025, "subsample": 0.9, "colsample_bytree": 1.0,
    "reg_lambda": 2.0, "random_state": 42, "n_jobs": 1,
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def weights(frame: pd.DataFrame) -> np.ndarray:
    count_per_cell = frame.groupby("battery_id")["battery_id"].transform("size").to_numpy(float)
    n_cells = frame["battery_id"].nunique()
    return (1.0 / (n_cells * count_per_cell))


def fit_and_save(family: str, battery_ids: list[str], estimator: str, artifact_name: str, traces: pd.DataFrame) -> dict:
    frame = traces[traces["battery_id"].isin(battery_ids)].copy()
    frame = frame.dropna(subset=FEATURES + [TARGET]).query("previous_gap_cycles > 0 and next_gap_cycles > 0")
    if frame["battery_id"].nunique() != len(battery_ids) or frame.empty:
        raise ValueError(f"Incomplete training records for {family}")
    sample_weight = weights(frame)
    if estimator == "ridge":
        model = make_pipeline(StandardScaler(), Ridge(alpha=2.0))
        model.fit(frame[FEATURES], frame[TARGET], ridge__sample_weight=sample_weight)
        estimator_name = "StandardScaler + Ridge(alpha=2.0)"
    elif estimator == "xgboost":
        model = XGBRegressor(**XGB_PARAMETERS)
        model.fit(frame[FEATURES], frame[TARGET], sample_weight=sample_weight)
        estimator_name = "XGBRegressor"
    else:
        raise ValueError(estimator)
    path = RELEASE / artifact_name
    with path.open("xb") as stream:
        joblib.dump(model, stream)
    validation = {
        "method": "leave-one-cell-out; the reported validation value is from held-out folds, not this final all-cell fit",
        "held_out_cells": len(battery_ids),
        "model_macro_cell_mae_soh_pp": {
            "Oxford": 0.256013,
            "CALCE_CS2": 0.990584,
        }[family],
        "persistence_macro_cell_mae_soh_pp": {
            "Oxford": 0.452050,
            "CALCE_CS2": 0.993798,
        }[family],
        "observed_cell_error_range_soh_pp": {
            "Oxford": [0.1302, 0.5479],
            "CALCE_CS2": [0.9231, 1.0997],
        }[family],
        "interpretation": (
            "Exploratory cell-held-out result; eight cells, no confidence interval."
            if family == "Oxford" else
            "Exploratory result is effectively tied with persistence at this precision; six cells, no confidence interval."
        ),
    }
    return {
        "artifact": artifact_name,
        "sha256": digest(path),
        "estimator": estimator_name,
        "feature_order": FEATURES,
        "target": TARGET,
        "capacity_reference": "capacity from the first measured record supplied by the user",
        "training_cells": battery_ids,
        "training_rows": int(len(frame)),
        "sample_weighting": "equal total weight per cell, then equal weight per valid record",
        "validation": validation,
    }


def main() -> None:
    if not TRACE_PATH.is_file() or not COMPARISON_MANIFEST.is_file():
        raise FileNotFoundError("Run compare_harmonized_multidataset_v1_3.py first")
    if RELEASE.exists():
        raise FileExistsError(f"Refusing to overwrite model release: {RELEASE}")
    traces = pd.read_csv(TRACE_PATH)
    comparison_manifest = json.loads(COMPARISON_MANIFEST.read_text(encoding="utf-8"))
    cells = comparison_manifest["included_cells_by_family"]
    RELEASE.mkdir(parents=True, exist_ok=False)
    source_models = {
        "Oxford": fit_and_save("Oxford", cells["Oxford"], "ridge", "oxford_soh_ridge_v1.joblib", traces),
        "CALCE_CS2": fit_and_save("CALCE_CS2", cells["CALCE_CS2"], "xgboost", "calce_cs2_soh_xgboost_v1.joblib", traces),
    }
    old_manifest_path = ROOT / "models/nasa_model_manifest_v2.json"
    old = json.loads(old_manifest_path.read_text(encoding="utf-8"))
    manifest = {
        "model_version": "4.0.0-multisource-experimental",
        "release_status": "experimental_source_specific_models",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_script": str(Path(__file__).relative_to(ROOT)),
        "training_script_sha256": digest(Path(__file__).resolve()),
        "comparison_manifest": "data/processed/multidataset_comparison_v1_3/comparison_manifest_v1_3.json",
        "comparison_manifest_sha256": digest(COMPARISON_MANIFEST),
        "models": {
            "next_cycle_soh": {
                **old["models"]["next_cycle_soh"],
                "artifact": "../../nasa_soh_linear_v2.joblib",
                "artifact_model_version": "2.0.0-experimental",
            },
            "rul": {
                **old["models"]["rul"],
                "artifact": "../../nasa_rul_xgboost_v2.joblib",
                "artifact_model_version": "2.0.0-experimental",
            },
        },
        "source_models": source_models,
        "source_rul_status": {
            "NASA": "Existing NASA-specific RUL model only; 1.4 Ah study endpoint.",
            "Oxford": "RUL withheld: only two of eight cells crossed the 70%-of-first-record exploratory endpoint.",
            "CALCE_CS2": "RUL withheld in the interactive analyzer; cross-family RUL validation was not reliable enough for transfer.",
        },
        "limitations": [
            "Models are selected and fitted for their named source family; no cross-family generalization is claimed.",
            "Oxford and CALCE SOH use a harmonized four-feature model and the user-provided first-measurement reference capacity.",
            "CALCE validation is effectively tied with persistence and should be treated as a research comparison, not a demonstrated improvement.",
            "RUL and second-life advice are not available for Oxford or CALCE in this release.",
            "Laboratory-cell evidence does not establish EV pack or field validation.",
        ],
    }
    manifest_path = RELEASE / "manifest.json"
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"release": str(RELEASE), "manifest": str(manifest_path), "source_models": source_models}, indent=2))


if __name__ == "__main__":
    main()
