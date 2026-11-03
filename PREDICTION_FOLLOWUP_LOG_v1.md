# Prediction and Follow-up Log v1

## Purpose

The dashboard can save a source-specific typed SOH prediction together with the measured inputs, cell identifier, dataset family, model release, conditions, and measurement provenance. Later measurements can be linked to that prediction for review.

This is a data collection and evaluation aid. Saving a record or follow-up never trains, replaces, or promotes a model.

## Storage and privacy

- Records are stored in browser `localStorage` under `ev-battery-ai.learning-log.v1`.
- The log stays in that browser profile on that device and origin. It is not uploaded to the FastAPI server and is not shared between the local dashboard and the Render URL.
- Export the log as JSON to keep a backup or move it to a separate, reviewed analysis workflow. Browser storage can be lost if the user clears site data.
- The app does not offer a destructive clear-log action. If saved JSON is malformed or browser storage is unavailable, new writes are blocked or reported as failed rather than silently replacing it.

## Captured record

Each prediction includes a generated record ID, creation time, cell ID, dataset family, provenance, optional test conditions, model release and model version, model name, exact typed input payload, predicted SOH, target cycle, optional RUL estimate and endpoint description, second-life screening code, and an initially empty list of follow-ups.

Follow-ups retain measurement cycle, measured discharge capacity, relative SOH based on the prediction's original reference capacity, provenance, and an SOH error only when the observation is at the predicted target cycle. Measurements at a different cycle remain available but are not scored as the direct forecast outcome.

The log can also capture a reviewer-reported second-life assessment linked to the prediction. It requires an intended application, reviewer/role, disposition, and evidence/report provenance; optional notes can summarize power, impedance, thermal, isolation, cell-matching, or BMS checks. These entries preserve engineering review outcomes as a separate data type. They are not verified by the app, do not imply safety certification, and are not used to train a recommendation model.

For optional RUL outcomes, a capacity above the explicitly entered endpoint is stored as right-censored at that observation. A capacity at or below the endpoint is labeled a threshold crossing only after the user confirms it is the first recorded crossing. The reported remaining cycles refer to the first observed threshold-crossing cycle, not an unobserved continuous failure time. An endpoint-free follow-up is SOH-only.

## Current scope and next steps

Version 1 saves source-specific typed predictions from **Analyze a battery**. CSV and collective-assessment outputs are not currently captured. These records must be reviewed before use as a training dataset. Any future candidate training should split by whole cell, report dataset-family results separately, compare against the current release and persistence baselines, and require explicit review before promotion. Second-life model learning remains out of scope until documented application assessments and outcomes exist.
