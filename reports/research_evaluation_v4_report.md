# Cell-level evaluation and comparability addendum (v4)

**Generated:** 2026-10-18T18:11:53.286566+00:00. **Status:** new summaries; source data and prior predictions/reports were not modified.

## Results by independent held-out cell

Metrics below average per-cell MAE equally across held-out cells. The observed range is the full range of cell-specific MAEs, **not** a confidence interval. The sample sizes are too small to estimate dependable population uncertainty.

| SOH task | Model | Macro cell MAE | Observed cell range | Cells |
|---|---|---:|---:|---:|
| NASA_B0005_B0018_next_discharge_SOH | linear_regression | 0.5955 | 0.3324–1.0271 | 4 |
| NASA_B0005_B0018_next_discharge_SOH | persistence | 0.5686 | 0.3659–0.7640 | 4 |
| NASA_B0005_B0018_next_discharge_SOH | xgboost | 1.2741 | 0.4729–3.1809 | 4 |
| NASA_B0025_B0026_B0027_B0028 | linear_regression | 1.3283 | 0.7713–2.6044 | 4 |
| NASA_B0025_B0026_B0027_B0028 | persistence | 1.0966 | 0.4111–2.9702 | 4 |
| NASA_B0025_B0026_B0027_B0028 | xgboost | 0.9485 | 0.4704–1.7337 | 4 |
| NASA_B0029_B0030_B0031_B0032 | linear_regression | 0.6535 | 0.4739–0.7786 | 4 |
| NASA_B0029_B0030_B0031_B0032 | persistence | 0.7442 | 0.6434–0.7971 | 4 |
| NASA_B0029_B0030_B0031_B0032 | xgboost | 0.7625 | 0.5574–0.8726 | 4 |
| Oxford_next_characterization_checkpoint_SOH | linear_regression | 0.2953 | 0.1515–0.5922 | 8 |
| Oxford_next_characterization_checkpoint_SOH | persistence | 0.4520 | 0.2628–0.8351 | 8 |
| Oxford_next_characterization_checkpoint_SOH | xgboost | 0.7341 | 0.2025–2.8708 | 8 |

| Task | Model | Macro cell MAE | Observed cell range | Cells |
|---|---|---:|---:|---:|
| RUL to 1.4 Ah | linear_regression | 1019.8252 | 25.4666–3007.3168 | 3 |
| RUL to 1.4 Ah | recent_slope_extrapolation | 533.5681 | 26.2080–1540.5991 | 3 |
| RUL to 1.4 Ah | xgboost | 11.5078 | 7.6702–15.0603 | 3 |

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
