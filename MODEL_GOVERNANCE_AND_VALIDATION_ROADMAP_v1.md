# Model governance and validation status

## What the local evidence supports

This project has real, reproducible laboratory-cell evaluations. The comparison in `data/processed/multidataset_comparison_v1_3/` uses complete held-out cells as the independent unit, weights cells explicitly, and keeps source-family metrics separate. It covers 26 cells across NASA cohorts, Oxford, and CALCE CS2. The report has no inferential confidence intervals because the independent-cell counts are small. These results are not evidence of EV-pack or field performance.

Measured examples from the existing reports:

- NASA core next-record SOH (the v4 evaluation): linear regression macro-cell MAE is 0.595 SOH percentage points across 4 held-out cells; persistence is 0.569 pp. The current linear model therefore does not beat this simple comparator on that cohort average.
- NASA RUL to the study-specific 1.4 Ah endpoint: XGBoost macro-cell MAE is 11.51 recorded discharge cycles across 3 complete held-out cells. B0007 is right-censored and is not scored as a complete failure time.
- In the separate harmonized comparison, CALCE CS2 multi-dataset XGBoost next-record SOH MAE is 1.005 pp across 6 cells, versus 0.994 pp for persistence. That difference is small and does not show a useful gain from pooling.
- In that same comparison, Oxford within-family Ridge MAE is 0.256 pp across 8 cells, while multi-dataset Ridge is 7.951 pp and multi-dataset XGBoost is 16.098 pp. This is a strong negative-transfer warning for the tested pooled models. Keep Oxford inference source-specific.

The two reports use different target definitions and evaluation protocols. Their metrics must not be combined into one accuracy score. The model release `4.0.0-multisource-experimental` routes SOH by source; the collective-input view is a two-point trend baseline, not a pooled trained model. NASA RUL remains specific to its stated threshold and protocol.

## Follow-up outcomes

The dashboard Prediction Log remains browser-local. It now reports matched-target SOH outcomes as a cell-macro MAE within each data source, counts cells separately from readings, and counts confirmed threshold crossings separately from right-censored observations. It has a JSON import/merge action: existing IDs are skipped and malformed imports leave existing entries unchanged. No sample records are created by this feature.

Treat imported or typed outcomes as unverified until the measurement provenance and test protocol have been reviewed. A follow-up is eligible for SOH error only when it is measured at the exact predicted target cycle. RUL outcomes are not interchangeable across endpoints, chemistries, or discharge protocols. A prediction log is a review dataset; it does not update model artifacts.

## Safe candidate-model gate

Keep the current release immutable while evaluating challengers. For each candidate release:

1. Assign a new release directory and model version; never replace an artifact in a published release.
2. Record training-data hashes, preprocessing version, feature order, target definition, training cells, and software versions in the candidate manifest.
3. Split by complete cell before fitting or tuning. For external-transfer claims, hold out the entire dataset family and avoid using its measurements for model selection.
4. Report per-cell errors, cell-macro MAE and RMSE, comparator metrics, endpoint/censoring counts, and the exact target horizon. Do not use cycle rows as independent sample size.
5. Compare against persistence and a transparent trend baseline. A candidate that fails to improve the relevant family baseline remains a candidate; it is not promoted for that family.
6. Review scientific scope and provenance, then manually point the active manifest to the candidate only after the gate passes. Preserve the prior release for rollback. There is no automatic retraining or promotion.

This is a proposed governance gate, not a claim that a new model has passed it. Existing versioned manifests and artifact hashes provide a starting point for the release process.

## Second-life outcomes and real-world limits

The current second-life result is a capacity-only project heuristic. There are no documented engineering reuse assessments in the local datasets, so no supervised recommendation score can be validated or learned. Before modeling application suitability, collect reviewed outcomes linked to traceable cells or packs, including the intended duty cycle, independent capacity and power tests, resistance/impedance, thermal and isolation checks, cell matching/BMS compatibility, reviewer, date, protocol, and the engineering disposition. Keep safety decisions with qualified engineers; a capacity threshold is not a reuse approval.

Real EV battery-pack and field validation requires pack-level or field measurements with traceable ground truth, operating histories, and safety outcomes. NASA, Oxford, and CALCE laboratory-cell results cannot substitute for that evidence.

## Next research actions that need new evidence

- Add more independent cells and protocols, especially held-out-family data where the intended deployment domain is represented.
- Gather prospective follow-up measurements with cell ID, source, test conditions, cycle/time definition, measured capacity, and provenance.
- Collect engineering-reviewed second-life assessment outcomes as a separate target from SOH/RUL.
- Obtain pack- or field-level validation data before making EV-pack performance claims.
