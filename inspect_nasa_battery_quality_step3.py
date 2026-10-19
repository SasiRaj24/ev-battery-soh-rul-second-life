from pathlib import Path
from scipy.io import loadmat
import numpy as np

folder = Path("data/nasa")

for name in ["B0005", "B0006", "B0007", "B0018"]:
    print(f"\n=== {name} ===")
    path = folder / f"{name}.mat"

    try:
        root = loadmat(
            str(path), squeeze_me=True, struct_as_record=False
        )[name]
        cycles = np.atleast_1d(root.cycle)
        discharge = [
            c for c in cycles
            if str(c.type).strip().lower() == "discharge"
        ]

        capacities = []
        temperatures = []
        voltage_mins = []
        missing_capacity = 0
        missing_voltage = 0
        measurement_lengths = []

        for c in discharge:
            data = c.data

            try:
                cap = float(np.asarray(data.Capacity).squeeze())
                if np.isfinite(cap):
                    capacities.append(cap)
                else:
                    missing_capacity += 1
            except (AttributeError, TypeError, ValueError):
                missing_capacity += 1

            try:
                temp = float(np.asarray(c.ambient_temperature).squeeze())
                if np.isfinite(temp):
                    temperatures.append(temp)
            except (AttributeError, TypeError, ValueError):
                pass

            try:
                voltage = np.asarray(data.Voltage_measured, dtype=float)
                voltage = voltage[np.isfinite(voltage)]
                if voltage.size:
                    voltage_mins.append(float(voltage.min()))
                    measurement_lengths.append(voltage.size)
                else:
                    missing_voltage += 1
            except (AttributeError, TypeError, ValueError):
                missing_voltage += 1

        print("Discharge records:", len(discharge))
        print("Valid capacity values:", len(capacities))
        print("Missing/invalid capacities:", missing_capacity)
        print("Missing/invalid voltage records:", missing_voltage)

        if capacities:
            rises = sum(
                capacities[i] > capacities[i - 1]
                for i in range(1, len(capacities))
            )
            print("Capacity range (Ah):",
                  round(min(capacities), 4), "to",
                  round(max(capacities), 4))
            print("Capacity increases between adjacent records:", rises)

        if temperatures:
            print("Ambient temperature range (°C):",
                  min(temperatures), "to", max(temperatures))

        if voltage_mins:
            print("Minimum measured voltage across discharges (V):",
                  round(min(voltage_mins), 4))
            print("Maximum of discharge minimum voltages (V):",
                  round(max(voltage_mins), 4))

        if measurement_lengths:
            print("Voltage samples per discharge (min/max):",
                  min(measurement_lengths), "/",
                  max(measurement_lengths))

    except Exception as e:
        print("INSPECTION ERROR:", type(e).__name__, str(e))