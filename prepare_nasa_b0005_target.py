
from pathlib import Path

import pandas as pd


def main():
    source = Path(
        "data/processed/nasa_b0005/nasa_b0005_ml_features.csv"
    )
    output = Path(
        "data/processed/nasa_b0005/nasa_b0005_next_cycle_target.csv"
    )

    if not source.is_file():
        raise FileNotFoundError(f"Source not found: {source}")

    if output.exists():
        raise FileExistsError(
            f"Output already exists; refusing to overwrite: {output}"
        )

    df = pd.read_csv(source).sort_values("cycle_number").reset_index(drop=True)

    # The target is the SOH and cycle number of the next recorded cycle.
    df["target_cycle_number"] = df["cycle_number"].shift(-1)
    df["target_soh_percent"] = df["soh_percent"].shift(-1)

    feature_columns = [
        "cycle_number",
        "ambient_temperature_C",
        "discharge_capacity_Ah",
        "soh_percent",
        "previous_capacity_Ah",
        "previous_soh_percent",
        "capacity_change_from_previous_Ah",
    ]

    target_columns = ["target_cycle_number", "target_soh_percent"]

    # Drop rows without lag features or a next-cycle target.
    dataset = df.dropna(
        subset=feature_columns + target_columns
    ).copy()

    # Confirm the target is the immediately following recorded cycle.
    if not (
        dataset["target_cycle_number"]
        == dataset["cycle_number"] + 1
    ).all():
        raise ValueError("Unexpected cycle sequence; inspect source data.")

    # The target columns are kept for evaluation, not used as input features.
    dataset = dataset[
        ["battery_id"] + feature_columns + target_columns
    ]

    if output.exists():
        raise FileExistsError(
            f"Output appeared before writing; refusing to overwrite: {output}"
        )

    with output.open("x", encoding="utf-8", newline="") as file:
        dataset.to_csv(file, index=False)

    print("SUCCESS: Next-cycle target dataset created.")
    print("Output:", output)
    print("Rows:", len(dataset))
    print("Input features:", feature_columns)
    print("Target: target_soh_percent")
    print("Target cycle range:",
          int(dataset["target_cycle_number"].min()),
          "to", int(dataset["target_cycle_number"].max()))
    print("Missing values:", int(dataset.isna().sum().sum()))
    print("\nFirst five rows:")
    print(dataset.head().to_string(index=False))
    print("\nLast three rows:")
    print(dataset.tail(3).to_string(index=False))


if __name__ == "__main__":
    main()
