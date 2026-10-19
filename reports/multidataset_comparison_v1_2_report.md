# Harmonized multi-dataset comparison v1

Generated 2026-10-18T18:44:27.413494+00:00. New outputs only; source measurements and prior results were not modified.

## Included data and common definitions

The scored comparison uses three reviewed NASA cohorts (12 cells) and Oxford (8 cells). NASA B0005/B0006/B0007/B0018, B0025-B0028, and B0029-B0032 remain separate cohorts. CALCE CS2 is not scored: overlapping workbook sessions have not been reconciled into a validated cycle-capacity trajectory. A preliminary reconstruction produced anomalous candidates from about 0.05 to over 5 Ah on traces otherwise near 1 Ah, consistent with the existing dataset audit's session-reconciliation warning. CALCE PL11/PL13 remain unparsed.

Capacity is normalized to each cell's first measured record. Shared features omit absolute Ah capacity, ambient temperature, and absolute cycle number. SOH predicts the next measured health-change rate per 100 cycles and projects it using the previous observation gap. This preserves an explicit next-record task, but the record cadence differs across families.

## SOH results by family and training strategy

| Family | Strategy | Macro cell MAE (SOH pp) | Observed cell range | Held-out cells |
|---|---|---:|---:|---:|
| NASA_core | NASA_core_only_ridge | 0.4869 | 0.3204–0.6369 | 4 |
| NASA_core | NASA_core_only_xgboost | 0.4846 | 0.3204–0.6454 | 4 |
| NASA_core | external_family_ridge | 0.6288 | 0.4009–0.8385 | 4 |
| NASA_core | external_family_xgboost | 0.4954 | 0.3295–0.6597 | 4 |
| NASA_core | multi_dataset_ridge | 0.5461 | 0.3449–0.7320 | 4 |
| NASA_core | multi_dataset_xgboost | 0.4938 | 0.3279–0.6568 | 4 |
| NASA_core | persistence | 0.5686 | 0.3659–0.7640 | 4 |
| NASA_core | within_family_ridge | 0.4869 | 0.3204–0.6369 | 4 |
| NASA_core | within_family_xgboost | 0.4846 | 0.3204–0.6454 | 4 |
| NASA_group_B0025_B0028 | external_family_ridge | 1.0415 | 0.3466–2.9139 | 4 |
| NASA_group_B0025_B0028 | external_family_xgboost | 1.0489 | 0.3531–2.9345 | 4 |
| NASA_group_B0025_B0028 | multi_dataset_ridge | 1.0410 | 0.3482–2.9084 | 4 |
| NASA_group_B0025_B0028 | multi_dataset_xgboost | 1.0496 | 0.3555–2.9351 | 4 |
| NASA_group_B0025_B0028 | persistence | 1.0966 | 0.4111–2.9702 | 4 |
| NASA_group_B0025_B0028 | within_family_ridge | 1.1219 | 0.4987–2.8934 | 4 |
| NASA_group_B0025_B0028 | within_family_xgboost | 1.0547 | 0.3645–2.9375 | 4 |
| NASA_group_B0029_B0032 | external_family_ridge | 0.6881 | 0.5897–0.7599 | 4 |
| NASA_group_B0029_B0032 | external_family_xgboost | 0.6799 | 0.5764–0.7335 | 4 |
| NASA_group_B0029_B0032 | multi_dataset_ridge | 0.6463 | 0.5451–0.7220 | 4 |
| NASA_group_B0029_B0032 | multi_dataset_xgboost | 0.6509 | 0.5474–0.7036 | 4 |
| NASA_group_B0029_B0032 | persistence | 0.7442 | 0.6434–0.7971 | 4 |
| NASA_group_B0029_B0032 | within_family_ridge | 0.5757 | 0.4753–0.6251 | 4 |
| NASA_group_B0029_B0032 | within_family_xgboost | 0.5856 | 0.4805–0.6326 | 4 |
| Oxford | external_family_ridge | 22.2687 | 20.6587–23.8168 | 8 |
| Oxford | external_family_xgboost | 23.9388 | 23.5443–24.4649 | 8 |
| Oxford | multi_dataset_ridge | 11.9343 | 10.3180–13.8587 | 8 |
| Oxford | multi_dataset_xgboost | 17.9532 | 17.6830–18.3343 | 8 |
| Oxford | persistence | 0.4520 | 0.2628–0.8351 | 8 |
| Oxford | within_family_ridge | 0.2560 | 0.1302–0.5479 | 8 |
| Oxford | within_family_xgboost | 0.2636 | 0.1311–0.5677 | 8 |

NASA core-only and multi-dataset strategies are evaluated on the same held-out NASA core cells. Within-family models use only other cells in that source family. External-family models omit the entire held-out family. Lower error is better. An observed range is not a confidence interval.

## RUL results by family

RUL uses a harmonized exploratory threshold of 70% of each cell's first measured capacity. Cells that do not reach it are right-censored and omitted from complete-case metrics. This is separate from the deployed NASA model's absolute 1.4 Ah endpoint.

| Family | Strategy | Macro cell MAE (cycles) | Observed cell range | Held-out cells |
|---|---|---:|---:|---:|
| NASA_core | external_family_ridge | 2262.324 | 2122.683–2401.966 | 2 |
| NASA_core | external_family_xgboost | 3012.226 | 2997.226–3027.226 | 2 |
| NASA_core | multi_dataset_ridge | 1010.284 | 962.063–1058.505 | 2 |
| NASA_core | multi_dataset_xgboost | 1504.104 | 1478.424–1529.783 | 2 |
| Oxford | external_family_ridge | 3000.541 | 2453.618–3547.465 | 2 |
| Oxford | external_family_xgboost | 3007.172 | 2464.487–3549.858 | 2 |
| Oxford | multi_dataset_ridge | 1644.470 | 1101.498–2187.443 | 2 |
| Oxford | multi_dataset_xgboost | 1952.324 | 1324.257–2580.391 | 2 |

## Interpretation boundaries

The cell is the independent test unit; repeated cycle observations are not treated as independent batteries. Family- and cell-balanced weights reduce domination by longer traces but cannot remove protocol shift. SOH next-record intervals differ across datasets; RUL endpoints are relative to first observed measurements. Results are exploratory, based on small cell counts, and have no inferential confidence interval.

This comparison does not claim laboratory-cell results validate an EV pack, field operation, or second-life safety. Existing inference releases remain unchanged; the new models here are fold-specific and are not promoted to the dashboard.

Detailed cell scores, capacity traces, source hashes, exclusions, censoring, and package versions are in data/processed/multidataset_comparison_v1_2.
