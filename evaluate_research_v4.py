"""Build a cell-level, protocol-aware evaluation addendum without changing prior outputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from validate_additional_datasets_v3 import validate_soh


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "processed" / "research_evaluation_v4"
REPORT = ROOT / "reports" / "research_evaluation_v4_report.md"


def summarize_by_cell(frame: pd.DataFrame, cell_col: str, model_col: str, error_col: str) -> dict:
    by_cell = frame.groupby([model_col, cell_col], as_index=False)[error_col].mean()
    result = {}
    for model, group in by_cell.groupby(model_col, sort=True):
        values = group[error_col].astype(float)
        result[str(model)] = {
            "macro_cell_mae": float(values.mean()),
            "minimum_cell_mae": float(values.min()),
            "maximum_cell_mae": float(values.max()),
            "held_out_cells": int(group[cell_col].nunique()),
            "observed_cell_maes": {
                str(row[cell_col]): float(row[error_col])
                for _, row in group.sort_values(cell_col).iterrows()
            },
            "uncertainty_note": "Observed held-out-cell spread only; too few independent cells for a dependable inferential interval.",
        }
    return result


def macro_table(summary: dict, metric_name: str) -> str:
    lines = [f"| {metric_name} | Model | Macro cell MAE | Observed cell range | Cells |", "|---|---|---:|---:|---:|"]
    for name, models in summary.items():
        for model, stats in models.items():
            lines.append(
                f"| {name} | {model} | {stats['macro_cell_mae']:.4f} | "
                f"{stats['minimum_cell_mae']:.4f}–{stats['maximum_cell_mae']:.4f} | {stats['held_out_cells']} |"
            )
    return "\n".join(lines)


def main() -> None:
    if OUT.exists() or REPORT.exists():
        raise FileExistsError("Refusing to overwrite an existing v4 evaluation output or report")

    summary: dict[str, dict] = {}
    fold_frames: list[pd.DataFrame] = []
    prediction_frames: list[pd.DataFrame] = []

    nasa_soh_path = ROOT / "data" / "processed" / "nasa_cross_battery_v1" / "nasa_cross_battery_v1_fold_metrics.csv"
    nasa_soh = pd.read_csv(nasa_soh_path)
    summary["NASA_B0005_B0018_next_discharge_SOH"] = summarize_by_cell(
        nasa_soh, "held_out_battery", "model", "mae_soh_percentage_points"
    )
    tagged = nasa_soh.copy()
    tagged["dataset_group"] = "NASA_B0005_B0006_B0007_B0018"
    tagged["task"] = "next_discharge_SOH"
    fold_frames.append(tagged)

    nasa_rul_path = ROOT / "data" / "processed" / "nasa_rul_v2" / "nasa_rul_v2_fold_metrics.csv"
    nasa_rul = pd.read_csv(nasa_rul_path)
    nasa_rul = nasa_rul[nasa_rul["model"] != "cycle_index_oracle_control"].copy()
    summary["NASA_complete_cell_RUL_to_1p4_Ah"] = summarize_by_cell(
        nasa_rul, "held_out_battery", "model", "mae_cycles"
    )
    tagged = nasa_rul.copy()
    tagged["dataset_group"] = "NASA_B0005_B0006_B0018"
    tagged["task"] = "RUL_to_1p4_Ah"
    fold_frames.append(tagged)

    additional_path = ROOT / "data" / "processed" / "additional_datasets_v3_1" / "nasa_capacity_traces_v3.csv"
    traces_frame = pd.read_csv(additional_path)
    nasa_groups = {
        "NASA_B0025_B0026_B0027_B0028": ["B0025", "B0026", "B0027", "B0028"],
        "NASA_B0029_B0030_B0031_B0032": ["B0029", "B0030", "B0031", "B0032"],
    }
    for group_name, battery_ids in nasa_groups.items():
        cohort = {
            battery_id: frame.sort_values("cycle_number").reset_index(drop=True)
            for battery_id, frame in traces_frame[traces_frame["battery_id"].isin(battery_ids)].groupby("battery_id")
        }
        if len(cohort) != len(battery_ids):
            raise ValueError(f"Incomplete source cell set for {group_name}: found {sorted(cohort)}")
        predictions, metrics = validate_soh(group_name, cohort)
        summary[group_name] = summarize_by_cell(
            metrics, "held_out_cell", "model", "mae_soh_percentage_points"
        )
        metrics = metrics.copy()
        metrics["dataset_group"] = group_name
        metrics["task"] = "next_record_SOH"
        fold_frames.append(metrics)
        predictions["dataset_group"] = group_name
        prediction_frames.append(predictions)

    oxford_path = ROOT / "data" / "processed" / "additional_datasets_v3_1" / "oxford_soh_lobo_metrics_v3.csv"
    oxford = pd.read_csv(oxford_path)
    summary["Oxford_next_characterization_checkpoint_SOH"] = summarize_by_cell(
        oxford, "held_out_cell", "model", "mae_soh_percentage_points"
    )
    tagged = oxford.copy()
    tagged["dataset_group"] = "Oxford_Battery_Degradation_Dataset_1"
    tagged["task"] = "next_characterization_checkpoint_SOH"
    fold_frames.append(tagged)

    folded = pd.concat(fold_frames, ignore_index=True, sort=False)
    report = """# Cell-level evaluation and comparability addendum (v4)

**Generated:** {created}. **Status:** new summaries; source data and prior predictions/reports were not modified.

## Results by independent held-out cell

Metrics below average per-cell MAE equally across held-out cells. The observed range is the full range of cell-specific MAEs, **not** a confidence interval. The sample sizes are too small to estimate dependable population uncertainty.

{soh_table}

| Task | Model | Macro cell MAE | Observed cell range | Cells |
|---|---|---:|---:|---:|
{rul_rows}

## Censoring and model selection

NASA RUL metrics include only the three recorded cells that crossed the dataset-specific 1.4 Ah endpoint. B0007 remains right-censored; it is not assigned a fabricated failure cycle. Current complete-case model scores do not estimate performance on censored cells. A censoring-aware survival model is not fitted because four independent NASA cells (three events and one censored trajectory) are insufficient to support a meaningful survival analysis. The validation reports the available fold spread rather than a misleading bootstrap or narrow confidence interval.

For NASA B0005/B0006/B0007/B0018 next-discharge SOH, linear regression has a macro-cell score that should be compared to persistence; selection should use the better baseline unless additional independent data show a repeatable gain. XGBoost remains a comparator, not the selected model by default.

## Cross-dataset validation boundary

Oxford scores are within-Oxford leave-one-cell-out results, not external validation of the NASA model. Oxford SOH checkpoints are measured at nominal 100-drive-cycle intervals; NASA features use a discharge-record index. CALCE workbook cycle indices overlap/restart and its capacity field requires timeline reconstruction. These feature/time definitions are not yet harmonized, so this addendum intentionally reports no NASA→Oxford or NASA→CALCE transfer score and does not pool family-level metrics. CALCE PL11/PL13 are also unparsed. Cross-family transfer remains unvalidated work.

## RUL endpoint and manual inference

The deployed RUL artifact is trained against the NASA absolute 1.4 Ah endpoint. The API now withholds a manual/CSV RUL output unless the caller confirms a compatible single-cell protocol and the same endpoint. This confirmation is a user assertion, not a sensor-derived protocol check; SOH and second-life outputs remain experimental and lab-cell scoped. A future relative endpoint requires new training labels and independent validation; simply scaling the current 1.4 Ah model is not valid.

## Second-life output

The application output is a capacity-only pre-screen, not an application recommendation. It now explicitly marks engineering assessment as required and lists resistance/impedance, power capability, thermal behavior, physical/electrical condition, matching, BMS and pack integration as unmeasured. No safety or reuse approval is inferred.

## Reproducibility and versioning

`train_nasa_models_v3.py` provides an exclusive-create release pipeline under `models/releases/<version>/`, recording source hashes, package versions, fixed estimator parameters and artifact hashes. Existing v2 inference artifacts remain the active default and are not replaced by this addendum.

All inputs here are laboratory cell data. No EV-pack or field validation is claimed.
""".format(
        created=datetime.now(timezone.utc).isoformat(),
        soh_table=macro_table({k: v for k, v in summary.items() if "RUL" not in k}, "SOH task"),
        rul_rows="\n".join(
            f"| RUL to 1.4 Ah | {model} | {item['macro_cell_mae']:.4f} | "
            f"{item['minimum_cell_mae']:.4f}–{item['maximum_cell_mae']:.4f} | {item['held_out_cells']} |"
            for model, item in summary["NASA_complete_cell_RUL_to_1p4_Ah"].items()
        ),
    )

    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / "evaluation_summary_v4.json").write_text(json.dumps({
        "version": "4.0.0-evaluation-addendum",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary_by_dataset_and_task": summary,
        "independent_unit": "held-out cell/battery; cycles are repeated measures, not independent cells",
        "confidence_intervals": "not computed; independent-cell counts are too small for a dependable inferential interval",
        "cross_dataset_transfer": "not scored because cycle/time features and measurement protocols are not harmonized",
        "right_censoring": {"B0007": "retained as right-censored; excluded from complete-case RUL metric"},
    }, indent=2) + "\n", encoding="utf-8")
    folded.to_csv(OUT / "fold_metrics_v4.csv", index=False)
    if prediction_frames:
        pd.concat(prediction_frames, ignore_index=True, sort=False).to_csv(
            OUT / "nasa_protocol_group_soh_predictions_v4.csv", index=False
        )
    REPORT.write_text(report, encoding="utf-8")
    print(json.dumps({"output_dir": str(OUT), "report": str(REPORT), "datasets": list(summary)}, indent=2))


if __name__ == "__main__":
    main()
