# NASA cell cross-battery validation (v1)

**Run date:** 2026-10-18  
**Data:** NASA PCoE accelerated aging files B0005, B0006, B0007, B0018  
**Task:** Predict SOH at the next recorded discharge from measurements through the current discharge.

## Measured results

Leave-one-battery-out validation held out each battery in turn. Each fold trained on the other three cells. The same five features were used for the learned models: discharge index, ambient temperature, current relative SOH, previous relative SOH, and change in discharge capacity from the previous record. Persistence predicts next-discharge SOH as current SOH.

| Model | Pooled MAE (SOH percentage points) | Pooled RMSE (SOH percentage points) | Pooled R² |
|---|---:|---:|---:|
| Persistence | 0.5574 | 0.9569 | 0.9922 |
| Linear regression | 0.5924 | 1.0282 | 0.9910 |
| XGBoost | 1.3088 | 2.6378 | 0.9406 |

The pooled result is weighted by the number of next-discharge predictions per cell. Fold metrics and all per-observation predictions are in `data/processed/nasa_cross_battery_v1/`.

The valid discharge counts are 168 each for B0005, B0006, and B0007, and 132 for B0018. A generated summary initially undercounted these by one and labeled the first supervised row's capacity as the first discharge capacity; its relative-SOH maximum also omitted the 100% baseline. The separate `nasa_cross_battery_v1_quality_addendum.json` corrects these displayed summary fields. Prediction rows and metrics were not affected.

| Held-out cell | Persistence MAE | Linear MAE | XGBoost MAE |
|---|---:|---:|---:|
| B0005 | 0.4380 | 0.3736 | 0.7744 |
| B0006 | 0.7066 | 1.0271 | 3.1809 |
| B0007 | 0.3659 | 0.3324 | 0.4729 |
| B0018 | 0.7640 | 0.6487 | 0.6681 |

These metrics come from the local NASA files and the v1 validation script. They measure one-step prediction of the next recorded discharge in four laboratory cells. They do not demonstrate field performance or EV battery-pack performance.

## Measurement and modeling choices

- Capacity and relative SOH use discharge records with finite positive `Capacity` values.
- Relative SOH is capacity divided by that cell's first valid discharge capacity, multiplied by 100. It is not normalized to rated capacity.
- Inputs include current-discharge capacity-derived SOH and previous-discharge information. This is a next-record prediction only when those current-discharge measurements are available at prediction time.
- The per-cell initial discharge is required to establish the relative-SOH baseline, including for a held-out cell. This is a stated measurement assumption, not learned from other cells.
- The four NASA cells have different discharge cutoff voltages; this affects capacity comparability. The study has only four cells and one fixed model configuration.
- High pooled R² mainly reflects the smooth degradation trend and should not replace fold-level error analysis. Persistence is the pooled MAE/RMSE reference; it is not a learned model.
- This analysis does not calculate remaining useful life (RUL).

## Reproducibility and preservation

Run `validate_nasa_cross_battery_v1.py` with the existing `.venv`. The script refuses to write if its output directory already exists. The original B0005 files and all source MAT files were preserved. No packages were installed.

## Suggested next research steps

Evaluate sensitivity to the per-cell SOH reference and cutoff-voltage differences, report uncertainty across cells, and seek independent cell cohorts before making broader generalization claims. Any EV-pack claim would require pack-level data and validation under pack operating conditions.
