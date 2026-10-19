# Five-priority implementation status — 2026-10-18

This note records the current state of the research project and the limits of the available evidence. Existing datasets, model artifacts, prediction outputs, and earlier reports remain preserved. The current inference default remains model release `2.0.0-experimental`.

## 1. Cell-level evaluation, per-cell spread, and censoring

The new evaluation addendum reports equal-weight macro MAE and each cell's observed MAE range. That range is descriptive, not a confidence interval; the independent-cell sample is too small for dependable population uncertainty. NASA SOH linear regression (macro-cell MAE 0.5955 percentage points) does not beat persistence (0.5686). NASA RUL XGBoost is 11.5078 cycles macro-cell MAE on three complete held-out cells. B0007 remains right-censored above the 1.4 Ah study endpoint. A survival model and calibrated prediction interval remain unsupported at this sample size.

## 2. Cross-battery and cross-dataset evaluation

NASA B0005/B0006/B0007/B0018 and the two extra four-cell NASA groups have separate within-group held-cell evaluations. Oxford's eight cells have separate within-Oxford results. None is a pooled cross-family transfer result. The main NASA model is not represented as validated on Oxford or CALCE.

CALCE CS2's cumulative discharge-capacity statistic and overlapping, resetting workbook cycle indices require reconstruction. Inspection across all Statistics sheets observed 50 duplicate timestamps in CS2_35 and 50 in CS2_38. Capacity also has decreases after chronological ordering for each cell: CS2_3 (16), CS2_9 (21), CS2_33 (11), CS2_34 (13), CS2_35 (13), CS2_36 (13), CS2_37 (14), and CS2_38 (14). These discontinuities mean chronological sorting alone does not establish a continuous trajectory; no CALCE error score is reported. CALCE PL11/PL13 remain pending a MATLAB-table-aware parser.

## 3. RUL endpoint and model scope

RUL training/validation uses recorded NASA discharge observations up to first capacity at or below 1.4 Ah. B0007 is censored for that endpoint. Manual and CSV analyses withhold RUL unless the user asserts a compatible NASA-like single-cell protocol and identical endpoint. This is an assertion, not an automated protocol check. Relative or user-specific RUL thresholds require new labels and independent validation.

## 4. Second-life assessment

The dashboard presents a capacity-only pre-screen with explicit project-assumption bands. The API marks engineering assessment as required and returns no application recommendation. Power capability, resistance/impedance, thermal behavior, physical/electrical condition, cell matching, BMS, and pack integration are not measured by the current inputs. No safety, reuse, pack, or field suitability is inferred.

## 5. Reproducible training and model versioning

`train_nasa_models_v3.py` writes a new experimental release beneath `models/releases/<version>/` using exclusive creation and records source/script/artifact hashes, package versions, features, parameters, training cells, and endpoint/censoring details. It does not overwrite v2 and has not been run; v2 remains the default. The API can select a manifest under `models/` via `EV_BATTERY_MODEL_MANIFEST`; restart the API after changing that environment variable. Artifact paths are constrained to the local models directory, optional artifact hashes are checked, and a newly selected release is reloaded by path.

## Current runnable stack

- Backend: FastAPI v2, served at `http://127.0.0.1:8000`.
- Dashboard: React/Vite v2, served at `http://127.0.0.1:5176`.
- The browser dashboard uses typed capacity and cycle inputs; CSV history remains optional.
- Production assets were built to the new directory `frontend_v2/dist_priorities_v5_20261018/`.

## Remaining research work

1. Reconstruct CS2 workbook sessions with documented source semantics before producing a continuous trajectory or external score.
2. Parse CALCE PL11/PL13 table records and audit units, timestamps, and cell identity.
3. Seek more independent cells and report calibrated uncertainty only when the data support it.
4. Validate RUL at independent, explicitly defined endpoints and across compatible cell protocols.
5. Treat second-life recommendations as future engineering work requiring power, impedance, thermal, safety, and application-specific evidence.
6. Collect EV-pack/field data before making any pack-level claim.

All scores to date are laboratory-cell results. They do not establish real-world EV battery-pack validation.
