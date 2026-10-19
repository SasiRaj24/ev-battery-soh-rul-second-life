# Run the SOH, RUL and second-life research app (v2)

Open two PowerShell terminals at the project root.

## API

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app_v2.main:app
```

The API listens on `http://127.0.0.1:8000`; interactive docs are at `http://127.0.0.1:8000/docs`. Stop any v1 API already using port 8000 before starting v2.

## Dashboard

```powershell
& .\frontend_v2\start-dashboard-v2.cmd
```

Open `http://localhost:5176`. The launcher sets PATH to Codex's bundled Node runtime and avoids PowerShell execution-policy restrictions.

The analysis view accepts typed measurements: reference capacity, previous and current cycle numbers and discharge capacities, and ambient temperature. CSV upload remains optional. Analysis returns next-discharge SOH, an experimental RUL estimate, an additive linear-model explanation, and a preliminary second-life screening category.

## Research limits

RUL is defined as discharges until measured capacity first reaches 1.4 Ah. Only B0005, B0006, and B0018 cross this threshold; B0007 is right-censored. The second-life bands are project assumptions and capacity-only; they do not establish safety, certification, vehicle-pack performance, or application suitability.
