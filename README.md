# EV Battery SOH, RUL and Second-Life Research Dashboard

**AI-Based State of Health and Remaining Useful Life Prediction for EV Batteries with Second-Life Recommendation**

This repository contains the React dashboard, FastAPI research API, versioned model artifacts, evaluation reports, processed evidence, and original NASA, Oxford, and CALCE cell datasets. Original datasets are stored with Git LFS.

## Scientific scope

This is a laboratory-cell research prototype. It does not establish EV battery-pack or field validation and does not certify battery safety or second-life suitability. RUL is reported only where supported by the NASA study endpoint; the second-life result is a capacity-based screening assumption requiring engineering assessment. See [PROJECT_OVERVIEW_v2.md](PROJECT_OVERVIEW_v2.md) and `reports/` for measured results, assumptions, and limitations.

## Run locally

Use [RUNNING_LOCAL_APP_v2.md](RUNNING_LOCAL_APP_v2.md) to start the local FastAPI API and React dashboard.

## Deploy the full-stack app

The dashboard and API are served together from one Render web service. Select **Deploy to Render** below, sign in to Render, review the service configuration, and approve deployment. The free service sleeps after 15 minutes without requests, so its first request after idling may take longer to respond.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/SasiRaj24/ev-battery-soh-rul-second-life)

The service builds from `Dockerfile` and uses the `render.yaml` blueprint. Raw datasets are not copied into the running container; the backend loads the specific versioned models and processed evaluation files it needs.
