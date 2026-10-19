# Additional battery datasets — v3.2 quality-aware update

**Date:** 2026-10-18. Algae is excluded. This addendum supersedes the broad NASA interpretation in `additional_datasets_v3_1_report.md`; it does not modify that earlier report or its outputs.

## Scope and provenance

The local source inventory contains 34 NASA battery MAT files, 8 Oxford cells in one MAT source, CALCE CS2 workbook exports, and unique PL11/PL13 records. NASA and Oxford traces in v3.1 remain preserved. The dashboard catalog now reads `data/processed/additional_datasets_v3_2/dataset_catalog_v3_2.json`. Existing inference model artifacts and original B0005/B0006/B0007/B0018 results remain unchanged.

## NASA interpretation correction

The v3.1 broad NASA score normalized every cell by its first positive recorded capacity. A source-quality review found extremely low first measurements in some files, yielding nonsensical relative SOH values (for example, B0033 exceeded 1,900%). NASA cohorts also vary in temperature, load, voltage cutoff, stopping conditions and stated capacity endpoint. The pooled v3.1 metrics (including its relative 70%-of-first-capacity RUL) are therefore retained as historical output but **must not be presented as reliable validation**. The dashboard withholds those pooled metrics and their RUL status counts.

Two four-cell protocol groups with more coherent observed capacity trajectories were scored separately for next-record SOH using leave-one-cell-out evaluation. Macro MAE is the mean of each held-out cell's MAE; units are SOH percentage points.

| NASA group | Persistence | Linear regression | XGBoost | Held-out cells |
|---|---:|---:|---:|---:|
| B0025–B0028 | 1.0966 | 1.3283 | 0.9485 | 4 |
| B0029–B0032 | 0.7442 | 0.6535 | 0.7625 | 4 |

These are measured exploratory within-group results, not a pooled cross-protocol benchmark. They do not establish generalization to other NASA cohorts, EV packs, field use, safety, or second-life qualification. No NASA RUL extension is reported: the selected local cohort documentation does not establish a shared endpoint for these groups. Other NASA files remain inventoried pending per-cohort baseline and endpoint review.

## Oxford and CALCE status

Oxford's 8-cell scores remain in the catalog as exploratory next-characterization-checkpoint predictions (not next-cycle predictions). The relative 70%-of-first-observation RUL comparison has only two endpoint crossings and remains too small for a dependable performance claim.

CALCE CS2 remains an inventory/audit: workbook exports overlap and reuse cycle indices, so session-aware reconstruction is still required before creating trajectories or metrics. PL11/PL13 remain catalogued, not parsed for validation.

## Project implementation

The API catalog endpoint now serves v3.2. The dashboard separates NASA groups and labels those numbers exploratory, withholds the invalid pooled NASA result, and marks Oxford RUL exploratory. The v2 inference artifacts remain trained on the original four NASA cells. The larger typography and dataset coverage screen remain in place.
