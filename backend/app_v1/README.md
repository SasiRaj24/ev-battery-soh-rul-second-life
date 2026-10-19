# Research API v1

This versioned, read-only API serves the generated NASA cell validation artifacts. It does not replace or modify the original `backend/main.py`.

From the project root, start it with the existing environment:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app_v1.main:app
```

Routes:

- `GET /api/v1/health`
- `GET /api/v1/validation/summary`
- `GET /api/v1/validation/folds`
- `GET /api/v1/validation/batteries/{B0005|B0006|B0007|B0018}/predictions?model=persistence|linear_regression|xgboost`
- `GET /api/v1/models`

Model deployment is intentionally not enabled. Leave-one-battery-out fold models were not saved as production artifacts. A later version can add a versioned model manifest and inference adapter to `ModelRegistry` without changing the research-results routes.
