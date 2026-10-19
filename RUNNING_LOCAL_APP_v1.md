# Run the local research app (v1)

Open two PowerShell terminals at the project root.

## API

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app_v1.main:app
```

The API listens on `http://localhost:8000`. Its interactive route documentation is at `http://localhost:8000/docs`.

## Dashboard

The development machine has bundled Node.js and pnpm, but neither is on the regular shell PATH. From the project root, run the `.cmd` launcher; PowerShell execution policy does not block it:

```powershell
& .\frontend_v1\start-dashboard.cmd
```

Then open `http://localhost:5173`. The API must be running for the dashboard to load validation metrics and predictions. The API allows the local Vite origin.

The launcher sets PATH for its own process before pnpm starts Vite. For a production bundle, prepend the bundled Node.js `node\bin` directory to PATH before running pnpm.

```powershell
& 'C:\Users\sasir\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd' --dir .\frontend_v1 run build
```

## Scope

The API and dashboard display next-discharge SOH validation for four NASA accelerated-aging laboratory cells. The app has no deployed inference model and does not represent real-world EV battery-pack validation.
