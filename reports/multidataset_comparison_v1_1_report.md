# Harmonized multi-dataset comparison v1

Generated 2026-10-18T18:43:20.079154+00:00. New outputs only; source measurements and prior results were not modified.

## Included data and common definitions

The comparison uses three previously reviewed NASA cohorts (12 cells), Oxford (8 cells), and reconstructed CALCE CS2 (6 cells). NASA B0005/B0006/B0007/B0018, B0025-B0028, and B0029-B0032 remain separate families. CS2 channel discharge counters were differenced within consecutive cycle-index records; duplicate timestamps from overlapping exports were collapsed only when capacities agreed. CS2_3 and CS2_9 were excluded before scoring because reconstructed capacity increments are unstable. CALCE PL11/PL13 remain unparsed.

Capacity is normalized to each cell's first measured record. Shared features omit absolute Ah capacity, ambient temperature, and absolute cycle number. SOH predicts the next measured health-change rate per 100 cycles and projects it using the previous observation gap. This preserves an explicit next-record task, but the record cadence differs across families.

## SOH results by family and training strategy

| Family | Strategy | Macro cell MAE (SOH pp) | Observed cell range | Held-out cells |
|---|---|---:|---:|---:|
| CALCE_CS2 | external_family_ridge | 1.2655 | 1.0186–1.4814 | 6 |
| CALCE_CS2 | external_family_xgboost | 1.2224 | 0.9702–1.4292 | 6 |
| CALCE_CS2 | multi_dataset_ridge | 1.2369 | 0.9866–1.4535 | 6 |
| CALCE_CS2 | multi_dataset_xgboost | 1.2173 | 0.9657–1.4236 | 6 |
| CALCE_CS2 | persistence | 1.2070 | 0.9561–1.4156 | 6 |
| CALCE_CS2 | within_family_ridge | 1.2650 | 1.0194–1.4910 | 6 |
| CALCE_CS2 | within_family_xgboost | 1.2036 | 0.9536–1.4085 | 6 |
| NASA_core | NASA_core_only_ridge | 0.4869 | 0.3204–0.6369 | 4 |
| NASA_core | NASA_core_only_xgboost | 0.4846 | 0.3204–0.6454 | 4 |
| NASA_core | external_family_ridge | 0.5184 | 0.3407–0.6753 | 4 |
| NASA_core | external_family_xgboost | 0.5036 | 0.3333–0.6714 | 4 |
| NASA_core | multi_dataset_ridge | 0.5092 | 0.3352–0.6631 | 4 |
| NASA_core | multi_dataset_xgboost | 0.5006 | 0.3311–0.6668 | 4 |
| NASA_core | persistence | 0.5686 | 0.3659–0.7640 | 4 |
| NASA_core | within_family_ridge | 0.4869 | 0.3204–0.6369 | 4 |
| NASA_core | within_family_xgboost | 0.4846 | 0.3204–0.6454 | 4 |
| NASA_group_B0025_B0028 | external_family_ridge | 1.0406 | 0.3466–2.9126 | 4 |
| NASA_group_B0025_B0028 | external_family_xgboost | 1.0502 | 0.3577–2.9366 | 4 |
| NASA_group_B0025_B0028 | multi_dataset_ridge | 1.0386 | 0.3482–2.9083 | 4 |
| NASA_group_B0025_B0028 | multi_dataset_xgboost | 1.0509 | 0.3592–2.9367 | 4 |
| NASA_group_B0025_B0028 | persistence | 1.0966 | 0.4111–2.9702 | 4 |
| NASA_group_B0025_B0028 | within_family_ridge | 1.1219 | 0.4987–2.8934 | 4 |
| NASA_group_B0025_B0028 | within_family_xgboost | 1.0547 | 0.3645–2.9375 | 4 |
| NASA_group_B0029_B0032 | external_family_ridge | 0.6228 | 0.5255–0.6894 | 4 |
| NASA_group_B0029_B0032 | external_family_xgboost | 0.6835 | 0.5802–0.7369 | 4 |
| NASA_group_B0029_B0032 | multi_dataset_ridge | 0.6100 | 0.5127–0.6736 | 4 |
| NASA_group_B0029_B0032 | multi_dataset_xgboost | 0.6590 | 0.5554–0.7126 | 4 |
| NASA_group_B0029_B0032 | persistence | 0.7442 | 0.6434–0.7971 | 4 |
| NASA_group_B0029_B0032 | within_family_ridge | 0.5757 | 0.4753–0.6251 | 4 |
| NASA_group_B0029_B0032 | within_family_xgboost | 0.5856 | 0.4805–0.6326 | 4 |
| Oxford | external_family_ridge | 19.8242 | 18.4463–21.1541 | 8 |
| Oxford | external_family_xgboost | 20.2219 | 19.9030–20.6601 | 8 |
| Oxford | multi_dataset_ridge | 7.7662 | 6.6427–9.2982 | 8 |
| Oxford | multi_dataset_xgboost | 16.1048 | 15.8914–16.4425 | 8 |
| Oxford | persistence | 0.4520 | 0.2628–0.8351 | 8 |
| Oxford | within_family_ridge | 0.2560 | 0.1302–0.5479 | 8 |
| Oxford | within_family_xgboost | 0.2636 | 0.1311–0.5677 | 8 |

NASA core-only and multi-dataset strategies are evaluated on the same held-out NASA core cells. Within-family models use only other cells in that source family. External-family models omit the entire held-out family. Lower error is better. An observed range is not a confidence interval.

## RUL results by family

RUL uses a harmonized exploratory threshold of 70% of each cell's first measured capacity. Cells that do not reach it are right-censored and omitted from complete-case metrics. This is separate from the deployed NASA model's absolute 1.4 Ah endpoint.

| Family | Strategy | Macro cell MAE (cycles) | Observed cell range | Held-out cells |
|---|---|---:|---:|---:|
| CALCE_CS2 | external_family_ridge | 1333.071 | 899.755–1514.477 | 6 |
| CALCE_CS2 | external_family_xgboost | 1467.491 | 1289.407–1526.907 | 6 |
| CALCE_CS2 | multi_dataset_ridge | 576.004 | 273.688–713.352 | 6 |
| CALCE_CS2 | multi_dataset_xgboost | 978.910 | 788.905–1042.343 | 6 |
| CALCE_CS2 | within_family_ridge | 95.739 | 62.784–230.121 | 6 |
| CALCE_CS2 | within_family_xgboost | 94.799 | 64.121–221.545 | 6 |
| NASA_core | external_family_ridge | 417.239 | 400.285–434.192 | 2 |
| NASA_core | external_family_xgboost | 1524.251 | 1509.251–1539.251 | 2 |
| NASA_core | multi_dataset_ridge | 349.931 | 340.872–358.989 | 2 |
| NASA_core | multi_dataset_xgboost | 1015.125 | 993.104–1037.147 | 2 |
| Oxford | external_family_ridge | 2991.247 | 2444.602–3537.892 | 2 |
| Oxford | external_family_xgboost | 2989.661 | 2447.116–3532.206 | 2 |
| Oxford | multi_dataset_ridge | 1733.464 | 1311.831–2155.097 | 2 |
| Oxford | multi_dataset_xgboost | 2199.508 | 1553.468–2845.548 | 2 |

## Interpretation boundaries

The cell is the independent test unit; repeated cycle observations are not treated as independent batteries. Family- and cell-balanced weights reduce domination by longer traces but cannot remove protocol shift. SOH next-record intervals differ across datasets; RUL endpoints are relative to first observed measurements. Results are exploratory, based on small cell counts, and have no inferential confidence interval.

This comparison does not claim laboratory-cell results validate an EV pack, field operation, or second-life safety. Existing inference releases remain unchanged; the new models here are fold-specific and are not promoted to the dashboard.

Detailed cell scores, capacity traces, source hashes, exclusions, censoring, and package versions are in data/processed/multidataset_comparison_v1_1.
