# Multi-dataset comparison version note

Use [multidataset_comparison_v1_2_report.md](multidataset_comparison_v1_2_report.md) and `data/processed/multidataset_comparison_v1_2/` as the authoritative comparison outputs.

## Superseded exploratory run

The earlier `multidataset_comparison_v1_1_report.md` and `data/processed/multidataset_comparison_v1_1/` included preliminary CALCE CS2 capacity reconstructions. Inspection showed anomalous candidate capacities (about 0.05 to over 5 Ah) on traces otherwise near 1 Ah. Those CS2 results are not valid for interpretation. Version 1.2 excludes all CALCE CS2 records from scoring pending session-aware reconstruction. Original CALCE source files were not changed.

## SOH horizon wording

The v1.2 report says the forecast projects using the “previous observation gap.” The implemented evaluation uses the known gap from the current record to the next scheduled record (`next_gap_cycles`) to project the predicted next-record SOH. The previous gap is only an input feature. Results and CSV files are unaffected by this report wording error.

## Reading the comparison

The NASA-core comparison is a leave-one-cell-out evaluation on the same four B0005/B0006/B0007/B0018 test cells. NASA-only XGBoost achieved 0.4846 SOH percentage points macro-cell MAE; NASA-plus-other-cohorts-and-Oxford XGBoost achieved 0.4938. Pooling did not improve this comparison. The RUL results have only two uncensored held-out cells per scored family and are exploratory, not a basis for deployment claims.
