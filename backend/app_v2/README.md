# Research API v2

This version adds experimental model inference and capacity-based screening while preserving `backend/main.py` and `backend/app_v1`.

Start from the project root using the existing environment:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app_v2.main:app
```

Routes:

- `GET /api/v2/health`
- `GET /api/v2/models`
- `GET /api/v2/validation/soh`
- `GET /api/v2/validation/rul`
- `POST /api/v2/analyze/csv` with a CSV request body
- `POST /api/v2/analyze/parameters` with `reference_capacity_Ah`, `previous_cycle_number`, `previous_capacity_Ah`, `current_cycle_number`, `current_capacity_Ah`, and `ambient_temperature_C` as JSON fields
- `POST /api/v2/analyze/collective` with reference capacity and two measured cycle/capacity checkpoints; returns capacity-derived current SOH, a two-point trend baseline, and capacity-only second-life screening alongside cross-dataset validation evidence

CSV headers must include `cycle_number,discharge_capacity_Ah,ambient_temperature_C` and contain at least two chronological, numeric discharge records. The API does not require `python-multipart`; the browser sends the file's text as a raw request body.

The dashboard's primary analysis path accepts typed measurements: an explicit reference capacity plus the previous and current measured discharge records. Cycle numbers must increase, and capacities must be positive. The CSV route remains available as an optional history-based path. Typed values are treated as user-entered measurements; the API does not verify their provenance.

Models are versioned in `models/nasa_model_manifest_v2.json`. `joblib` artifacts are local trusted project files and should only be loaded from this workspace. Inference is experimental; RUL is tied to the NASA 1.4 Ah threshold and the second-life bands are project screening assumptions. Neither model nor screen is certified for field or pack use.

The collective endpoint intentionally does not blend the source-specific AI artifacts. Cell-held-out comparison found negative transfer for some families (notably Oxford), so current SOH is calculated from the entered capacity reference and the next-checkpoint value is a transparent two-point linear baseline. It is not a trained pooled model; collective RUL is withheld. The included NASA, Oxford, and CALCE evidence remains laboratory-cell evidence and does not establish EV-pack validation.
