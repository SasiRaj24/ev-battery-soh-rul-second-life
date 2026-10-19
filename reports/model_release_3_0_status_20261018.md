# Model release 3.0.0-experimental — status addendum

This addendum supplements `project_five_priorities_status_v5_20261018.md`: after that note was written, `train_nasa_models_v3.py --version 3.0.0-experimental` completed successfully.

- New release: `models/releases/3.0.0-experimental/manifest.json`
- Release status: `experimental_not_default`
- SOH estimator: linear regression, 628 rows from B0005, B0006, B0007, B0018.
- RUL estimator: XGBoost, 328 rows from B0005, B0006, B0018; endpoint is first measured capacity at or below 1.4 Ah; B0007 is recorded as censored and excluded.
- The manifest contains source, training-script, and artifact SHA-256 hashes, package versions, feature order, parameters, and limitations.
- Existing `nasa_*_v2.joblib` artifacts and manifest were not overwritten. API default remains v2.
- The API can select the new release by `EV_BATTERY_MODEL_MANIFEST`; selection is opt-in. Loading was verified in a separate Python process with hash checks active.

Validation evidence still comes from the separate held-cell studies; the final-fit release itself is not a held-out estimator and does not establish external, field, or pack validation.
