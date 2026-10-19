
from pathlib import Path

import pandas as pd


def main():
    source = Path(
        "data/processed/nasa_b0005/nasa_b0005_next_cycle_target.csv"
    )
    output = Path(
        "data/processed/nasa_b0005/nasa_b0005_train_test_split.csv"
    )

    if not source.is_file():
        raise FileNotFoundError(f"Source not found: {source}")

    if output.exists():
        raise FileExistsError(
            f"Output already exists; refusing to overwrite: {output}"
        )

    df = pd.read_csv(source).sort_values("cycle_number").reset_index(drop=True)

    if len(df) < 10:
        raise ValueError("Not enough rows for a reliable train/test split.")

    # Keep the timeline in order: earlier observations train the model.
    split_index = int(len(df) * 0.80)
    df["dataset_split"] = "train"
    df.loc[split_index:, "dataset_split"] = "test"

    train = df[df["dataset_split"] == "train"]
    test = df[df["dataset_split"] == "test"]

    # Confirm that training targets end before test targets begin.
    if train["target_cycle_number"].max() >= test["target_cycle_number"].min():
        raise ValueError("Training and test target periods overlap.")

    with output.open("x", encoding="utf-8", newline="") as file:
        df.to_csv(file, index=False)

    print("SUCCESS: Chronological split created.")
    print("Output:", output)
    print("Total rows:", len(df))
    print(f"Training rows: {len(train)} (first 80%)")
    print(f"Testing rows: {len(test)} (last 20%)")
    print(
        "Training target cycles:",
        int(train["target_cycle_number"].min()),
        "to",
        int(train["target_cycle_number"].max()),
    )
    print(
        "Testing target cycles:",
        int(test["target_cycle_number"].min()),
        "to",
        int(test["target_cycle_number"].max()),
    )
    print("Missing values:", int(df.isna().sum().sum()))
    print("\nSplit counts:")
    print(df["dataset_split"].value_counts().to_string())


if __name__ == "__main__":
    main()
