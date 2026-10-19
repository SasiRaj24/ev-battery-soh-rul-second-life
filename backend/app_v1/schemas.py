from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    api_version: str
    validation_data_available: bool


class ModelStatus(BaseModel):
    model: str
    role: str
    deployed: bool
    details: str
