
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    folder = Path("data/processed/nasa_b0005")

    split_file = folder / "nasa_b0005_train_test_split.csv"
    linear_file = folder / "nasa_b0005_linear_predictions.csv"
    xgb_file = folder / "nasa_b0005_xgboost_predictions.csv"

    output_file = folder / "nasa_b0005_trend_comparison.csv"
    metrics_file = folder / "nasa_b0005_trend_metrics.txt"

    required = [split_file, linear_file, xgb_file]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {path}")

    # Never overwrite existing outputs.
    conflicts = [str(p) for p in [output_file, metrics_file] if p.exists()]
    if conflicts:
        raise FileExistsError(
            "Refusing to overwrite existing files:\n" + "\n".join(conflicts)
        )

    split = pd.read_csv(split_file)
    linear = pd.read_csv(linear_file)
    xgb = pd.read_csv(xgb_file)

    test = (
        split[split["dataset_split"] == "test"]
        .sort_values("target_cycle_number")
        .reset_index(drop=True)
    )

    # Persistence predicts next-cycle SOH as current measured SOH.
    result = test[
        ["cycle_number", "target_cycle_number", "target_soh_percent", "soh_percent"]
    ].rename(
        columns={
            "target_soh_percent": "actual_soh_percent",
            "soh_percent": "persistence_prediction_percent",
        }
    )

    # One-step trend extrapolation:
    # current SOH + (current SOH - previous measured SOH).
    # This uses only current and previous measurements.
    result["trend_prediction_percent"] = (
        test["soh_percent"].to_numpy()
        + (
            test["soh_percent"].to_numpy()
            - test["previous_soh_percent"].to_numpy()
        )
    )

    result = result.merge(
        linear[
            ["target_cycle_number", "predicted_soh_percent"]
        ].rename(
            columns={"predicted_soh_percent": "linear_prediction_percent"}
        ),
        on="target_cycle_number",
        how="left",
        validate="one_to_one",
    )

    result = result.merge(
        xgb[
            ["target_cycle_number", "predicted_soh_percent"]
        ].rename(
            columns={"predicted_soh_percent": "xgboost_prediction_percent"}
        ),
        on="target_cycle_number",
        how="left",
        validate="one_to_one",
    )

    if result.isna().any().any():
        raise ValueError("Missing values found in comparison data.")

    prediction_columns = [
        "persistence_prediction_percent",
        "trend_prediction_percent",
        "linear_prediction_percent",
        "xgboost_prediction_percent",
    ]

    lines = [
        "NASA B0005 next-cycle SOH prediction comparison",
        f"Test samples: {len(result)}",
        "",
        "MAE and RMSE are in SOH percentage points.",
        "Lower MAE/RMSE is better.",
        "",
    ]

    for column in prediction_columns:
        errors = (
            result["actual_soh_percent"].to_numpy()
            - result[column].to_numpy()
        )
        mae = np.mean(np.abs(errors))
        rmse = np.sqrt(np.mean(errors ** 2))
        lines.append(
            f"{column}: MAE={mae:.4f}, RMSE={rmse:.4f}"
        )

    # Exclusive creation protects existing files.
    with output_file.open("x", encoding="utf-8", newline="") as file:
        result.to_csv(file, index=False)

    with metrics_file.open("x", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")

    print("SUCCESS: Trend comparison created.")
    print("CSV:", output_file)
    print("Metrics:", metrics_file)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
