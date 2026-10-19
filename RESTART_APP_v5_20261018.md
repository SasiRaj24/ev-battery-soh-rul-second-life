# Restart instructions for the updated research dashboard

The dashboard source is already hot-reloading on `http://127.0.0.1:5176/`. The API process currently serving port 8000 predates the new `/api/v2/validation/research` route, so the cell-macro SOH/RUL metrics are deliberately shown as unavailable until that process is restarted.

In the PowerShell terminal where the API is running, press `Ctrl+C`, then start it again from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app_v2.main:app --host 127.0.0.1 --port 8000
```

Refresh the dashboard at `http://127.0.0.1:5176/`. The overview should then show the 4-cell SOH macro MAE, 3-cell RUL macro MAE, and per-cell SOH comparison against persistence. `GET /api/v2/validation/research` serves the underlying summary.

The default stays at `2.0.0-experimental`. A newly fitted `3.0.0-experimental` release is available under `models/releases/3.0.0-experimental/manifest.json` but is explicitly not the default. To select it for a separate API run, set the manifest before starting Uvicorn:

```powershell
$env:EV_BATTERY_MODEL_MANIFEST = 'models/releases/3.0.0-experimental/manifest.json'
.\.venv\Scripts\python.exe -m uvicorn backend.app_v2.main:app --host 127.0.0.1 --port 8000
```

Use the v3 manifest only for research comparison. Its models are newly fitted on all eligible NASA training cells; their displayed validation evidence remains the separate held-out evaluation, not predictions from these final-fit artifacts.
