"""Write empirical feature-support ranges for the source-specific model guard."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
TRACE = ROOT / "data/processed/multidataset_comparison_v1_3/harmonized_capacity_traces_v1_3.csv"
OUTPUT = ROOT / "models/releases/4.0.0-multisource-experimental/feature_support_v1.json"
FEATURES = [
    "current_soh_percent", "previous_soh_percent",
    "previous_soh_change_pp_per_100_cycles", "previous_gap_cycles",
]


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    traces = pd.read_csv(TRACE)
    result = {
        "definition": "1st and 99th percentiles of cell-balanced source-family training rows; out-of-range inputs are withheld",
        "features": FEATURES,
        "by_source": {},
    }
    for source, family, selected in [
        ("Oxford", "Oxford", traces[traces.dataset_family == "Oxford"]),
        ("CALCE_CS2", "CALCE_CS2", traces[traces.dataset_family == "CALCE_CS2"]),
    ]:
        valid = selected.dropna(subset=FEATURES + ["next_soh_change_pp_per_100_cycles"]).query(
            "previous_gap_cycles > 0 and next_gap_cycles > 0"
        )
        result["by_source"][source] = {
            "training_cells": sorted(valid.battery_id.unique().tolist()),
            "valid_training_rows": int(len(valid)),
            "limits": {
                feature: {
                    "lower_q01": float(valid[feature].quantile(0.01)),
                    "upper_q99": float(valid[feature].quantile(0.99)),
                    "observed_min": float(valid[feature].min()),
                    "observed_max": float(valid[feature].max()),
                }
                for feature in FEATURES
            },
        }
    with OUTPUT.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(OUTPUT)
    print(json.dumps(result["by_source"], indent=2))


if __name__ == "__main__":
    main()
