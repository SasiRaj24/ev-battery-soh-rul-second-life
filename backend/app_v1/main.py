from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import service
from .registry import ModelRegistry
from .schemas import HealthResponse, ModelStatus


app = FastAPI(
    title="EV Battery AI — Research API",
    description=(
        "Read-only access to NASA laboratory-cell cross-battery evaluation. "
        "The API does not claim EV pack validation or expose a deployed model."
    ),
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
model_registry = ModelRegistry()


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    available = (service.ARTIFACT_DIR / "nasa_cross_battery_v1_summary.json").is_file()
    return HealthResponse(
        status="healthy",
        api_version="v1",
        validation_data_available=available,
    )


@app.get("/api/v1/validation/summary")
def validation_summary() -> dict:
    return service.get_summary()


@app.get("/api/v1/validation/folds")
def validation_folds() -> list[dict]:
    return service.get_fold_metrics()


@app.get("/api/v1/validation/batteries/{battery_id}/predictions")
def battery_predictions(battery_id: str, model: str = "persistence") -> list[dict]:
    return service.get_predictions(battery_id, model)


@app.get("/api/v1/models", response_model=list[ModelStatus])
def models() -> list[ModelStatus]:
    return model_registry.list_status()
