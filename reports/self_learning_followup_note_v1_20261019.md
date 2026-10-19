# Deferred project item: self-learning workflow

Status: Deferred at the user's request on 2026-10-19. Resume when requested.

## Proposed next step
Add a prediction-and-follow-up log before implementing automated model learning.

The log should link each prediction to its later measured outcome and preserve cell/source identity, measurement provenance, cycle and capacity values, applicable test conditions, and the model version used. Keep logging separate from model training; do not silently update active models.

## Validation and promotion requirements
- Evaluate candidate models with cell-held-out splits and report results by dataset family.
- Compare against the active model and simple baselines; preserve all existing model releases.
- Track right-censored cells for RUL rather than treating them as completed failures.
- Require documented outcomes and engineering review for second-life recommendation learning; capacity-only screening is not safety evidence.
- Promote a candidate only as a new version after review of its held-out results. Keep rollback to the previous release.

## Scope
Current interactive prediction inputs are not, by themselves, labeled training outcomes. Laboratory-cell evidence does not establish EV-pack or field validation. Second-life suggestions remain preliminary capacity screens until supported by independent engineering and reuse outcomes.
