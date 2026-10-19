
from pathlib import Path

import pandas as pd


def main():
    source = Path(
        "data/processed/nasa_b0005/nasa_b0005_discharge_cycles.csv"
    )
    output = Path(
        "data/processed/nasa_b0005/nasa_b0005_ml_features.csv"
    )

    # Never overwrite an existing file.
    if not source.is_file():
        raise FileNotFoundError(f"Source not found: {source}")

    if output.exists():
        raise FileExistsError(
            f"Output already exists; refusing to overwrite: {output}"
        )

    df = pd.read_csv(source).sort_values("cycle_number").reset_index(drop=True)

    required = {
        "cycle_number",
        "ambient_temperature_C",
        "discharge_capacity_Ah",
        "soh_percent",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Required columns missing: {sorted(missing)}")

    # Features use only information from the current or earlier cycles.
    df["previous_capacity_Ah"] = (
        df["discharge_capacity_Ah"].shift(1)
    )
    df["previous_soh_percent"] = df["soh_percent"].shift(1)
    df["capacity_change_from_previous_Ah"] = (
        df["discharge_capacity_Ah"].diff()
    )

    # Explicitly identify rows without prior-cycle information.
    df["has_previous_cycle"] = df["previous_capacity_Ah"].notna()

    # Keep all 168 observations; the first row's lag features are missing
    # because no previous cycle exists.
    if output.exists():
        raise FileExistsError(
            f"Output appeared before writing; refusing to overwrite: {output}"
        )

    with output.open("x", encoding="utf-8", newline="") as file:
        df.to_csv(file, index=False)

    print("SUCCESS: Feature dataset created.")
    print("Output:", output)
    print("Rows:", len(df))
    print("Columns:", df.columns.tolist())
    print("Rows with previous-cycle features:",
          int(df["has_previous_cycle"].sum()))
    print("Missing values by column:")
    print(df.isna().sum().to_string())
    print("\nFirst five rows:")
    print(df.head().to_string(index=False))


if __name__ == "__main__":
    main()
