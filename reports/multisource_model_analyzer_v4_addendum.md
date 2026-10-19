# Multi-source analyzer implementation addendum

The Analyze Battery typed-input form now lets the user select NASA, Oxford, or CALCE CS2. It routes SOH only to the selected source-family model. The Oxford form asks for the next scheduled checkpoint cycle. Ambient temperature is collected only for NASA because the harmonized Oxford/CALCE models were not trained on that feature.

RUL remains available only through the existing NASA path and is withheld for Oxford/CALCE. Second-life output remains a capacity-only research screen, not a safety or certification decision.

For Oxford and CALCE, the API checks typed features against observed source-family training support and checks the projected next-record SOH change against the training 1st–99th percentile range. It withholds an unsupported model estimate and shows persistence as a reference instead. CALCE model performance remains effectively tied with persistence in six-cell held-out validation; this model is included for a source-specific research comparison, not because improvement was demonstrated.

The NASA inference artifacts were not replaced. The active release manifest reports the multisource bundle version; the NASA SOH artifact itself remains version 2.0.0-experimental. Oxford and CALCE artifacts are versioned and hash-checked inside `models/releases/4.0.0-multisource-experimental/`.

The local dashboard is served at `http://127.0.0.1:5176/` and the updated API at `http://127.0.0.1:8001/`. The React production build and Python syntax compilation completed successfully. No EV battery-pack or field validation is claimed.
