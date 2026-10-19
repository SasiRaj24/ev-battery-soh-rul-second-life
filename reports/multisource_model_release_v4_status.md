# Multi-source model release 4.0.0 experimental

## Analyzer routes

The typed-input analyzer routes by selected source family:

- NASA uses the existing NASA SOH and RUL artifacts from model release 2.0.0.
- Oxford uses a new four-feature Ridge SOH artifact trained on the eight local Oxford cells.
- CALCE CS2 uses a new four-feature XGBoost SOH artifact trained on CS2_33 through CS2_38.

The new artifacts are in `models/releases/4.0.0-multisource-experimental/`; their hashes and feature order are recorded in `manifest.json`. The original NASA model files and earlier releases remain unchanged.

## Validation evidence

The source-specific models use cell-balanced, leave-one-cell-out validation from `reports/multidataset_comparison_v1_3_report.md`:

| Source | Model | Macro-cell SOH MAE | Persistence MAE | Held-out cells |
|---|---|---:|---:|---:|
| Oxford | Ridge | 0.2560 SOH pp | 0.4521 SOH pp | 8 |
| CALCE CS2 | XGBoost | 0.9906 SOH pp | 0.9938 SOH pp | 6 |

Oxford showed lower observed error than persistence in this small cell-level study. CALCE was effectively tied with persistence; its inclusion provides a source-specific research comparison, not demonstrated improvement. There are no confidence intervals.

## Scope and limitations

Capacity is normalized to the user-provided first-measurement reference. Oxford must include the next scheduled checkpoint cycle because records are sparse. CALCE per-cycle discharge capacity is the within-cycle span of its cumulative raw channel counter; CS2_3 and CS2_9 remain excluded by the quality gate. CALCE RUL and Oxford RUL are withheld from the interactive analyzer. RUL remains available only for NASA with its compatible protocol and 1.4 Ah study endpoint. These models use laboratory cells; they do not establish EV-pack performance, field validity, or second-life safety.
