# Harmonized multi-dataset comparison v1

Generated 2026-10-19T17:59:18.104662+00:00. New outputs only; source measurements and prior results were not modified.

## Included data and common definitions

The comparison uses three NASA cohorts (12 cells), Oxford (8 cells), and CALCE CS2 (6 cells). NASA B0005/B0006/B0007/B0018, B0025-B0028, and B0029-B0032 remain separate families. CS2 per-cycle discharge capacity was calculated as the within-cycle span of its cumulative channel counter (maximum minus minimum), restricted to 0.2–1.5 Ah; same-timestamp duplicate exports were collapsed where capacities agreed, and conflicting timestamps were excluded. CS2_3 and CS2_9 failed the cell-level stability gate and were excluded. CALCE PL11/PL13 remain unparsed.

Capacity is normalized to each cell's first measured record. Shared features omit absolute Ah capacity, ambient temperature, and absolute cycle number. SOH predicts the next measured health-change rate per 100 cycles and projects it using the known interval to the next scheduled observation. This preserves an explicit next-record task, but the record cadence differs across families.

## SOH results by family and training strategy

| Family | Strategy | Macro cell MAE (SOH pp) | Observed cell range | Held-out cells |
|---|---|---:|---:|---:|
| CALCE_CS2 | external_family_ridge | 1.0495 | 0.9813–1.1554 | 6 |
| CALCE_CS2 | external_family_xgboost | 1.0099 | 0.9424–1.1218 | 6 |
| CALCE_CS2 | multi_dataset_ridge | 1.0227 | 0.9531–1.1334 | 6 |
| CALCE_CS2 | multi_dataset_xgboost | 1.0048 | 0.9373–1.1160 | 6 |
| CALCE_CS2 | persistence | 0.9938 | 0.9226–1.1054 | 6 |
| CALCE_CS2 | within_family_ridge | 1.0141 | 0.9466–1.1169 | 6 |
| CALCE_CS2 | within_family_xgboost | 0.9906 | 0.9231–1.0997 | 6 |
| NASA_core | NASA_core_only_ridge | 0.4869 | 0.3204–0.6369 | 4 |
| NASA_core | NASA_core_only_xgboost | 0.4846 | 0.3204–0.6454 | 4 |
| NASA_core | external_family_ridge | 0.5181 | 0.3409–0.6768 | 4 |
| NASA_core | external_family_xgboost | 0.5034 | 0.3332–0.6711 | 4 |
| NASA_core | multi_dataset_ridge | 0.5091 | 0.3357–0.6646 | 4 |
| NASA_core | multi_dataset_xgboost | 0.5008 | 0.3312–0.6669 | 4 |
| NASA_core | persistence | 0.5686 | 0.3659–0.7640 | 4 |
| NASA_core | within_family_ridge | 0.4869 | 0.3204–0.6369 | 4 |
| NASA_core | within_family_xgboost | 0.4846 | 0.3204–0.6454 | 4 |
| NASA_group_B0025_B0028 | external_family_ridge | 1.0389 | 0.3480–2.9103 | 4 |
| NASA_group_B0025_B0028 | external_family_xgboost | 1.0502 | 0.3577–2.9366 | 4 |
| NASA_group_B0025_B0028 | multi_dataset_ridge | 1.0376 | 0.3485–2.9077 | 4 |
| NASA_group_B0025_B0028 | multi_dataset_xgboost | 1.0509 | 0.3592–2.9367 | 4 |
| NASA_group_B0025_B0028 | persistence | 1.0966 | 0.4111–2.9702 | 4 |
| NASA_group_B0025_B0028 | within_family_ridge | 1.1219 | 0.4987–2.8934 | 4 |
| NASA_group_B0025_B0028 | within_family_xgboost | 1.0547 | 0.3645–2.9375 | 4 |
| NASA_group_B0029_B0032 | external_family_ridge | 0.6397 | 0.5416–0.7043 | 4 |
| NASA_group_B0029_B0032 | external_family_xgboost | 0.6837 | 0.5804–0.7371 | 4 |
| NASA_group_B0029_B0032 | multi_dataset_ridge | 0.6164 | 0.5148–0.6793 | 4 |
| NASA_group_B0029_B0032 | multi_dataset_xgboost | 0.6588 | 0.5553–0.7125 | 4 |
| NASA_group_B0029_B0032 | persistence | 0.7442 | 0.6434–0.7971 | 4 |
| NASA_group_B0029_B0032 | within_family_ridge | 0.5757 | 0.4753–0.6251 | 4 |
| NASA_group_B0029_B0032 | within_family_xgboost | 0.5856 | 0.4805–0.6326 | 4 |
| Oxford | external_family_ridge | 20.3855 | 19.2699–21.5058 | 8 |
| Oxford | external_family_xgboost | 20.1206 | 19.8038–20.5565 | 8 |
| Oxford | multi_dataset_ridge | 7.9506 | 7.0734–9.2256 | 8 |
| Oxford | multi_dataset_xgboost | 16.0982 | 15.8864–16.4222 | 8 |
| Oxford | persistence | 0.4520 | 0.2628–0.8351 | 8 |
| Oxford | within_family_ridge | 0.2560 | 0.1302–0.5479 | 8 |
| Oxford | within_family_xgboost | 0.2636 | 0.1311–0.5677 | 8 |

NASA core-only and multi-dataset strategies are evaluated on the same held-out NASA core cells. Within-family models use only other cells in that source family. External-family models omit the entire held-out family. Lower error is better. An observed range is not a confidence interval.

## RUL results by family

RUL uses a harmonized exploratory threshold of 70% of each cell's first measured capacity. Cells that do not reach it are right-censored and omitted from complete-case metrics. This is separate from the deployed NASA model's absolute 1.4 Ah endpoint.

| Family | Strategy | Macro cell MAE (cycles) | Observed cell range | Held-out cells |
|---|---|---:|---:|---:|
| CALCE_CS2 | external_family_ridge | 1050.440 | 873.116–1514.477 | 6 |
| CALCE_CS2 | external_family_xgboost | 1338.574 | 1269.407–1526.907 | 6 |
| CALCE_CS2 | multi_dataset_ridge | 376.685 | 189.411–894.828 | 6 |
| CALCE_CS2 | multi_dataset_xgboost | 892.797 | 819.042–1093.633 | 6 |
| CALCE_CS2 | within_family_ridge | 163.152 | 95.249–322.916 | 6 |
| CALCE_CS2 | within_family_xgboost | 154.718 | 105.971–226.000 | 6 |
| NASA_core | external_family_ridge | 467.033 | 433.888–500.179 | 2 |
| NASA_core | external_family_xgboost | 1588.411 | 1573.411–1603.411 | 2 |
| NASA_core | multi_dataset_ridge | 345.691 | 319.896–371.486 | 2 |
| NASA_core | multi_dataset_xgboost | 1057.850 | 1035.841–1079.860 | 2 |
| Oxford | external_family_ridge | 2923.273 | 2369.642–3476.904 | 2 |
| Oxford | external_family_xgboost | 2928.337 | 2385.599–3471.074 | 2 |
| Oxford | multi_dataset_ridge | 1712.195 | 1368.201–2056.188 | 2 |
| Oxford | multi_dataset_xgboost | 2173.374 | 1531.654–2815.094 | 2 |

## Interpretation boundaries

The cell is the independent test unit; repeated cycle observations are not treated as independent batteries. Family- and cell-balanced weights reduce domination by longer traces but cannot remove protocol shift. SOH next-record intervals differ across datasets; RUL endpoints are relative to first observed measurements. Results are exploratory, based on small cell counts, and have no inferential confidence interval.

This comparison does not claim laboratory-cell results validate an EV pack, field operation, or second-life safety. Existing inference releases remain unchanged; the new models here are fold-specific and are not promoted to the dashboard.

Detailed cell scores, capacity traces, source hashes, exclusions, censoring, and package versions are in data/processed/multidataset_comparison_v1_3.
