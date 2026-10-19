# AI-Based State of Health and Remaining Useful Life Prediction for EV Batteries with Second-Life Recommendation

## Project status

This project continues the existing B0005 work and adds versioned cross-cell validation, experimental RUL modeling, local inference, CSV upload, prediction explanation, and preliminary second-life screening. Existing source datasets and B0005 artifacts are preserved.

## Implemented components

- **SOH validation:** leave-one-battery-out comparison for B0005, B0006, B0007, and B0018; one-step next-discharge target; persistence, linear regression, and XGBoost.
- **RUL validation:** separate leave-one-battery-out analysis to the NASA study's 1.4 Ah measured-capacity threshold. B0005, B0006, and B0018 cross it; B0007 is right-censored and is not assigned an artificial failure point.
- **Versioned models:** `models/nasa_model_manifest_v2.json` records model artifacts, input feature order, training cells, and limitations.
- **FastAPI v2:** health and metadata, validation summaries, and CSV-history analysis for SOH, RUL, and a capacity-based second-life screen.
- **React v2:** validation dashboard, endpoint censoring view, CSV upload, SOH trajectory chart, additive linear-model terms, RUL estimate, and screening category.

## Results and interpretation

SOH held-cell validation gives pooled MAE 0.5574 percentage points for persistence, 0.5924 for linear regression, and 1.3088 for XGBoost. Therefore the learned SOH model is shown beside persistence and is not described as the best predictor.

For RUL, XGBoost gives pooled MAE 11.6707 cycles and RMSE 13.6480 cycles across the three complete held-out cells. Each fold trains on only two independent cells. This is exploratory evidence with substantial cell-to-cell uncertainty, not a field-ready RUL guarantee.

The 1.4 Ah threshold comes from this NASA dataset's 70%-of-2-Ah EOL convention. It is not used as a universal second-life rule. The dashboard's 70% and 80% screening bands are explicit project assumptions. The screen asks for further electrical, impedance/DC resistance, physical, thermal, cell-matching, BMS, and pack engineering review; it cannot determine safety or certify a reuse application. A broader second-life assessment procedure considers operating context and battery condition beyond capacity alone ([NREL assessment procedure](https://www.nrel.gov/docs/fy22osti/84527.pdf); [SOH under real-profile operation](https://doi.org/10.1016/j.apenergy.2022.119992)).

All underlying measurements are NASA accelerated-aging laboratory **cell** data. The project does not claim EV battery-pack or field validation. Additional independent cells, pack-level data, safety measurements, and application-specific testing remain future work.

## Run the application

Use [RUNNING_LOCAL_APP_v2.md](RUNNING_LOCAL_APP_v2.md). Run the v2 API with `.venv` and launch the v2 dashboard with its `.cmd` launcher. The upload API expects `cycle_number`, `discharge_capacity_Ah`, and `ambient_temperature_C` columns.

## Key artifacts

- SOH validation: `data/processed/nasa_cross_battery_v1/`
- RUL validation: `data/processed/nasa_rul_v2/`
- RUL and screening methodology: `reports/nasa_rul_secondlife_v2.md`
- Versioned model files: `models/nasa_*_v2.joblib` and `models/nasa_model_manifest_v2.json`
- API: `backend/app_v2/`
- Web app: `frontend_v2/`
