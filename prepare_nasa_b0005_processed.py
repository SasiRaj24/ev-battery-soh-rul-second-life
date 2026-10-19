
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat


def main():
    source = Path("data/nasa/B0005.mat")
    output_dir = Path("data/processed/nasa_b0005")
    csv_path = output_dir / "nasa_b0005_discharge_cycles.csv"
    summary_path = output_dir / "nasa_b0005_processing_summary.json"

    # Check all output conflicts before processing or writing.
    targets = [csv_path, summary_path]
    conflicts = [str(path) for path in targets if path.exists()]
    if conflicts:
        raise FileExistsError(
            "Nothing was written. These output files already exist: "
            + ", ".join(conflicts)
        )

    if not source.is_file():
        raise FileNotFoundError(f"NASA B0005 source file not found: {source}")

    print(f"Reading source: {source}")
    mat = loadmat(source, simplify_cells=True)
    events = mat["B0005"]["cycle"]

    rows = []

    for event_number, event in enumerate(events, start=1):
        if event.get("type") != "discharge":
            continue

        data = event.get("data", {})
        if "Capacity" not in data:
            continue

        capacity = float(np.asarray(data["Capacity"]).reshape(-1)[0])

        if not np.isfinite(capacity) or capacity <= 0:
            continue

        rows.append({
            "battery_id": "B0005",
            "event_number": event_number,
            "cycle_number": len(rows) + 1,
            "ambient_temperature_C": float(
                event.get("ambient_temperature", np.nan)
            ),
            "discharge_capacity_Ah": capacity,
        })

    if len(rows) < 2:
        raise ValueError(
            f"Expected multiple valid discharge events; found {len(rows)}."
        )

    df = pd.DataFrame(rows)
    initial_capacity = float(df["discharge_capacity_Ah"].iloc[0])

    df["soh_percent"] = (
        df["discharge_capacity_Ah"] / initial_capacity
    ) * 100.0

    df["capacity_decline_percent"] = 100.0 - df["soh_percent"]

    summary = {
        "dataset": "NASA Battery B0005",
        "source_file": str(source),
        "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": (
            "SOH (%) = discharge capacity / first recorded "
            "discharge capacity * 100"
        ),
        "soh_reference_capacity_Ah": initial_capacity,
        "valid_discharge_events": int(len(df)),
        "first_discharge_capacity_Ah": float(
            df["discharge_capacity_Ah"].iloc[0]
        ),
        "last_discharge_capacity_Ah": float(
            df["discharge_capacity_Ah"].iloc[-1]
        ),
        "last_recorded_soh_percent": float(df["soh_percent"].iloc[-1]),
        "capacity_decline_percent": float(
            df["capacity_decline_percent"].iloc[-1]
        ),
        "rul_label_created": False,
        "notes": [
            "Original MAT file is read only.",
            "SOH uses the first recorded discharge capacity as its baseline.",
            "This baseline is not necessarily the manufacturer's rated capacity.",
            "RUL is not calculated in this processing step.",
        ],
    }

    # Create the output folder only after the source is successfully processed.
    output_dir.mkdir(parents=True, exist_ok=True)

    # Recheck conflicts immediately before writing.
    conflicts = [str(path) for path in targets if path.exists()]
    if conflicts:
        raise FileExistsError(
            "An output appeared before writing. Nothing will be overwritten: "
            + ", ".join(conflicts)
        )

    # Exclusive creation ('x') refuses to overwrite an existing file.
    try:
        with csv_path.open("x", encoding="utf-8", newline="") as file:
            df.to_csv(file, index=False)

        with summary_path.open("x", encoding="utf-8") as file:
            json.dump(summary, file, indent=2)

    except Exception:
        print("Writing was interrupted. Check the output paths before retrying.")
        print(f"CSV exists: {csv_path.exists()} — {csv_path}")
        print(f"Summary exists: {summary_path.exists()} — {summary_path}")
        raise

    print("\nSUCCESS — NASA B0005 processed.")
    print(f"CSV: {csv_path}")
    print(f"Summary: {summary_path}")
    print(f"Discharge events: {len(df)}")
    print(f"Initial capacity: {initial_capacity:.6f} Ah")
    print(
        "Final capacity: "
        f"{df['discharge_capacity_Ah'].iloc[-1]:.6f} Ah"
    )
    print(f"Final recorded SOH: {df['soh_percent'].iloc[-1]:.2f}%")
    print(
        "Capacity decline: "
        f"{df['capacity_decline_percent'].iloc[-1]:.2f}%"
    )
    print("Original dataset was not modified.")


if __name__ == "__main__":
    main()
