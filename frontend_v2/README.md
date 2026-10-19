# Research dashboard v2

This version provides source-specific typed battery analysis, optional history CSV upload, experimental RUL estimates, validation folds, and a separate collective evidence assessment with a capacity-only second-life screening category.

Start from the project root with `& .\frontend_v2\start-dashboard-v2.cmd`. Vite uses port 5176. The v2 API must be running at `http://127.0.0.1:8000`.

For source-specific analysis, enter the measured SOH reference capacity, previous and current cycle numbers and discharge capacities, and ambient temperature where required. Cycle numbers must increase and capacities must be positive. CSV input remains available as an optional alternative with headers `cycle_number,discharge_capacity_Ah,ambient_temperature_C`. Entered and uploaded data is analyzed only; it is not added to model training.

The Collective assessment tab presents evidence from NASA, Oxford, and CALCE comparisons. Because pooled models showed negative transfer in held-out-family evaluation, its typed-input forecast is explicitly a two-point trend baseline rather than a pooled AI result. RUL is withheld in that mode. Second-life output is a low-confidence capacity screen only.

All recommendations are preliminary project heuristics, not safety or certification decisions. RUL is tied to the NASA study's 1.4 Ah cell threshold and has low confidence.
