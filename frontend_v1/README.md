# Cellscope research dashboard v1

React dashboard for the four-cell NASA leave-one-battery-out evaluation. It plots measured next-discharge SOH beside the selected held-out fold prediction, shows pooled model scores and per-cell persistence errors, and labels the laboratory-cell scope.

The dashboard uses the versioned read-only API in `backend/app_v1`. Set `VITE_API_BASE_URL` to the API base if it is not `http://127.0.0.1:8000/api/v1`.

Dependencies are installed and locked in `pnpm-lock.yaml`. The production bundle was generated in `dist/`. From the project root, run `& .\frontend_v1\start-dashboard.cmd` to start the development server. The command launcher adds the bundled Node.js runtime to PATH before invoking pnpm and does not require PowerShell script execution permissions.
