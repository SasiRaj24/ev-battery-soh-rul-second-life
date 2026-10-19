"""Compare NASA-only with cell-balanced multi-source SOH/RUL models.

Outputs are exclusive-created under data/processed/multidataset_comparison_v1.
This is exploratory research, not EV-pack validation.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "processed" / "multidataset_comparison_v1"
REPORT = ROOT / "reports" / "multidataset_comparison_v1_report.md"
NASA_CELLS = {
    "NASA_core": ("B0005", "B0006", "B0007", "B0018"),
    "NASA_group_B0025_B0028": ("B0025", "B0026", "B0027", "B0028"),
    "NASA_group_B0029_B0032": ("B0029", "B0030", "B0031", "B0032"),
}
CS2_INCLUDED = ("CS2_33", "CS2_34", "CS2_35", "CS2_36", "CS2_37", "CS2_38")
CS2_EXCLUDED = ("CS2_3", "CS2_9")
SOH_FEATURES = [
    "current_soh_percent", "previous_soh_percent",
    "previous_soh_change_pp_per_100_cycles", "previous_gap_cycles",
]
RUL_FEATURES = [
    "current_soh_percent", "previous_soh_percent",
    "recent_slope_pp_per_100_cycles", "previous_gap_cycles",
]
XGB_PARAMETERS = {
    "objective": "reg:squarederror", "n_estimators": 160, "max_depth": 2,
    "learning_rate": 0.025, "subsample": 0.9, "colsample_bytree": 1.0,
    "reg_lambda": 2.0, "random_state": 42, "n_jobs": 1,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cell_frame(family: str, dataset: str, battery: str, cycles, capacities, source_files: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame({
        "dataset_family": family, "dataset": dataset, "battery_id": battery,
        "cycle_number": np.asarray(cycles, dtype=float),
        "discharge_capacity_Ah": np.asarray(capacities, dtype=float),
    }).replace([np.inf, -np.inf], np.nan).dropna()
    frame = frame[frame["discharge_capacity_Ah"] > 0].sort_values("cycle_number")
    frame = frame.drop_duplicates("cycle_number", keep="last").reset_index(drop=True)
    if len(frame) < 5:
        raise ValueError(f"{battery} has fewer than five valid measured capacity records")
    frame["soh_percent"] = frame["discharge_capacity_Ah"] / float(frame["discharge_capacity_Ah"].iloc[0]) * 100.0
    frame["previous_soh_percent"] = frame["soh_percent"].shift(1)
    frame["previous_gap_cycles"] = frame["cycle_number"].diff()
    frame["previous_soh_change_pp_per_100_cycles"] = frame["soh_percent"].diff() / frame["previous_gap_cycles"] * 100.0
    frame["next_soh_percent"] = frame["soh_percent"].shift(-1)
    frame["next_gap_cycles"] = frame["cycle_number"].shift(-1) - frame["cycle_number"]
    frame["next_soh_change_pp_per_100_cycles"] = (frame["next_soh_percent"] - frame["soh_percent"]) / frame["next_gap_cycles"] * 100.0
    frame["source_files"] = ";".join(sorted(set(source_files)))
    return frame


def load_nasa() -> tuple[dict[str, pd.DataFrame], list[Path]]:
    traces, sources = {}, []
    for family, batteries in NASA_CELLS.items():
        for battery in batteries:
            path = ROOT / "data" / "nasa" / f"{battery}.mat"
            loaded = loadmat(path, simplify_cells=True)
            if battery not in loaded:
                raise ValueError(f"Missing MATLAB variable {battery} in {path.name}")
            capacities = []
            for event in np.atleast_1d(loaded[battery].get("cycle", [])):
                if not isinstance(event, dict) or str(event.get("type", "")).strip().lower() != "discharge":
                    continue
                data = event.get("data") or {}
                try:
                    value = float(np.asarray(data["Capacity"]).reshape(-1)[0])
                except (KeyError, TypeError, ValueError, IndexError):
                    continue
                if np.isfinite(value) and value > 0:
                    capacities.append(value)
            traces[battery] = cell_frame(
                family, "NASA_PCoE", battery, np.arange(1, len(capacities) + 1),
                capacities, [str(path.relative_to(ROOT))],
            )
            sources.append(path)
    return traces, sources


def load_oxford() -> tuple[dict[str, pd.DataFrame], list[Path]]:
    path = ROOT / "data" / "oxford" / "Oxford_Battery_Degradation_Dataset_1.mat"
    loaded, traces = loadmat(path, simplify_cells=True), {}
    for index in range(1, 9):
        battery, rows = f"Cell{index}", []
        cell = loaded.get(battery)
        if not isinstance(cell, dict):
            raise ValueError(f"Oxford record {battery} is missing")
        for name, checkpoint in cell.items():
            match = re.fullmatch(r"cyc(\d+)", str(name))
            discharge = checkpoint.get("C1dc") if isinstance(checkpoint, dict) else None
            if not match or not isinstance(discharge, dict) or "q" not in discharge:
                continue
            q = np.asarray(discharge["q"], dtype=float).reshape(-1)
            q = q[np.isfinite(q)]
            if q.size:
                # Oxford documents q in mAh; C1dc discharge q is negative.
                capacity = float(abs(np.min(q)) / 1000.0)
                if capacity > 0:
                    rows.append((int(match.group(1)), capacity))
        rows.sort()
        traces[battery] = cell_frame(
            "Oxford", "Oxford_Battery_Degradation_Dataset_1", battery,
            [r[0] for r in rows], [r[1] for r in rows],
            [str(path.relative_to(ROOT))],
        )
    return traces, [path]


def _channel_id(sheet: str) -> str:
    # Excel row-limit splits use names such as Channel_1-008_1 and _2.
    match = re.match(r"^(Channel_.+?)(?:_\d+)?$", sheet, flags=re.IGNORECASE)
    return match.group(1).lower() if match else sheet.lower()


def load_cs2() -> tuple[dict[str, pd.DataFrame], list[Path], dict]:
    root, traces, source_files, audit = ROOT / "data" / "calce" / "CS2", {}, [], {}
    for battery in CS2_INCLUDED:
        candidates, files = [], sorted((root / battery).glob("*.xlsx"))
        for path in files:
            book = pd.ExcelFile(path)
            channel_sheets = [s for s in book.sheet_names if s.lower().startswith("channel_")]
            groups = {}
            for sheet in channel_sheets:
                groups.setdefault(_channel_id(sheet), []).append(sheet)
            if len(groups) > 1:
                raise ValueError(f"Multiple channel identifiers in {path.name}; ambiguous channel")
            pieces = []
            for sheet in channel_sheets:
                frame = pd.read_excel(path, sheet_name=sheet, usecols=lambda c: c in {
                    "Cycle_Index", "Date_Time", "Discharge_Capacity(Ah)"
                })
                required = {"Cycle_Index", "Date_Time", "Discharge_Capacity(Ah)"}
                if required.issubset(frame.columns):
                    pieces.append(frame)
            if not pieces:
                continue
            raw = pd.concat(pieces, ignore_index=True).dropna(
                subset=["Cycle_Index", "Date_Time", "Discharge_Capacity(Ah)"]
            )
            raw["Cycle_Index"] = pd.to_numeric(raw["Cycle_Index"], errors="coerce")
            raw["Date_Time"] = pd.to_datetime(raw["Date_Time"], errors="coerce")
            raw["Discharge_Capacity(Ah)"] = pd.to_numeric(raw["Discharge_Capacity(Ah)"], errors="coerce")
            raw = raw.dropna().sort_values(["Date_Time", "Cycle_Index"])
            grouped = raw.groupby("Cycle_Index", sort=True).agg(
                end=("Discharge_Capacity(Ah)", "max"),
                start=("Discharge_Capacity(Ah)", "min"),
                date=("Date_Time", "max"),
            )
            previous_end, previous_cycle = None, None
            for cycle, row in grouped.iterrows():
                cycle, start, end = int(cycle), float(row["start"]), float(row["end"])
                capacity, reset = None, False
                if previous_end is None:
                    if cycle == 1 and start <= 0.01:
                        capacity = end - start
                elif cycle == previous_cycle + 1:
                    if end >= previous_end:
                        capacity = end - previous_end
                    elif start <= 0.01:
                        # A zero-based cumulative capacity counter restarted.
                        capacity, reset = end - start, True
                if capacity is not None and np.isfinite(capacity) and capacity > 0:
                    candidates.append({
                        "date_time": row["date"], "source_cycle_index": cycle,
                        "capacity_Ah": float(capacity), "source_file": str(path.relative_to(ROOT)),
                        "counter_reset": reset,
                    })
                previous_end, previous_cycle = end, cycle
            source_files.append(path)
        frame = pd.DataFrame(candidates)
        if frame.empty:
            raise ValueError(f"No reconstructable channel cycles in {battery}")
        frame["date_time"] = pd.to_datetime(frame["date_time"], errors="coerce")
        frame = frame.dropna(subset=["date_time", "capacity_Ah"]).sort_values("date_time")
        spans = frame.groupby("date_time")["capacity_Ah"].agg(lambda x: x.max() - x.min())
        conflicts = set(spans[spans > 0.005].index)
        duplicate_rows = int(frame.duplicated("date_time", keep=False).sum())
        frame = frame[~frame["date_time"].isin(conflicts)].drop_duplicates("date_time", keep="last")
        frame = frame.sort_values("date_time").reset_index(drop=True)
        median, q99 = float(frame["capacity_Ah"].median()), float(frame["capacity_Ah"].quantile(0.99))
        # Pre-score quality gate: coherent CS2 cells have stable, sub-1.5 Ah
        # cycle increments; CS2_3/CS2_9 fail due session-level discontinuities.
        if len(frame) < 100 or not (0.2 <= median <= 1.5) or q99 > 1.5:
            raise ValueError(f"CS2 capacity quality gate failed for {battery}: n={len(frame)}, median={median}, q99={q99}")
        audit[battery] = {
            "workbooks": len(files), "reconstructed_cycles_before_deduplication": len(candidates),
            "duplicate_timestamp_rows": duplicate_rows, "conflicting_timestamps_excluded": len(conflicts),
            "cycles_after_deduplication": len(frame), "capacity_Ah_median": median,
            "capacity_Ah_q99": q99, "counter_resets_inside_workbooks": int(sum(x["counter_reset"] for x in candidates)),
            "first_date": frame["date_time"].iloc[0].isoformat(), "last_date": frame["date_time"].iloc[-1].isoformat(),
        }
        traces[battery] = cell_frame(
            "CALCE_CS2", "CALCE_CS2", battery, np.arange(1, len(frame) + 1),
            frame["capacity_Ah"].to_numpy(), sorted(frame["source_file"].unique().tolist()),
        )
    return traces, sorted(set(source_files)), audit


def make_soh_rows(traces: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.concat([
        frame.dropna(subset=SOH_FEATURES + ["next_soh_change_pp_per_100_cycles"])
        .query("previous_gap_cycles > 0 and next_gap_cycles > 0")
        for frame in traces.values()
    ], ignore_index=True)


def training_weights(frame: pd.DataFrame, balance_families: bool) -> np.ndarray:
    sizes = frame.groupby("battery_id")["battery_id"].transform("size").to_numpy(dtype=float)
    families = frame["dataset_family"].to_numpy()
    weights = np.zeros(len(frame), dtype=float)
    names = sorted(set(families))
    for name in names:
        ix = np.flatnonzero(families == name)
        n_cells = frame.iloc[ix]["battery_id"].nunique()
        weight = (1.0 / len(names) if balance_families else 1.0) / n_cells
        weights[ix] = weight / sizes[ix]
    return weights / weights.sum()


def fit_predict(estimator: str, train: pd.DataFrame, test: pd.DataFrame, features: list[str], target: str, balance_families: bool) -> np.ndarray:
    weights = training_weights(train, balance_families)
    if estimator == "ridge":
        model = make_pipeline(StandardScaler(), Ridge(alpha=2.0))
        model.fit(train[features], train[target], ridge__sample_weight=weights)
    elif estimator == "xgboost":
        model = XGBRegressor(**XGB_PARAMETERS)
        model.fit(train[features], train[target], sample_weight=weights)
    else:
        raise ValueError(estimator)
    return np.asarray(model.predict(test[features]), dtype=float)


def errors(actual, predicted) -> tuple[float, float]:
    delta = np.asarray(actual, dtype=float) - np.asarray(predicted, dtype=float)
    return float(np.abs(delta).mean()), float(np.sqrt(np.square(delta).mean()))


def evaluate_soh(traces: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, records = make_soh_rows(traces), []
    cells = sorted(rows[["battery_id", "dataset_family"]].drop_duplicates().itertuples(index=False, name=None))
    for held_out, family in cells:
        test = rows[rows["battery_id"] == held_out]
        all_train = rows[rows["battery_id"] != held_out]
        family_train = rows[(rows["battery_id"] != held_out) & (rows["dataset_family"] == family)]
        external_train = rows[rows["dataset_family"] != family]
        strategies = [("persistence", None, None)]
        for label, train in [
            ("within_family", family_train),
            ("multi_dataset", all_train),
            ("external_family", external_train),
        ]:
            for estimator in ("ridge", "xgboost"):
                strategies.append((f"{label}_{estimator}", estimator, train))
        if family == "NASA_core":
            core = rows[(rows["dataset_family"] == "NASA_core") & (rows["battery_id"] != held_out)]
            for estimator in ("ridge", "xgboost"):
                strategies.append((f"NASA_core_only_{estimator}", estimator, core))
        for strategy, estimator, train in strategies:
            if estimator is None:
                prediction = test["current_soh_percent"].to_numpy(dtype=float)
                n_train, train_families = 0, []
            else:
                if train["battery_id"].nunique() < 2:
                    continue
                rate = fit_predict(
                    estimator, train, test, SOH_FEATURES,
                    "next_soh_change_pp_per_100_cycles",
                    balance_families=("multi_dataset" in strategy or "external_family" in strategy),
                )
                prediction = test["current_soh_percent"].to_numpy(dtype=float) + (
                    rate * test["previous_gap_cycles"].to_numpy(dtype=float) / 100.0
                )
                n_train = int(train["battery_id"].nunique())
                train_families = sorted(train["dataset_family"].unique().tolist())
            mae, rmse = errors(test["next_soh_percent"], prediction)
            records.append({
                "held_out_battery": held_out, "dataset_family": family,
                "strategy": strategy, "mae_next_observation_soh_pp": mae,
                "rmse_next_observation_soh_pp": rmse, "test_records": len(test),
                "training_cells": n_train, "training_families": ";".join(train_families),
            })
    detail = pd.DataFrame(records)
    summary = detail.groupby(["dataset_family", "strategy"], as_index=False).agg(
        macro_cell_mae_pp=("mae_next_observation_soh_pp", "mean"),
        minimum_cell_mae_pp=("mae_next_observation_soh_pp", "min"),
        maximum_cell_mae_pp=("mae_next_observation_soh_pp", "max"),
        held_out_cells=("held_out_battery", "nunique"),
    )
    return detail, summary


def make_rul_rows(traces: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict]:
    rows, statuses = [], {}
    for battery, trace in traces.items():
        frame = trace.copy().reset_index(drop=True)
        endpoint = float(frame["discharge_capacity_Ah"].iloc[0] * 0.70)
        crossing = np.flatnonzero(frame["discharge_capacity_Ah"].to_numpy(dtype=float) <= endpoint)
        if not len(crossing):
            statuses[battery] = {
                "status": "right_censored", "last_soh_percent": float(frame["soh_percent"].iloc[-1]),
                "endpoint_relative_soh_percent": 70.0, "endpoint_capacity_Ah": endpoint,
            }
            continue
        position = int(crossing[0])
        eol = float(frame["cycle_number"].iloc[position])
        statuses[battery] = {
            "status": "threshold_crossed", "eol_cycle": eol,
            "endpoint_relative_soh_percent": 70.0, "endpoint_capacity_Ah": endpoint,
        }
        frame = frame.iloc[: position + 1].copy()
        frame["rul_cycles"] = eol - frame["cycle_number"]
        frame["recent_slope_pp_per_100_cycles"] = frame["previous_soh_change_pp_per_100_cycles"]
        rows.append(frame.dropna(subset=RUL_FEATURES + ["rul_cycles"]).query("rul_cycles >= 0"))
    return (pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()), statuses


def evaluate_rul(traces: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rows, statuses = make_rul_rows(traces)
    if rows.empty:
        return pd.DataFrame(), pd.DataFrame(), statuses
    records = []
    cells = sorted(rows[["battery_id", "dataset_family"]].drop_duplicates().itertuples(index=False, name=None))
    for held_out, family in cells:
        test = rows[rows["battery_id"] == held_out]
        all_train = rows[rows["battery_id"] != held_out]
        family_train = rows[(rows["battery_id"] != held_out) & (rows["dataset_family"] == family)]
        external_train = rows[rows["dataset_family"] != family]
        strategies = [
            ("multi_dataset_ridge", "ridge", all_train),
            ("external_family_ridge", "ridge", external_train),
            ("multi_dataset_xgboost", "xgboost", all_train),
            ("external_family_xgboost", "xgboost", external_train),
        ]
        if family_train["battery_id"].nunique() >= 2:
            strategies.extend([
                ("within_family_ridge", "ridge", family_train),
                ("within_family_xgboost", "xgboost", family_train),
            ])
        if family == "NASA_core" and family_train["battery_id"].nunique() >= 2:
            strategies.extend([
                ("NASA_core_only_ridge", "ridge", family_train),
                ("NASA_core_only_xgboost", "xgboost", family_train),
            ])
        for strategy, estimator, train in strategies:
            if train["battery_id"].nunique() < 2:
                continue
            prediction = np.maximum(0.0, fit_predict(
                estimator, train, test, RUL_FEATURES, "rul_cycles",
                balance_families=("multi_dataset" in strategy or "external_family" in strategy),
            ))
            mae, rmse = errors(test["rul_cycles"], prediction)
            records.append({
                "held_out_battery": held_out, "dataset_family": family,
                "strategy": strategy, "mae_rul_cycles": mae, "rmse_rul_cycles": rmse,
                "test_records": len(test), "training_cells": train["battery_id"].nunique(),
                "training_families": ";".join(sorted(train["dataset_family"].unique().tolist())),
            })
    detail = pd.DataFrame(records)
    summary = detail.groupby(["dataset_family", "strategy"], as_index=False).agg(
        macro_cell_mae_cycles=("mae_rul_cycles", "mean"),
        minimum_cell_mae_cycles=("mae_rul_cycles", "min"),
        maximum_cell_mae_cycles=("mae_rul_cycles", "max"),
        held_out_cells=("held_out_battery", "nunique"),
    ) if not detail.empty else pd.DataFrame()
    return detail, summary, statuses


def write_csv_exclusive(path: Path, frame: pd.DataFrame) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        frame.to_csv(stream, index=False)


def main() -> None:
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError(f"Refusing to overwrite comparison output or report: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=False)
    nasa, nasa_sources = load_nasa()
    oxford, oxford_sources = load_oxford()
    cs2, cs2_sources, cs2_audit = load_cs2()
    traces = {**nasa, **oxford, **cs2}
    soh_detail, soh_summary = evaluate_soh(traces)
    rul_detail, rul_summary, rul_status = evaluate_rul(traces)
    trace_table = pd.concat(traces.values(), ignore_index=True)
    source_paths = sorted(set(nasa_sources + oxford_sources + cs2_sources))
    packages = {
        name: importlib.metadata.version(name)
        for name in ("numpy", "pandas", "scipy", "scikit-learn", "xgboost", "openpyxl")
    }
    summary = {
        "version": "1.0.0-harmonized-comparison",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "question": "Does cell-balanced multi-source training improve held-cell SOH or harmonized relative-endpoint RUL versus family-only baselines?",
        "included_cells_by_family": {
            family: sorted(frame["battery_id"].unique().tolist())
            for family, frame in trace_table.groupby("dataset_family")
        },
        "excluded_sources": {
            "CALCE_CS2": {
                battery: "Excluded before scoring: unstable reconstructed per-cycle capacities across workbook sessions."
                for battery in CS2_EXCLUDED
            },
            "CALCE_PL": {
                "PL11": "MATLAB MCOS table objects remain opaque to the installed parser.",
                "PL13": "MATLAB MCOS table objects remain opaque to the installed parser.",
            },
            "other_NASA_cells": "Not included in this comparison; heterogeneous protocols/baselines are not quality-cleared by the reviewed cohorts.",
        },
        "calce_cs2_reconstruction_audit": cs2_audit,
        "harmonization": {
            "SOH_features": SOH_FEATURES,
            "RUL_features": RUL_FEATURES,
            "SOH": "100 * capacity / first measured capacity of that cell",
            "next_record_target": "next measured SOH change per 100 cycles; scaled by prior observation interval when reconstructing next SOH",
            "excluded_shared_features": [
                "absolute capacity in Ah (cell capacities differ)",
                "ambient temperature (field meaning differs across source formats/protocols)",
                "absolute cycle count as a shared feature (cycle/time scales differ)",
            ],
        },
        "validation_design": {
            "independent_unit": "complete held-out cell; no rows from the held-out cell are used in model fitting",
            "multi_dataset_weights": "equal total weight per source family, equal weight per cell in family, equal weight per row in cell",
            "within_family_weights": "equal weight per cell",
            "external_family": "train on other families only; no same-family examples in training",
            "uncertainty": "cell-level errors and observed ranges only; no inferential confidence intervals",
        },
        "RUL": {
            "endpoint": "first observed capacity <= 70% of that cell's first observed capacity",
            "censoring_status_by_cell": rul_status,
            "limit": "This comparative endpoint does not replace the deployed NASA model's absolute 1.4 Ah endpoint.",
        },
        "package_versions": packages,
        "source_manifest": [
            {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in source_paths
        ],
        "scope": "Laboratory cells only; no EV pack or field validation is claimed.",
    }
    write_csv_exclusive(OUTPUT / "harmonized_capacity_traces_v1.csv", trace_table)
    write_csv_exclusive(OUTPUT / "soh_cell_metrics_v1.csv", soh_detail)
    write_csv_exclusive(OUTPUT / "soh_family_summary_v1.csv", soh_summary)
    write_csv_exclusive(OUTPUT / "rul_cell_metrics_v1.csv", rul_detail)
    write_csv_exclusive(OUTPUT / "rul_family_summary_v1.csv", rul_summary)
    with (OUTPUT / "comparison_manifest_v1.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, allow_nan=False)
        stream.write("\n")
    report = [
        "# Harmonized multi-dataset comparison v1", "",
        f"Generated {summary['created_at_utc']}. New outputs only; source measurements and prior results were not modified.", "",
        "## Included data and common definitions", "",
        "The comparison uses three previously reviewed NASA cohorts (12 cells), Oxford (8 cells), and reconstructed CALCE CS2 (6 cells). NASA B0005/B0006/B0007/B0018, B0025-B0028, and B0029-B0032 remain separate families. CS2 channel discharge counters were differenced within consecutive cycle-index records; duplicate timestamps from overlapping exports were collapsed only when capacities agreed. CS2_3 and CS2_9 were excluded before scoring because reconstructed capacity increments are unstable. CALCE PL11/PL13 remain unparsed.",
        "",
        "Capacity is normalized to each cell's first measured record. Shared features omit absolute Ah capacity, ambient temperature, and absolute cycle number. SOH predicts the next measured health-change rate per 100 cycles and projects it using the previous observation gap. This preserves an explicit next-record task, but the record cadence differs across families.",
        "",
        "## SOH results by family and training strategy", "",
        "| Family | Strategy | Macro cell MAE (SOH pp) | Observed cell range | Held-out cells |",
        "|---|---|---:|---:|---:|",
    ]
    for row in soh_summary.itertuples(index=False):
        report.append(f"| {row.dataset_family} | {row.strategy} | {row.macro_cell_mae_pp:.4f} | {row.minimum_cell_mae_pp:.4f}–{row.maximum_cell_mae_pp:.4f} | {row.held_out_cells} |")
    report += [
        "",
        "NASA core-only and multi-dataset strategies are evaluated on the same held-out NASA core cells. Within-family models use only other cells in that source family. External-family models omit the entire held-out family. Lower error is better. An observed range is not a confidence interval.",
        "",
        "## RUL results by family", "",
        "RUL uses a harmonized exploratory threshold of 70% of each cell's first measured capacity. Cells that do not reach it are right-censored and omitted from complete-case metrics. This is separate from the deployed NASA model's absolute 1.4 Ah endpoint.", "",
        "| Family | Strategy | Macro cell MAE (cycles) | Observed cell range | Held-out cells |",
        "|---|---|---:|---:|---:|",
    ]
    for row in rul_summary.itertuples(index=False):
        report.append(f"| {row.dataset_family} | {row.strategy} | {row.macro_cell_mae_cycles:.3f} | {row.minimum_cell_mae_cycles:.3f}–{row.maximum_cell_mae_cycles:.3f} | {row.held_out_cells} |")
    report += [
        "",
        "## Interpretation boundaries", "",
        "The cell is the independent test unit; repeated cycle observations are not treated as independent batteries. Family- and cell-balanced weights reduce domination by longer traces but cannot remove protocol shift. SOH next-record intervals differ across datasets; RUL endpoints are relative to first observed measurements. Results are exploratory, based on small cell counts, and have no inferential confidence interval.",
        "",
        "This comparison does not claim laboratory-cell results validate an EV pack, field operation, or second-life safety. Existing inference releases remain unchanged; the new models here are fold-specific and are not promoted to the dashboard.",
        "",
        "Detailed cell scores, capacity traces, source hashes, exclusions, censoring, and package versions are in data/processed/multidataset_comparison_v1.",
    ]
    with REPORT.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(report) + "\n")
    print(json.dumps({
        "output": str(OUTPUT), "report": str(REPORT),
        "cells": summary["included_cells_by_family"],
        "soh_summary": soh_summary.to_dict(orient="records"),
        "rul_summary": rul_summary.to_dict(orient="records"),
        "cs2_audit": cs2_audit, "rul_status": rul_status,
    }, indent=2))


if __name__ == "__main__":
    main()
