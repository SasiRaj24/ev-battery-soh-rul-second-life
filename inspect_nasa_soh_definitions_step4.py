from pathlib import Path
from scipy.io import loadmat
import numpy as np

folder = Path("data/nasa")

print("Exploratory SOH comparison; no files will be modified.")
print("Rated-capacity reference: 2.0 Ah")
print("Threshold reference: 1.4 Ah")
print("SOH values are calculated from recorded discharge capacity.\n")

for name in ["B0005", "B0006", "B0007", "B0018"]:
    root = loadmat(
        str(folder / f"{name}.mat"),
        squeeze_me=True,
        struct_as_record=False
    )[name]

    cycles = np.atleast_1d(root.cycle)
    discharge = [
        c for c in cycles
        if str(c.type).strip().lower() == "discharge"
    ]
    capacities = np.array([
        float(np.asarray(c.data.Capacity).squeeze())
        for c in discharge
    ])

    relative_soh = capacities / capacities[0] * 100
    rated_percent = capacities / 2.0 * 100
    below = np.flatnonzero(capacities < 1.4)

    print(f"=== {name} ===")
    print(f"First capacity: {capacities[0]:.4f} Ah")
    print(f"Last capacity: {capacities[-1]:.4f} Ah")
    print(f"Last relative SOH: {relative_soh[-1]:.2f}%")
    print(f"Minimum relative SOH: {relative_soh.min():.2f}%")
    print(f"Last capacity as percentage of 2 Ah: {rated_percent[-1]:.2f}%")

    if len(below):
        print(f"First recorded capacity below 1.4 Ah: discharge record {below[0] + 1}")
    else:
        print("No recorded capacity below 1.4 Ah")

    print()