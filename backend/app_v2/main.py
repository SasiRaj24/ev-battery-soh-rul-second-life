from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import service


app = FastAPI(
    title="EV Battery AI — SOH, RUL and Second-Life Research API",
    description=(
        "Experimental, versioned battery-cell analyses. Capacity screening is "
        "heuristic; no route certifies an EV pack or battery for reuse."
    ),
    version="2.0.0-experimental",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174", "http://127.0.0.1:5174",
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5176", "http://127.0.0.1:5176",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class BatteryParameters(BaseModel):
    dataset_source: Literal["NASA", "Oxford", "CALCE_CS2"] = "NASA"
    reference_capacity_Ah: float = Field(gt=0, le=1000)
    previous_cycle_number: int = Field(ge=0)
    previous_capacity_Ah: float = Field(gt=0, le=1000)
    current_cycle_number: int = Field(ge=2)
    current_capacity_Ah: float = Field(gt=0, le=1000)
    ambient_temperature_C: float = Field(default=25.0, ge=-80, le=150)
    forecast_cycle_number: int | None = Field(default=None, ge=2)
    compatible_with_nasa_rul_scope: bool = False


class CollectiveBatteryParameters(BaseModel):
    reference_capacity_Ah: float = Field(gt=0, le=1000)
    previous_cycle_number: int = Field(ge=0)
    previous_capacity_Ah: float = Field(gt=0, le=1000)
    current_cycle_number: int = Field(ge=1)
    current_capacity_Ah: float = Field(gt=0, le=1000)
    forecast_cycle_number: int | None = Field(default=None, ge=2)


@app.get("/api/v2/health")
def health() -> dict:
    return {
        "status": "healthy",
        "api_version": app.version,
        "models_ready": service.models_ready(),
    }


@app.get("/api/v2/models")
def models() -> dict:
    return service.model_manifest()


@app.get("/api/v2/datasets")
def datasets() -> dict:
    return service.dataset_catalog()


@app.get("/api/v2/validation/soh")
def soh_validation() -> dict:
    return service.soh_validation()


@app.get("/api/v2/validation/rul")
def rul_validation() -> dict:
    return service.rul_validation()


@app.get("/api/v2/validation/research")
def research_validation() -> dict:
    return service.research_evaluation()


@app.post("/api/v2/analyze/csv")
async def analyze_csv(request: Request) -> dict:
    raw = await request.body()
    frame = service.parse_history_csv(raw)
    compatible = request.query_params.get("compatible_with_nasa_rul_scope", "false").lower() == "true"
    return service.analyze_history(frame, compatible_with_nasa_rul_scope=compatible)


@app.post("/api/v2/analyze/parameters")
def analyze_parameters(parameters: BatteryParameters) -> dict:
    return service.analyze_parameters(parameters.model_dump())


@app.post("/api/v2/analyze/collective")
def analyze_collective(parameters: CollectiveBatteryParameters) -> dict:
    return service.analyze_collective_parameters(parameters.model_dump())
