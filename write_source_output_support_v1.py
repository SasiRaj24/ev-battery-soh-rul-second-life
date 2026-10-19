"""Record empirical 1%-99% next-record SOH-change support for source models."""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
TRACE = ROOT / "data/processed/multidataset_comparison_v1_3/harmonized_capacity_traces_v1_3.csv"
OUTPUT = ROOT / "models/releases/4.0.0-multisource-experimental/output_support_v1.json"


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    df = pd.read_csv(TRACE)
    result = {
        "definition": "Empirical 1st and 99th percentiles of observed next-record SOH change; model forecasts outside this range are withheld.",
        "by_source": {},
    }
    for source in ("Oxford", "CALCE_CS2"):
        rows = df[df.dataset_family == source].copy()
        delta = (rows.next_soh_percent - rows.soh_percent).dropna()
        result["by_source"][source] = {
            "lower_q01_soh_pp": float(delta.quantile(0.01)),
            "upper_q99_soh_pp": float(delta.quantile(0.99)),
            "records": int(len(delta)),
        }
    with OUTPUT.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(OUTPUT)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
