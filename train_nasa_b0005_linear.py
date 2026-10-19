
from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def main():
    folder = Path("data/processed/nasa_b0005")
    source = folder / "nasa_b0005_train_test_split.csv"

    model_path = folder / "nasa_b0005_linear_model.joblib"
    predictions_path = folder / "nasa_b0005_linear_predictions.csv"
    metrics_path = folder / "nasa_b0005_linear_metrics.json"
    outputs = [model_path, predictions_path, metrics_path]

    if not source.is_file():
        raise FileNotFoundError(f"Dataset not found: {source}")

    conflicts = [str(p) for p in outputs if p.exists()]
    if conflicts:
        raise FileExistsError(
            "Refusing to overwrite existing files:\n" + "\n".join(conflicts)
        )

    df = pd.read_csv(source).sort_values("cycle_number").reset_index(drop=True)

    features = [
        "cycle_number",
        "soh_percent",
        "previous_soh_percent",
        "capacity_change_from_previous_Ah",
    ]
    target = "target_soh_percent"

    train = df[df["dataset_split"] == "train"].copy()
    test = df[df["dataset_split"] == "test"].copy()

    if train[features + [target]].isna().any().any():
        raise ValueError("Training data contains missing values.")
    if test[features + [target]].isna().any().any():
        raise ValueError("Test data contains missing values.")

    model = LinearRegression()
    model.fit(train[features], train[target])
    predictions = model.predict(test[features])

    actual = test[target].to_numpy()
    mae = float(mean_absolute_error(actual, predictions))
    rmse = float(np.sqrt(mean_squared_error(actual, predictions)))
    r2 = float(r2_score(actual, predictions))

    results = test[
        ["battery_id", "cycle_number", "target_cycle_number", target]
    ].copy()
    results.rename(
        columns={target: "actual_soh_percent"}, inplace=True
    )
    results["predicted_soh_percent"] = predictions
    results["absolute_error_percentage_points"] = np.abs(
        results["actual_soh_percent"] - results["predicted_soh_percent"]
    )

    metrics = {
        "model": "LinearRegression",
        "battery_id": "B0005",
        "task": "next_recorded_cycle_SOH_prediction",
        "training_rows": int(len(train)),
        "testing_rows": int(len(test)),
        "features": features,
        "target": target,
        "mae_percentage_points": mae,
        "rmse_percentage_points": rmse,
        "r2": r2,
        "note": (
            "Single-battery chronological test; compare against persistence "
            "and XGBoost. Does not establish cross-battery generalization."
        ),
    }

    # Recheck all destinations before saving.
    conflicts = [str(p) for p in outputs if p.exists()]
    if conflicts:
        raise FileExistsError(
            "Refusing to overwrite existing files:\n" + "\n".join(conflicts)
        )

    with model_path.open("xb") as file:
        joblib.dump(model, file)

    with predictions_path.open("x", encoding="utf-8", newline="") as file:
        results.to_csv(file, index=False)

    with metrics_path.open("x", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)

    print("SUCCESS: Linear regression trained.")
    print("Training rows:", len(train))
    print("Testing rows:", len(test))
    print(f"MAE:  {mae:.4f} SOH percentage points")
    print(f"RMSE: {rmse:.4f} SOH percentage points")
    print(f"R2:   {r2:.4f}")
    print("\nSaved files:")
    for path in outputs:
        print(path)
    print("\nFirst five test predictions:")
    print(results.head().to_string(index=False))


if __name__ == "__main__":
    main()
