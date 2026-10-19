# Additional battery datasets: v3.1 audit and separate cell-held-out validation

**Status:** 2026-10-18. This report uses only the corrected v3.1 outputs. The earlier development directory `data/processed/additional_datasets_v3/` is preserved but explicitly invalid because its first SOH run aligned target and input on the same row. Do not report those metrics.

## Scope and data handling

All non-algae sources were inventoried. NASA PCoE and Oxford capacity records were converted into new, source-linked cycle/checkpoint CSVs and evaluated separately. CALCE files were audited but not given model metrics because their exports need session-aware reconstruction. No source files were changed. No algae file was loaded by this run.

The existing v2 inference models and original four-cell NASA results are unchanged. The new validation results are separate research results and do not update the v2 model artifacts.

## NASA PCoE extension

Thirty-four battery MAT files were parsed, including the original B0005/B0006/B0007/B0018 and thirty additional battery files. Discharge records with non-finite or nonpositive capacity were excluded from the model table and counted in the source-quality catalog. SOH is normalized to each cell's first valid observed capacity.

SOH was evaluated by leaving one entire cell out. Each held-out point predicts the **next recorded discharge SOH** from current/past measurements. The table gives the macro average of the held-out-cell MAEs, so each held-out battery contributes one fold regardless of its number of rows.

| Model | Macro cell-held-out MAE (SOH percentage points) | Folds |
|---|---:|---:|
| Persistence | 9.4091 | 34 |
| Linear regression | 10.9749 | 34 |
| XGBoost | 44.0403 | 34 |

The added NASA files do **not** support simply extending the strong-looking four-cell v1 score to the broader file set. On this broader cohort the persistence baseline is better than both learned models, especially XGBoost. Protocol variation and unusual/short cell trajectories need further stratification and quality review before model selection.

For exploratory RUL only, the endpoint was **70% of each cell's first valid observed capacity**. This is a project comparison assumption, not a universal retirement, safety, or second-life threshold. Eleven cells crossed it and 23 remained right-censored. XGBoost macro cell-held-out MAE was 20.1086 recorded discharge cycles over 11 folds. This endpoint is different from the four-cell v2 analysis at the NASA dataset's absolute 1.4 Ah criterion; the scores are not directly comparable.

## Oxford Battery Degradation Dataset 1

Eight cells were parsed from the Oxford MAT file. Capacity is derived from the magnitude of the minimum `C1dc.q` in mAh, converted to Ah, following the local dataset readme. Measurements are characterization checkpoints nominally spaced about 100 drive cycles apart. Thus the SOH task predicts the **next recorded characterization SOH**, not the next discharge cycle.

| Model | Macro cell-held-out MAE (SOH percentage points) | Folds |
|---|---:|---:|
| Persistence | 0.4520 | 8 |
| Linear regression | 0.2953 | 8 |
| XGBoost | 0.7341 | 8 |

For the same explicit 70%-of-first-observed-capacity RUL assumption, only two cells crossed the endpoint; six were right-censored. The two-fold XGBoost MAE was 2,159.49 actual cycle numbers. Two complete cells are insufficient for a dependable RUL performance claim; this is retained as exploratory output only.

## CALCE

The project catalog now includes eight CS2 identifiers with 232 Excel workbooks. 127 workbooks contain parseable `Statistics` sheets (4,015 rows); 105 do not. Workbook exports overlap, reuse cycle indices, and contain 100 duplicate timestamps across files. The discharge-capacity field is cumulative in inspected workbooks. These records are preserved in source files, but must be reconciled by timestamp and test-session boundaries before generating continuous cell trajectories or training metrics.

The PL folder contains two unique cells, PL11 and PL13, with exact duplicate copies under `SOC_0%-100%_HalfC`. SciPy exposes the MATLAB table payloads as opaque objects in this environment, so these cells are catalogued but not yet converted. They are not counted twice.

## Outputs

All new normalized traces, predictions, fold metrics, and the source-quality catalog are in `data/processed/additional_datasets_v3_1/`. The validation script is `validate_additional_datasets_v3.py` and refuses to overwrite its output directory.

These are laboratory-cell results. They do not establish EV battery-pack, field, safety, certification, or application validation.
