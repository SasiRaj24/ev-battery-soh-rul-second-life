from pydantic import BaseModel, Field
from fastapi import FastAPI

app = FastAPI(
    title="EV Battery AI",
    description="AI-powered EV battery health and second-life assessment",
    version="0.1.0",
)


@app.get("/")
def home():
    return {
        "message": "EV Battery AI backend is running",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "project": "EV Battery AI",
    }

class BatteryInput(BaseModel):
    battery_id: str = Field(min_length=1, max_length=50)
    nominal_capacity_kwh: float = Field(gt=0)
    measured_capacity_kwh: float = Field(gt=0)
    voltage_v: float = Field(gt=0)
    temperature_c: float = Field(ge=-50, le=100)
    charge_cycles: int = Field(ge=0)


@app.post("/battery/analyze")
def analyze_battery(battery: BatteryInput):
    capacity_retention = (
        battery.measured_capacity_kwh
        / battery.nominal_capacity_kwh
    ) * 100

    return {
        "battery_id": battery.battery_id,
        "capacity_retention_percent": round(capacity_retention, 2),
        "battery_data": battery.model_dump(),
        "prediction_status": "not_predicted",
        "message": (
            "Battery data validated successfully. "
            "A trained AI model is not connected yet."
        ),
    }
