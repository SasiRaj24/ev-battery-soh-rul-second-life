# NASA cell RUL and second-life screening (v2)

## Scope and label

Remaining useful life (RUL) is defined here as the number of subsequent valid discharge records until the first measured capacity at or below **1.4 Ah**. This is the 70%-of-2-Ah nominal-capacity EOL criterion described in the local NASA dataset README. It is a study label for this laboratory dataset, not a universal EV or second-life threshold.

B0005, B0006, and B0018 cross that threshold in the recorded files. B0007 ends at 1.4325 Ah without crossing it, so its RUL is **right-censored**: its threshold-crossing RUL is unknown and exceeds the 168 observed discharge records. B0007 is excluded from RUL model scoring/training rather than assigned an invented endpoint.

## Measured cross-cell RUL results

Leave-one-battery-out evaluation across the three complete trajectories trains each fold on two cells and evaluates the third. Features are available through the current discharge. The model's target uses the complete held-out trajectory only to identify its retrospective threshold-crossing label.

| Held-out cell | XGBoost MAE (cycles) | XGBoost RMSE (cycles) |
|---|---:|---:|
| B0005 | 15.0603 | 16.4233 |
| B0006 | 7.6702 | 9.9463 |
| B0018 | 11.7928 | 13.2939 |
| Pooled cell-held-out rows | 11.6707 | 13.6480 |

The linear model performed poorly overall (pooled MAE 1,007.65 cycles) and simple recent-slope extrapolation was unstable (pooled MAE 589.76, RMSE 9,163.39 cycles). These results show why the dashboard presents the held-out-cell XGBoost score with its small-cell sample caveat and does not select the trend baseline as an operational RUL method. A zero-error `cycle_index_oracle_control` is included in the raw validation output only as an identity/control column; it uses the true target and is not a predictor or candidate model.

The RUL study has only three independent complete cells, with two independent training cells per fold. Many within-cell cycle rows do not create a larger independent-cell sample. Do not interpret these metrics as robust generalization evidence.

## Versioned inference artifacts

`models/nasa_soh_linear_v2.joblib` and `models/nasa_rul_xgboost_v2.joblib` are final fit artifacts for experimental local inference. The SOH model uses all four NASA cells; the RUL model uses B0005, B0006 and B0018. The validation metrics above are from separate leave-one-cell-out fits, not from the all-cell artifacts. The manifest is `models/nasa_model_manifest_v2.json`.

SOH inference predicts one next recorded discharge. The API also returns persistence as a comparator and additive linear-model terms as an explanation. These feature terms are a mathematical decomposition of the fitted model, not causal explanations. RUL output is a point estimate with low confidence and no calibrated prediction interval.

## Second-life screening output

The application reports a **preliminary capacity-based screening category** using explicit project assumptions: at least 80% relative SOH, 70–80%, or below 70%. These cutoffs are not represented as universal industry rules, safety criteria, or a certification decision. The NASA 1.4 Ah label is a dataset EOL criterion; it is separate from the second-life screen.

Capacity alone cannot establish suitability or safety. Before any reuse decision, the project flags the need for independent capacity/power checks, impedance or DC resistance assessment, physical and electrical isolation inspection, thermal characterization under the intended duty cycle, cell matching, and BMS/pack compatibility. NREL's second-life assessment procedure considers operating context and broader battery condition, while second-life SOH studies emphasize assessment under realistic operating profiles ([NREL procedure](https://www.nrel.gov/docs/fy22osti/84527.pdf), [real-profile SOH study](https://doi.org/10.1016/j.apenergy.2022.119992)).

The uploaded-data screen is an educational research aid only. It does not certify cells, prescribe a reuse application, or establish real-world EV-pack performance.

## Reproducible artifacts

- Validation: `data/processed/nasa_rul_v2/`
- Validation code: `validate_nasa_rul_v2.py`
- Training code: `train_nasa_models_v2.py`
- API/dashboard implementation: `backend/app_v2/` and `frontend_v2/`
- Raw NASA MAT files and pre-existing B0005 artifacts remain preserved.
