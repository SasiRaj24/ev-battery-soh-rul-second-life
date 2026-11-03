"""Application services for versioned experimental NASA-cell models."""

from __future__ import annotations

import json
import hashlib
import os
import copy
from functools import lru_cache
from io import StringIO
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models"
DEFAULT_MANIFEST_PATH = MODEL_DIR / "releases" / "4.0.0-multisource-experimental" / "manifest.json"
SOH_SUMMARY_PATH = ROOT / "data" / "processed" / "nasa_cross_battery_v1" / "nasa_cross_battery_v1_summary.json"
SOH_ADDENDUM_PATH = ROOT / "data" / "processed" / "nasa_cross_battery_v1" / "nasa_cross_battery_v1_quality_addendum.json"
RUL_SUMMARY_PATH = ROOT / "data" / "processed" / "nasa_rul_v2" / "nasa_rul_v2_summary.json"
RUL_FOLDS_PATH = ROOT / "data" / "processed" / "nasa_rul_v2" / "nasa_rul_v2_fold_metrics.csv"
RUL_PREDICTIONS_PATH = ROOT / "data" / "processed" / "nasa_rul_v2" / "nasa_rul_v2_predictions.csv"
DATASET_CATALOG_PATH = ROOT / "data" / "processed" / "additional_datasets_v3_3" / "dataset_catalog_v3_3.json"
RESEARCH_EVALUATION_PATH = ROOT / "data" / "processed" / "research_evaluation_v4" / "evaluation_summary_v4.json"
SOH_FEATURES = [
    "cycle_number", "ambient_temperature_C", "soh_percent",
    "previous_soh_percent", "capacity_change_from_previous_Ah",
]
RUL_FEATURES = [
    "cycle_number", "ambient_temperature_C", "discharge_capacity_Ah",
    "soh_percent", "previous_soh_percent", "capacity_change_from_previous_Ah",
]
EOL_AH = 1.4
MAX_CSV_BYTES = 2_000_000
MAX_ROWS = 10_000

_soh_model = None
_rul_model = None
_loaded_model_paths: tuple[Path, Path] | None = None
_source_soh_models: dict[str, tuple[Path, object]] = {}


@lru_cache(maxsize=64)
def _read_json_cached(path_text: str, modified_ns: int, size: int) -> dict:
    return json.loads(Path(path_text).read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def _read_csv_cached(path_text: str, modified_ns: int, size: int) -> pd.DataFrame:
    return pd.read_csv(path_text)


def _json_file(path: Path, message: str) -> dict:
    try:
        stat = path.stat()
        value = _read_json_cached(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
        return copy.deepcopy(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail=message) from exc


def _csv_file(path: Path, message: str) -> pd.DataFrame:
    try:
        stat = path.stat()
        return _read_csv_cached(str(path.resolve()), stat.st_mtime_ns, stat.st_size).copy(deep=True)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise HTTPException(status_code=503, detail=message) from exc


def model_manifest() -> dict:
    configured = os.environ.get("EV_BATTERY_MODEL_MANIFEST")
    manifest_path = Path(configured) if configured else DEFAULT_MANIFEST_PATH
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    manifest_path = manifest_path.resolve()
    try:
        manifest_path.relative_to(MODEL_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Configured model manifest must be inside the models directory") from exc
    return _json_file(manifest_path, "Versioned model manifest is unavailable")


def _active_manifest_path() -> Path:
    configured = os.environ.get("EV_BATTERY_MODEL_MANIFEST")
    path = Path(configured) if configured else DEFAULT_MANIFEST_PATH
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _active_model_paths() -> tuple[Path, Path]:
    manifest = model_manifest()
    manifest_path = _active_manifest_path()
    try:
        soh_path = (manifest_path.parent / manifest["models"]["next_cycle_soh"]["artifact"]).resolve()
        rul_path = (manifest_path.parent / manifest["models"]["rul"]["artifact"]).resolve()
        soh_path.relative_to(MODEL_DIR.resolve())
        rul_path.relative_to(MODEL_DIR.resolve())
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Model manifest has invalid artifact paths") from exc
    return soh_path, rul_path


def dataset_catalog() -> dict:
    return _json_file(DATASET_CATALOG_PATH, "Expanded local dataset catalog is unavailable")


def models_ready() -> bool:
    try:
        soh_path, rul_path = _active_model_paths()
        manifest = model_manifest()
        source_paths = [
            ( _active_manifest_path().parent / entry["artifact"]).resolve()
            for entry in manifest.get("source_models", {}).values()
        ]
        support_paths = (
            [_active_manifest_path().parent / "feature_support_v1.json", _active_manifest_path().parent / "output_support_v1.json"]
            if manifest.get("source_models") else []
        )
        return all(path.is_file() for path in (soh_path, rul_path, *source_paths, *support_paths))
    except HTTPException:
        return False


def load_models():
    global _soh_model, _rul_model, _loaded_model_paths
    if not models_ready():
        raise HTTPException(status_code=503, detail="Versioned model artifacts are unavailable")
    soh_path, rul_path = _active_model_paths()
    active_paths = (soh_path, rul_path)
    if _loaded_model_paths != active_paths:
        try:
            if not soh_path.is_file() or not rul_path.is_file():
                raise HTTPException(status_code=503, detail="Versioned model artifacts are unavailable")
            manifest = model_manifest()
            entries = (manifest["models"]["next_cycle_soh"], manifest["models"]["rul"])
            for path, entry in zip(active_paths, entries):
                expected_hash = entry.get("sha256")
                if expected_hash:
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    if digest.lower() != str(expected_hash).lower():
                        raise HTTPException(status_code=503, detail=f"Model artifact hash mismatch: {path.name}")
            # Publish the pair only after both artifacts pass validation and load.
            soh_model = joblib.load(soh_path)
            rul_model = joblib.load(rul_path)
            _soh_model, _rul_model = soh_model, rul_model
            _loaded_model_paths = active_paths
        except (OSError, ValueError, EOFError) as exc:
            raise HTTPException(status_code=503, detail="Versioned model artifacts could not be loaded") from exc
    return _soh_model, _rul_model


def load_source_soh_model(source: str):
    if source not in {"Oxford", "CALCE_CS2"}:
        raise HTTPException(status_code=422, detail="Choose NASA, Oxford, or CALCE CS2 as the analysis source")
    manifest = model_manifest()
    manifest_path = _active_manifest_path()
    try:
        entry = manifest["source_models"][source]
        model_path = (manifest_path.parent / entry["artifact"]).resolve()
        model_path.relative_to(MODEL_DIR.resolve())
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"No versioned SOH model is registered for {source}") from exc
    cached = _source_soh_models.get(source)
    if cached and cached[0] == model_path:
        return cached[1], entry
    if not model_path.is_file():
        raise HTTPException(status_code=503, detail=f"SOH model artifact is unavailable for {source}")
    expected_hash = entry.get("sha256")
    if expected_hash:
        digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if digest.lower() != str(expected_hash).lower():
            raise HTTPException(status_code=503, detail=f"Model artifact hash mismatch for {source}")
    try:
        model = joblib.load(model_path)
    except (OSError, ValueError, EOFError) as exc:
        raise HTTPException(status_code=503, detail=f"SOH model could not be loaded for {source}") from exc
    _source_soh_models[source] = (model_path, model)
    return model, entry


def soh_validation() -> dict:
    summary = _json_file(SOH_SUMMARY_PATH, "SOH validation summary is unavailable")
    if SOH_ADDENDUM_PATH.is_file():
        correction = _json_file(SOH_ADDENDUM_PATH, "SOH summary correction is unavailable")
        for battery, count in correction["valid_discharge_records_by_battery"].items():
            summary["battery_data_summary"][battery]["valid_discharge_records"] = count
        for battery, capacity in correction["first_discharge_capacity_Ah_by_battery"].items():
            summary["battery_data_summary"][battery]["first_discharge_capacity_Ah"] = capacity
        for battery, maximum in correction["relative_soh_max_percent_by_battery"].items():
            summary["battery_data_summary"][battery]["relative_soh_max_percent"] = maximum
        summary["quality_addendum"] = correction["note"]
    return summary


def rul_validation() -> dict:
    summary = _json_file(RUL_SUMMARY_PATH, "RUL validation summary is unavailable")
    summary["pooled_metrics_cycles"] = {
        name: value
        for name, value in summary["pooled_metrics_cycles"].items()
        if name != "cycle_index_oracle_control"
    }
    if not RUL_FOLDS_PATH.is_file() or not RUL_PREDICTIONS_PATH.is_file():
        raise HTTPException(status_code=503, detail="RUL validation detail files are unavailable")
    folds = _csv_file(RUL_FOLDS_PATH, "RUL validation fold metrics could not be read")
    folds = folds[folds["model"] != "cycle_index_oracle_control"]
    summary["fold_metrics"] = folds.to_dict(orient="records")
    return summary


def research_evaluation() -> dict:
    """Return cell-macro evidence and observed held-cell spread from v4."""
    return _json_file(RESEARCH_EVALUATION_PATH, "Cell-level research evaluation summary is unavailable")


def parse_history_csv(raw: bytes) -> pd.DataFrame:
    if not raw:
        raise HTTPException(status_code=400, detail="Upload a CSV with discharge history")
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail=f"CSV exceeds {MAX_CSV_BYTES} bytes")
    try:
        text = raw.decode("utf-8-sig")
        frame = pd.read_csv(StringIO(text))
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise HTTPException(status_code=400, detail="Could not parse the uploaded CSV") from exc
    required = {"cycle_number", "discharge_capacity_Ah", "ambient_temperature_C"}
    missing = required - set(frame.columns)
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "CSV is missing required columns",
                "required_columns": sorted(required),
                "missing_columns": sorted(missing),
            },
        )
    if not 2 <= len(frame) <= MAX_ROWS:
        raise HTTPException(status_code=422, detail=f"CSV must contain 2 to {MAX_ROWS} discharge rows")
    frame = frame[["cycle_number", "discharge_capacity_Ah", "ambient_temperature_C"]].copy()
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise HTTPException(status_code=422, detail="CSV values must be numeric and finite")
    if (frame["discharge_capacity_Ah"] <= 0).any():
        raise HTTPException(status_code=422, detail="Discharge capacities must be positive")
    cycles = frame["cycle_number"].to_numpy(dtype=float)
    if (np.diff(cycles) <= 0).any():
        raise HTTPException(status_code=422, detail="cycle_number must increase strictly")
    if not np.all(cycles == np.floor(cycles)):
        raise HTTPException(status_code=422, detail="cycle_number must contain whole-number cycle indices")
    return frame.reset_index(drop=True)


def engineer_history(frame: pd.DataFrame, reference_capacity_Ah: float | None = None) -> pd.DataFrame:
    result = frame.copy()
    baseline = float(reference_capacity_Ah) if reference_capacity_Ah is not None else float(result["discharge_capacity_Ah"].iloc[0])
    if not np.isfinite(baseline) or baseline <= 0:
        raise HTTPException(status_code=422, detail="Reference capacity must be a positive finite value")
    result["soh_percent"] = result["discharge_capacity_Ah"] / baseline * 100.0
    result["previous_soh_percent"] = result["soh_percent"].shift(1)
    result["capacity_change_from_previous_Ah"] = result["discharge_capacity_Ah"].diff()
    return result


def _second_life_screen(current_soh: float) -> dict:
    if current_soh >= 80.0:
        code = "continued_use_or_second_life_assessment"
        category = "Higher retained capacity: review continued first-life use or second-life options."
        rationale = "Relative SOH is at least the project's 80% screening assumption."
    elif current_soh >= 70.0:
        code = "second_life_assessment_candidate"
        category = "Candidate for engineering assessment for a lower-demand use."
        rationale = "Relative SOH is between the project's 70% and 80% screening assumptions."
    else:
        code = "recycling_or_reengineering_review"
        category = "Prioritize recycling or detailed re-engineering review."
        rationale = "Relative SOH is below the project's 70% screening assumption."
    return {
        "category_code": code,
        "category": category,
        "decision_status": "engineering_assessment_required",
        "application_recommendation": None,
        "rationale": rationale,
        "thresholds_are_project_assumptions": True,
        "confidence": "low; capacity-only screen",
        "not_a_safety_or_certification_decision": True,
        "not_measured_by_current_inputs": [
            "Power capability under the intended duty cycle",
            "DC resistance or impedance",
            "Thermal behavior and protection response",
            "Physical condition and electrical isolation",
            "Cell matching, BMS compatibility, and pack integration",
        ],
        "required_follow_up": [
            "Independent capacity and power-capability test under the intended duty cycle",
            "DC resistance or impedance assessment",
            "Physical condition and electrical-isolation inspection",
            "Thermal characterization and protection checks under intended operation",
            "Cell-to-cell matching, BMS compatibility, and pack-level engineering review",
        ],
    }


def analyze_history(
    frame: pd.DataFrame,
    reference_capacity_Ah: float | None = None,
    input_mode: str = "csv_history",
    compatible_with_nasa_rul_scope: bool = False,
) -> dict:
    soh_model, rul_model = load_models()
    manifest = model_manifest()
    rul_eol_capacity = float(manifest.get("models", {}).get("rul", {}).get("rul_eol_capacity_Ah", EOL_AH))
    featured = engineer_history(frame, reference_capacity_Ah)
    current = featured.iloc[-1]
    soh_input = featured.iloc[[-1]][SOH_FEATURES]
    predicted_soh = float(soh_model.predict(soh_input)[0])
    persistence_soh = float(current["soh_percent"])
    coefficients = np.asarray(soh_model.coef_, dtype=float)
    contributions = [
        {
            "feature": name,
            "value": float(current[name]),
            "coefficient": float(coefficient),
            "additive_model_term_percentage_points": float(current[name] * coefficient),
        }
        for name, coefficient in zip(SOH_FEATURES, coefficients)
    ]
    contributions.sort(
        key=lambda item: abs(item["additive_model_term_percentage_points"]),
        reverse=True,
    )
    explanation = {
        "model": "LinearRegression",
        "intercept": float(soh_model.intercept_),
        "feature_terms": contributions,
        "interpretation": "Terms add with the intercept to produce the estimate. This is an exact linear-model decomposition, not a causal explanation.",
        "persistence_comparator_percent": persistence_soh,
        "model_minus_persistence_percentage_points": predicted_soh - persistence_soh,
    }

    rul_input = featured.iloc[[-1]][RUL_FEATURES]
    current_capacity = float(current["discharge_capacity_Ah"])
    if not compatible_with_nasa_rul_scope:
        rul_estimate = None
        rul_status = "not_estimated_protocol_unconfirmed"
    elif current_capacity <= rul_eol_capacity:
        rul_estimate = 0.0
        rul_status = "dataset_eol_threshold_reached"
    else:
        rul_estimate = max(0.0, float(rul_model.predict(rul_input)[0]))
        rul_status = "experimental_model_estimate"
    importances = getattr(rul_model, "feature_importances_", np.zeros(len(RUL_FEATURES)))
    ranked_importance = sorted(
        [
            {"feature": name, "training_feature_importance": float(value)}
            for name, value in zip(RUL_FEATURES, importances)
        ],
        key=lambda item: item["training_feature_importance"],
        reverse=True,
    )
    current_soh = float(current["soh_percent"])
    history_chart = [
        {
            "cycle": float(row.cycle_number),
            "measured_soh_percent": float(row.soh_percent),
            "predicted_next_soh_percent": None,
        }
        for row in featured.itertuples(index=False)
    ]
    history_chart.append({
        "cycle": float(current["cycle_number"]) + 1.0,
        "measured_soh_percent": None,
        "predicted_next_soh_percent": predicted_soh,
    })
    return {
        "model_version": manifest.get("models", {}).get("next_cycle_soh", {}).get(
            "artifact_model_version", manifest.get("model_version", "unknown")
        ),
        "model_release": manifest.get("model_version", "unknown"),
        "battery_id": "manual_parameters" if input_mode == "manual_parameters" else "uploaded_history",
        "input_mode": input_mode,
        "observed_discharge_records": int(len(featured)),
        "current_cycle_number": float(current["cycle_number"]),
        "current_capacity_Ah": current_capacity,
        "relative_soh_percent": current_soh,
        "soh_reference_capacity_Ah": float(reference_capacity_Ah) if reference_capacity_Ah is not None else float(featured["discharge_capacity_Ah"].iloc[0]),
        "history_chart": history_chart,
        "next_discharge_soh": {
            "predicted_soh_percent": predicted_soh,
            "task": "one-step prediction of next recorded discharge",
            "explanation": explanation,
            "validation_context": "LOBO linear MAE 0.5924 SOH points; persistence comparator MAE 0.5574.",
        },
        "remaining_useful_life": {
            "estimated_remaining_discharge_cycles": round(rul_estimate, 1) if rul_estimate is not None else None,
            "status": rul_status,
            "eol_definition": f"first measured discharge capacity <= {rul_eol_capacity} Ah",
            "confidence": "low; three complete NASA cells in held-out validation",
            "prediction_interval": None,
            "feature_importance_global_not_local": ranked_importance,
            "limitations": [
                "RUL is tied to this dataset's 1.4 Ah threshold and discharge protocol.",
                "The RUL model was trained on only B0005, B0006, and B0018; B0007 did not cross the threshold and was right-censored.",
                "RUL is withheld unless the caller confirms a compatible NASA-like single-cell protocol and the same 1.4 Ah endpoint.",
                "Entered or uploaded data must use compatible cell chemistry and test conditions for even exploratory interpretation.",
            ],
        },
        "second_life_screening": _second_life_screen(current_soh),
        "scope": "Research estimates from NASA laboratory-cell data; not EV pack validation, a safety test, or an application certification.",
    }


def analyze_parameters(values: dict) -> dict:
    """Run the existing models from two typed measurements and a stated SOH reference."""
    source = str(values.get("dataset_source", "NASA"))
    previous_cycle = int(values["previous_cycle_number"])
    current_cycle = int(values["current_cycle_number"])
    if previous_cycle < 0 or current_cycle <= previous_cycle or (source == "NASA" and previous_cycle < 1):
        raise HTTPException(status_code=422, detail="Cycle numbers must increase; NASA inputs start at cycle 1, Oxford may start at cycle 0")
    reference = float(values["reference_capacity_Ah"])
    previous_capacity = float(values["previous_capacity_Ah"])
    current_capacity = float(values["current_capacity_Ah"])
    temperature = float(values.get("ambient_temperature_C", 25.0))
    numeric = np.asarray([reference, previous_capacity, current_capacity, temperature], dtype=float)
    if not np.isfinite(numeric).all() or min(reference, previous_capacity, current_capacity) <= 0:
        raise HTTPException(status_code=422, detail="Capacity values must be positive and all values finite")
    frame = pd.DataFrame([
        {"cycle_number": previous_cycle, "discharge_capacity_Ah": previous_capacity, "ambient_temperature_C": temperature},
        {"cycle_number": current_cycle, "discharge_capacity_Ah": current_capacity, "ambient_temperature_C": temperature},
    ])
    if source in {"Oxford", "CALCE_CS2"}:
        forecast_cycle = values.get("forecast_cycle_number")
        if source == "Oxford" and forecast_cycle is None:
            raise HTTPException(status_code=422, detail="Enter the next scheduled Oxford measurement cycle")
        forecast_cycle = int(forecast_cycle) if forecast_cycle is not None else current_cycle + 1
        if forecast_cycle <= current_cycle:
            raise HTTPException(status_code=422, detail="Next scheduled measurement cycle must be greater than the current cycle")
        return analyze_harmonized_parameters(
            source, previous_cycle, previous_capacity, current_cycle,
            current_capacity, reference, forecast_cycle,
        )
    if source != "NASA":
        raise HTTPException(status_code=422, detail="Choose NASA, Oxford, or CALCE CS2 as the analysis source")
    return analyze_history(
        frame,
        reference_capacity_Ah=reference,
        input_mode="manual_parameters",
        compatible_with_nasa_rul_scope=bool(values.get("compatible_with_nasa_rul_scope", False)),
    )


def analyze_collective_parameters(values: dict) -> dict:
    """Cross-dataset informed capacity assessment; avoids an unsupported pooled model."""
    previous_cycle = int(values["previous_cycle_number"])
    current_cycle = int(values["current_cycle_number"])
    if previous_cycle < 0 or current_cycle <= previous_cycle:
        raise HTTPException(status_code=422, detail="Cycle numbers must increase")
    reference = float(values["reference_capacity_Ah"])
    previous_capacity = float(values["previous_capacity_Ah"])
    current_capacity = float(values["current_capacity_Ah"])
    numeric = np.asarray([reference, previous_capacity, current_capacity], dtype=float)
    if not np.isfinite(numeric).all() or min(reference, previous_capacity, current_capacity) <= 0:
        raise HTTPException(status_code=422, detail="Capacity values must be positive and finite")
    forecast_cycle = values.get("forecast_cycle_number")
    forecast_cycle = int(forecast_cycle) if forecast_cycle is not None else current_cycle + (current_cycle - previous_cycle)
    if forecast_cycle <= current_cycle:
        raise HTTPException(status_code=422, detail="Forecast cycle must be after the current cycle")

    current_soh = current_capacity / reference * 100.0
    previous_soh = previous_capacity / reference * 100.0
    # A two-point linear extrapolation is a transparent baseline, not a trained model.
    rate_per_cycle = (current_soh - previous_soh) / (current_cycle - previous_cycle)
    forecast_soh = float(np.clip(current_soh + rate_per_cycle * (forecast_cycle - current_cycle), 0.0, 150.0))
    screen = _second_life_screen(current_soh)
    return {
        "analysis_mode": "collective_dataset_evidence_capacity_baseline",
        "model_version": "collective-baseline-v1",
        "model_release": "collective-baseline-v1",
        "input_mode": "manual_parameters",
        "dataset_sources_considered": ["NASA PCoE", "Oxford Battery Degradation Dataset 1", "CALCE CS2"],
        "independent_cells_in_source_specific_evaluation": 26,
        "current_cycle_number": float(current_cycle),
        "forecast_cycle_number": float(forecast_cycle),
        "current_capacity_Ah": current_capacity,
        "soh_reference_capacity_Ah": reference,
        "relative_soh_percent": float(current_soh),
        "predicted_next_soh_percent": forecast_soh,
        "condition": {
            "status": "capacity_based_research_estimate",
            "interpretation": "Relative SOH is computed from the entered capacity and reference capacity; projected SOH extends the two latest measurements linearly.",
            "trend_percentage_points_per_cycle": float(rate_per_cycle),
        },
        "history_chart": [
            {"cycle": float(previous_cycle), "measured_soh_percent": float(previous_soh), "predicted_next_soh_percent": None},
            {"cycle": float(current_cycle), "measured_soh_percent": float(current_soh), "predicted_next_soh_percent": None},
            {"cycle": float(forecast_cycle), "measured_soh_percent": None, "predicted_next_soh_percent": forecast_soh},
        ],
        "second_life_screening": screen,
        "rul_status": "withheld_not_supported_by_collective_cross_dataset_evidence",
        "dataset_evidence": [
            {"family": "NASA core", "collective_model_mae_soh_pp": 0.5008, "within_family_model_mae_soh_pp": 0.4846, "interpretation": "Pooling was slightly worse than family-specific XGBoost."},
            {"family": "NASA B0025–B0028", "collective_model_mae_soh_pp": 1.0509, "within_family_model_mae_soh_pp": 1.0547, "interpretation": "Exploratory scores are close; four held-out cells and no confidence interval."},
            {"family": "NASA B0029–B0032", "collective_model_mae_soh_pp": 0.6588, "within_family_model_mae_soh_pp": 0.5856, "interpretation": "Pooling was worse than the within-family XGBoost result."},
            {"family": "Oxford", "collective_model_mae_soh_pp": 7.9506, "within_family_model_mae_soh_pp": 0.2560, "interpretation": "Pooling showed severe negative transfer; family-specific modeling is preferred."},
            {"family": "CALCE CS2", "collective_model_mae_soh_pp": 1.0048, "persistence_mae_soh_pp": 0.9938, "interpretation": "Pooling was effectively tied with persistence and did not establish an improvement."},
        ],
        "validation_context": "Cross-dataset LOBO comparisons use small laboratory-cell cohorts; metrics are measured study results, not EV pack validation.",
        "scope": "Capacity-based cell research estimate informed by NASA, Oxford, and CALCE evidence. The forecast is an unvalidated two-point trend baseline, not a pooled AI model. No EV pack, field, RUL, reuse-safety, or application validation is established.",
    }


def analyze_harmonized_parameters(
    source: str, previous_cycle: int, previous_capacity: float,
    current_cycle: int, current_capacity: float, reference_capacity: float,
    forecast_cycle: int,
) -> dict:
    model, entry = load_source_soh_model(source)
    feature_values = {
        "current_soh_percent": current_capacity / reference_capacity * 100.0,
        "previous_soh_percent": previous_capacity / reference_capacity * 100.0,
        "previous_soh_change_pp_per_100_cycles": (
            (current_capacity - previous_capacity) / reference_capacity * 100.0
            / (current_cycle - previous_cycle) * 100.0
        ),
        "previous_gap_cycles": current_cycle - previous_cycle,
    }
    features = pd.DataFrame([{name: feature_values[name] for name in entry["feature_order"]}])
    predicted_rate = float(model.predict(features)[0])
    current_soh = feature_values["current_soh_percent"]
    raw_prediction = current_soh + predicted_rate * (forecast_cycle - current_cycle) / 100.0
    release_dir = _active_manifest_path().parent
    try:
        output_support = json.loads((release_dir / "output_support_v1.json").read_text(encoding="utf-8"))["by_source"][source]
        feature_support = json.loads((release_dir / "feature_support_v1.json").read_text(encoding="utf-8"))["by_source"][source]["limits"]
        supported_inputs = all(
            feature_support[name]["observed_min"] <= feature_values[name] <= feature_support[name]["observed_max"]
            for name in feature_values
        )
        supported_delta = (
            supported_inputs
            and output_support["lower_q01_soh_pp"] <= raw_prediction - current_soh <= output_support["upper_q99_soh_pp"]
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail=f"Training-range guard is unavailable for {source}") from exc
    prediction = float(np.clip(raw_prediction, 0.0, 100.0)) if supported_delta else None
    validation = entry["validation"]
    persistence_mae = float(validation["persistence_macro_cell_mae_soh_pp"])
    model_mae = float(validation["model_macro_cell_mae_soh_pp"])
    description = {
        "Oxford": "Oxford cell-held-out study: 8 cells; checkpoint spacing is not always identical.",
        "CALCE_CS2": "CALCE CS2 cell-held-out study: 6 cells; results are effectively tied with persistence.",
    }[source]
    explanation_text = (
        "Source-specific experimental model. Feature values and model output are associational, not causal; no calibrated prediction interval is available."
        if supported_delta else
        "The model input or projected next-record SOH change falls outside observed training support, so its estimate is withheld. Persistence is shown as a reference only."
    )
    return {
        "model_version": "4.0.0-multisource-experimental",
        "model_release": "4.0.0-multisource-experimental",
        "battery_id": "manual_parameters",
        "input_mode": "manual_parameters",
        "dataset_source": source,
        "model_name": entry["estimator"],
        "observed_discharge_records": 2,
        "current_cycle_number": float(current_cycle),
        "forecast_cycle_number": float(forecast_cycle),
        "current_capacity_Ah": float(current_capacity),
        "relative_soh_percent": float(current_soh),
        "soh_reference_capacity_Ah": float(reference_capacity),
        "history_chart": [
            {"cycle": float(previous_cycle), "measured_soh_percent": feature_values["previous_soh_percent"], "predicted_next_soh_percent": None},
            {"cycle": float(current_cycle), "measured_soh_percent": float(current_soh), "predicted_next_soh_percent": None},
            {"cycle": float(forecast_cycle), "measured_soh_percent": None, "predicted_next_soh_percent": prediction},
        ],
        "next_discharge_soh": {
            "predicted_soh_percent": prediction,
            "status": "available" if supported_delta else "withheld_outside_observed_training_change_range",
            "task": "prediction of SOH at the next scheduled measurement",
            "explanation": {
                "model": entry["estimator"],
                "feature_values": feature_values,
                "feature_terms": [],
                "interpretation": explanation_text,
                "persistence_comparator_percent": float(current_soh),
                "model_minus_persistence_percentage_points": float(prediction - current_soh) if prediction is not None else None,
            },
            "validation_context": f"{description} Leave-one-cell-out macro-cell MAE {model_mae:.4f} SOH pp; persistence {persistence_mae:.4f} pp.",
            "validation": validation,
            "prediction_interval": None,
        },
        "remaining_useful_life": {
            "estimated_remaining_discharge_cycles": None,
            "status": "not_validated_for_selected_dataset",
            "eol_definition": "No validated RUL endpoint for this source-specific analyzer.",
            "confidence": "withheld",
            "prediction_interval": None,
            "limitations": ["The interactive RUL model remains NASA-specific.", "A laboratory-cell comparison is not EV-pack or second-life safety validation."],
        },
        "second_life_screening": _second_life_screen(current_soh),
        "scope": f"Exploratory {source} laboratory-cell SOH research estimate; no EV-pack, field, or reuse-safety validation is established.",
    }
