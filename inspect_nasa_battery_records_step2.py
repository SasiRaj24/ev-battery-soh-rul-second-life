from pathlib import Path
from scipy.io import loadmat
import numpy as np

folder = Path("data/nasa")

for name in ["B0005", "B0006", "B0007", "B0018"]:
    print(f"\n=== {name} ===")
    try:
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

        print("Total records:", len(cycles))
        print("Discharge records:", len(discharge))
        print("Cycle fields:", cycles[0]._fieldnames)

        if discharge:
            data = discharge[0].data
            print("Discharge data fields:", data._fieldnames)
            print("First capacity (Ah):",
                  float(np.asarray(data.Capacity).squeeze()))
            print("Last capacity (Ah):",
                  float(np.asarray(discharge[-1].data.Capacity).squeeze()))

    except Exception as e:
        print("INSPECTION ERROR:", type(e).__name__, str(e))