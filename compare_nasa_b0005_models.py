
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def main():
    folder = Path("data/processed/nasa_b0005")

    source = folder / "nasa_b0005_train_test_split.csv"
    xgb_file = folder / "nasa_b0005_xgboost_predictions.csv"
    linear_file = folder / "nasa_b0005_linear_predictions.csv"

    csv_output = folder / "nasa_b0005_model_comparison.csv"
    plot_output = folder / "nasa_b0005_model_comparison.png"

    outputs = [csv_output, plot_output]

    for path in [source, xgb_file, linear_file]:
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {path}")

    conflicts = [str(p) for p in outputs if p.exists()]
    if conflicts:
        raise FileExistsError(
            "Refusing to overwrite existing files:\n" + "\n".join(conflicts)
        )

    split = pd.read_csv(source)
    test = (
        split[split["dataset_split"] == "test"]
        .sort_values("target_cycle_number")
        .reset_index(drop=True)
    )

    xgb = pd.read_csv(xgb_file)
    linear = pd.read_csv(linear_file)

    # Merge by target cycle to avoid relying on row order.
    comparison = test[
        ["target_cycle_number", "target_soh_percent", "soh_percent"]
    ].rename(
        columns={
            "target_soh_percent": "actual_soh_percent",
            "soh_percent": "persistence_prediction_percent",
        }
    )

    comparison = comparison.merge(
        xgb[["target_cycle_number", "predicted_soh_percent"]].rename(
            columns={"predicted_soh_percent": "xgboost_prediction_percent"}
        ),
        on="target_cycle_number",
        how="left",
        validate="one_to_one",
    )

    comparison = comparison.merge(
        linear[["target_cycle_number", "predicted_soh_percent"]].rename(
            columns={"predicted_soh_percent": "linear_prediction_percent"}
        ),
        on="target_cycle_number",
        how="left",
        validate="one_to_one",
    )

    if comparison.isna().any().any():
        raise ValueError("Missing values after merging model predictions.")

    # Check filenames again before creating outputs.
    conflicts = [str(p) for p in outputs if p.exists()]
    if conflicts:
        raise FileExistsError(
            "Output appeared before writing; refusing to overwrite:\n"
            + "\n".join(conflicts)
        )

    with csv_output.open("x", encoding="utf-8", newline="") as file:
        comparison.to_csv(file, index=False)

    try:
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.plot(
            comparison["target_cycle_number"],
            comparison["actual_soh_percent"],
            label="Actual SOH",
            linewidth=2,
        )
        ax.plot(
            comparison["target_cycle_number"],
            comparison["persistence_prediction_percent"],
            label="Persistence baseline",
        )
        ax.plot(
            comparison["target_cycle_number"],
            comparison["linear_prediction_percent"],
            label="Linear regression",
        )
        ax.plot(
            comparison["target_cycle_number"],
            comparison["xgboost_prediction_percent"],
            label="XGBoost",
        )

        ax.set_title("NASA B0005: Next-Cycle SOH Prediction")
        ax.set_xlabel("Target cycle number")
        ax.set_ylabel("SOH (%)")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()

        # Exclusive creation prevents replacing an existing graph.
        with plot_output.open("xb") as file:
            fig.savefig(file, format="png", dpi=160)
        plt.close(fig)

    except Exception:
        print(
            "WARNING: Graph creation failed. Any already-created output "
            "has been preserved."
        )
        raise

    print("SUCCESS: Model comparison created.")
    print("CSV:", csv_output)
    print("Graph:", plot_output)
    print("\nFirst five comparison rows:")
    print(comparison.head().to_string(index=False))


if __name__ == "__main__":
    main()
