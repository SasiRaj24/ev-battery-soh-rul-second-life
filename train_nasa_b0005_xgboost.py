
from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
import xgboost
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor


def main():
    folder = Path("data/processed/nasa_b0005")
    source = folder / "nasa_b0005_train_test_split.csv"

    model_path = folder / "nasa_b0005_xgboost_model.joblib"
    predictions_path = folder / "nasa_b0005_xgboost_predictions.csv"
    metrics_path = folder / "nasa_b0005_xgboost_metrics.json"

    outputs = [model_path, predictions_path, metrics_path]

    if not source.is_file():
        raise FileNotFoundError(f"Dataset not found: {source}")

    conflicts = [str(path) for path in outputs if path.exists()]
    if conflicts:
        raise FileExistsError(
            "Refusing to overwrite existing files:\n" + "\n".join(conflicts)
        )

    df = pd.read_csv(source)

    feature_columns = [
        "cycle_number",
        "ambient_temperature_C",
        "discharge_capacity_Ah",
        "soh_percent",
        "previous_capacity_Ah",
        "previous_soh_percent",
        "capacity_change_from_previous_Ah",
    ]
    target_column = "target_soh_percent"

    required = feature_columns + [target_column, "dataset_split"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if df[required].isna().any().any():
        raise ValueError("Missing values found in model data.")

    train = df[df["dataset_split"] == "train"].copy()
    test = df[df["dataset_split"] == "test"].copy()

    if train.empty or test.empty:
        raise ValueError("Training or test set is empty.")

    X_train = train[feature_columns]
    y_train = train[target_column]
    X_test = test[feature_columns]
    y_test = test[target_column]

    model = XGBRegressor(
        objective="reg:squarederror",
        n_estimators=200,
        max_depth=3,
        learning_rate=0.03,
        subsample=0.9,
        colsample_bytree=1.0,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=1,
    )

    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    mae = float(mean_absolute_error(y_test, predictions))
    rmse = float(np.sqrt(mean_squared_error(y_test, predictions)))
    r2 = float(r2_score(y_test, predictions))

    results = test[
        ["battery_id", "cycle_number", "target_cycle_number", target_column]
    ].copy()
    results = results.rename(columns={target_column: "actual_soh_percent"})
    results["predicted_soh_percent"] = predictions
    results["absolute_error_percentage_points"] = np.abs(
        results["actual_soh_percent"] - results["predicted_soh_percent"]
    )

    metrics = {
        "model": "XGBRegressor",
        "xgboost_version": xgboost.__version__,
        "battery_id": "B0005",
        "task": "next_recorded_cycle_SOH_prediction",
        "training_rows": int(len(train)),
        "testing_rows": int(len(test)),
        "features": feature_columns,
        "target": target_column,
        "mae_percentage_points": mae,
        "rmse_percentage_points": rmse,
        "r2": r2,
        "note": (
            "Single-battery chronological test. Results do not establish "
            "generalization to other EV batteries."
        ),
    }

    # Refuse overwrites even if a destination appears during execution.
    conflicts = [str(path) for path in outputs if path.exists()]
    if conflicts:
        raise FileExistsError(
            "Output appeared before saving; refusing to overwrite:\n"
            + "\n".join(conflicts)
        )

    # Use exclusive creation for each output.
    with model_path.open("xb") as file:
        joblib.dump(model, file)

    try:
        with predictions_path.open("x", encoding="utf-8", newline="") as file:
            results.to_csv(file, index=False)

        with metrics_path.open("x", encoding="utf-8") as file:
            json.dump(metrics, file, indent=2)

    except Exception:
        # Preserve any file already created; never delete automatically.
        print("WARNING: A save failed. Existing outputs were preserved.")
        raise

    print("SUCCESS: XGBoost baseline trained.")
    print("XGBoost version:", xgboost.__version__)
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
