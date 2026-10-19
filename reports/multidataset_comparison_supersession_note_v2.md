# Multi-dataset comparison version note v2

Use [multidataset_comparison_v1_3_report.md](multidataset_comparison_v1_3_report.md) and `data/processed/multidataset_comparison_v1_3/` as the authoritative comparison. It includes 12 NASA cells, 8 Oxford cells, and 6 quality-screened CALCE CS2 cells.

## Earlier exploratory versions

- v1.1 differenced adjacent cycle endpoints in the CALCE cumulative channel, producing invalid capacity outliers. Its CALCE scores must not be used.
- v1.2 omitted CALCE while reconstruction was being checked. It remains a valid NASA/Oxford-only comparison but is superseded for coverage by v1.3.
- v1.3 calculates capacity as the within-cycle maximum-minus-minimum span of the cumulative raw channel counter, removes incomplete spans outside 0.2–1.5 Ah, collapses agreeing duplicate timestamps, and excludes conflicting timestamps. CS2_3 and CS2_9 fail the stability gate and are not scored.

## Findings

On the same four held-out NASA core cells, NASA-only XGBoost SOH MAE is 0.4846 percentage points and multi-source XGBoost MAE is 0.5008. Pooling did not improve NASA-core SOH. Oxford performs best with its source-specific Ridge model (0.2560 pp versus persistence 0.4521 pp across eight held-out cells). CALCE CS2 XGBoost is effectively tied with persistence (0.9906 versus 0.9938 pp across six cells). Both comparisons are exploratory and have no inferential confidence intervals. RUL transfer remains unsuitable for deployment.
