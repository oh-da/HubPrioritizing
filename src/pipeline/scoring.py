"""
Part 4: scoring and prioritisation.

Ports cells 78-88 of ``COMPLETE_TRANSIT_PIPELINE.ipynb`` with the notebook's column
names, so downstream consumers keep working:

1. :func:`prepare_scoring_frame`  mode-name cleanup, ``Total_Unique_Lines``,
   ``Region_category`` / ``Location_category`` / ``RegionLocation``
2. :func:`add_mode_score`         ``score`` = Σ(lines x mode weight) x diversity bonus
3. :func:`classify`               ``HubType`` (ארצי / מטרופוליני / עירוני / Train Station /
   Not Hub), ``eligible``, ``is_rail_only``
4. :func:`filter_eligible`        drop ineligible hubs when the flag is on
5. :func:`normalize_scores`       per-HubType 1-10 normalisation, log demand, pop/jobs
   with distance decay -> the five ``*_Norm`` criteria
6. :func:`monte_carlo`            10,000 random weight sets (<= 0.5 each), seed 42 ->
   ``Average_Simulated_Score``, ``Rank_within_HubType``, ``Overall_Rank``
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from ..classification.hierarchy import classify_hub_tier
from ..config import (
    ELIGIBILITY_MIN_PASSENGERS,
    MAX_CRITERION_WEIGHT,
    MODE_LINE_COLS,
    MODE_WEIGHTS,
    MONTE_CARLO_ITERATIONS,
    MONTE_CARLO_RANDOM_SEED,
    RAIL_ONLY_MODES,
    TIER_METRO,
    TIER_NATIONAL,
)
from .aggregate import ring_column_names
from .report import RunReport

# Order matters: it fixes which random weight applies to which criterion.
SCORING_COLS: tuple[str, ...] = (
    "RegionLocation_Norm",
    "bus_terminal_Norm",
    "score_Norm",
    "TotalDemand_Norm",
    "PopEmp_Score_Norm",
)
CENTER_KEYWORDS = ("תל אביב", "Tel Aviv", "תל-אביב", "מרכז", "Center")
_MODE_ALIASES = {"HighSpeed": "HighSpeed Rail", "Interurban": "Interurban Rail", "Suburban": "Suburban Rail"}


# ----------------------------------------------------------------------------------------
# 1. preparation
# ----------------------------------------------------------------------------------------


def correct_mode_planned(modes) -> list[str]:
    """Standardise mode names; generic ``'Rail'`` is dropped (notebook behaviour)."""
    if not isinstance(modes, list):
        return []
    cleaned = []
    for m in modes:
        m = str(m).strip().replace(",", "")
        m = _MODE_ALIASES.get(m, m)
        if m != "Rail":
            cleaned.append(m)
    return cleaned


def region_category(area) -> int:
    """0 = Tel Aviv / Center (lower national-equity priority), 1 = elsewhere."""
    if area is None or (isinstance(area, float) and pd.isna(area)):
        return 1
    areas = area if isinstance(area, list) else [str(area)]
    return 0 if any(k in str(a) for a in areas for k in CENTER_KEYWORDS) else 1


def location_category(location) -> int:
    """3 = core (גלעין), 2 = ring (טבעת), 1 = periphery / other; highest wins."""
    if location is None or (isinstance(location, float) and pd.isna(location)):
        return 1
    items = location if isinstance(location, list) else [str(location)]
    best = 1
    for loc in items:
        s = str(loc)
        if "גלעין" in s or "Core" in s:
            best = max(best, 3)
        elif "טבעת" in s or "Ring" in s:
            best = max(best, 2)
    return best


def prepare_scoring_frame(groups: pd.DataFrame) -> pd.DataFrame:
    """Add ``Total_Unique_Lines``, ``Region_category``, ``Location_category``, ``RegionLocation``."""
    df = pd.DataFrame(groups).copy()
    if "geometry" in df.columns and hasattr(groups, "geometry"):
        df = pd.DataFrame(groups)  # keep geometry column as plain objects
        df = df.copy()
    df["Mode_Planned"] = df["Mode_Planned"].map(correct_mode_planned)
    if "Total_Unique_Lines" not in df.columns:
        df["Total_Unique_Lines"] = df["Line_Unique"].map(lambda x: len(x) if isinstance(x, list) else 0)
    df["Region_category"] = df["area"].map(region_category) if "area" in df.columns else 1
    df["Location_category"] = df["location"].map(location_category) if "location" in df.columns else 1
    df["RegionLocation"] = df["Region_category"] * df["Location_category"]
    return df


# ----------------------------------------------------------------------------------------
# 2. mode service score
# ----------------------------------------------------------------------------------------


def mode_service_score(row: Mapping, mode_weights: Mapping[str, float] = MODE_WEIGHTS, alpha: float = 0.1) -> float:
    total = 0.0
    for mode, weight in mode_weights.items():
        col = f"{mode} Lines"
        v = row.get(col)
        if v is not None and pd.notna(v) and v > 0:
            total += float(v) * float(weight)
    n_modes = row.get("Num_Modes", 1)
    if n_modes is not None and pd.notna(n_modes) and n_modes > 0:
        total *= 1 + alpha * (n_modes - 1)
    return total


def add_mode_score(df: pd.DataFrame, mode_weights: Mapping[str, float] = MODE_WEIGHTS, alpha: float = 0.1) -> pd.DataFrame:
    """``score``: weighted line count with a 10 % bonus per additional mode."""
    out = df.copy()
    mode_cols = [c for c in MODE_LINE_COLS if c in out.columns]
    if "Num_Modes" not in out.columns or (out["Num_Modes"].max() == 0 and mode_cols):
        out["Num_Modes"] = (out[mode_cols] > 0).sum(axis=1).astype(int)
    out["score"] = [mode_service_score(r, mode_weights, alpha) for r in out.to_dict("records")]
    if "bus_terminal" not in out.columns:
        out["bus_terminal"] = 0
    return out


# ----------------------------------------------------------------------------------------
# 3. eligibility and classification
# ----------------------------------------------------------------------------------------


def is_rail_only(modes: Iterable[str], rail_only_modes: Iterable[str] = RAIL_ONLY_MODES) -> bool:
    modes = [m for m in (modes or []) if m is not None]
    return bool(modes) and all(m in set(rail_only_modes) for m in modes)


def classify(df: pd.DataFrame, require_non_rail: bool = True, min_passengers: float = ELIGIBILITY_MIN_PASSENGERS) -> pd.DataFrame:
    """Add ``HubType`` plus the eligibility flags ``is_rail_only`` and ``eligible``.

    eligible = demand >= 1000 and >= 2 planned modes (and not rail-only when
    ``require_non_rail``). ``HubType`` is computed for every row so that ineligible
    hubs can still be exported when the filter is off.
    """
    out = df.copy()
    out["HubType"] = [
        classify_hub_tier(float(d) if pd.notna(d) else 0.0, m, int(n))
        for d, m, n in zip(out["TotalDemand"], out["Mode_Planned"], out["Total_Unique_Lines"])
    ]
    out["is_rail_only"] = out["Mode_Planned"].map(is_rail_only)
    eligible = (out["TotalDemand"] >= min_passengers) & (out["Mode_Planned"].map(len) > 1)
    if require_non_rail:
        eligible &= ~out["is_rail_only"]
    out["eligible"] = eligible
    return out


def filter_eligible(df: pd.DataFrame, enabled: bool = True, report: RunReport | None = None) -> pd.DataFrame:
    if not enabled:
        if report is not None:
            report.info("scoring", f"eligibility filter disabled; scoring all {len(df)} groups")
        return df.copy()
    kept = df[df["eligible"]].copy()
    if report is not None:
        report.set_metric("groups_before_eligibility", len(df))
        report.set_metric("hubs_after_eligibility", len(kept))
        report.info("scoring", f"eligibility filter kept {len(kept)} of {len(df)} groups (>= 1000 passengers, >= 2 modes, non-rail mode)")
    return kept


# ----------------------------------------------------------------------------------------
# 4. normalisation
# ----------------------------------------------------------------------------------------


def _minmax_1_10(values: pd.Series) -> pd.Series:
    lo, hi = values.min(), values.max()
    if hi > lo:
        return 1 + (values - lo) * 9 / (hi - lo)
    return pd.Series(5.5, index=values.index)


def normalize_by_type(df: pd.DataFrame, col: str, type_col: str = "HubType") -> pd.Series:
    """Min-max to 1-10 within each hub type (5.5 when a type has a constant value)."""
    out = pd.Series(np.nan, index=df.index, dtype=float)
    for t in df[type_col].unique():
        mask = df[type_col] == t
        out[mask] = _minmax_1_10(df.loc[mask, col].astype(float))
    return out


def normalize_log_demand_by_type(df: pd.DataFrame, type_col: str = "HubType") -> tuple[pd.Series, pd.Series]:
    """``LogDemand`` and ``TotalDemand_Norm`` (notebook cell 86: range taken over non-zero values)."""
    log_demand = df["TotalDemand"].astype(float).map(lambda x: 0.0 if x == 0 else float(np.log10(x)))
    norm = pd.Series(np.nan, index=df.index, dtype=float)
    for t in df[type_col].unique():
        mask = df[type_col] == t
        values = log_demand[mask]
        nonzero = values[values > 0]
        if len(nonzero):
            lo, hi = nonzero.min(), nonzero.max()
            norm[mask] = 1 + (values - lo) * 9 / (hi - lo) if hi > lo else 5.5
        else:
            norm[mask] = 1.0
    return log_demand, norm


def pop_emp_raw_score(df: pd.DataFrame, rings: Sequence[int] = (500, 1000, 1500), decay_beta: float = 1.5) -> pd.Series:
    """Σ over rings of (mix-weighted population + jobs) / midpoint^beta.

    National and metropolitan hubs weight jobs 80 % / population 20 %, local hubs the
    reverse. Ring midpoints derive from ``rings`` (250/750/1250 m for the defaults).
    """
    cols = ring_column_names(rings)
    inner = 0
    mids = []
    for _, _, i, o in cols:
        mids.append((i + o) / 2)
        inner = o
    decay = np.asarray(mids, dtype=float) ** decay_beta
    pop = df[[c[0] for c in cols]].astype(float).to_numpy()
    emp = df[[c[1] for c in cols]].astype(float).to_numpy()
    upper = df["HubType"].isin(["National", "Regional", TIER_NATIONAL, TIER_METRO]).to_numpy()
    w_pop = np.where(upper, 0.2, 0.8)[:, None]
    w_emp = np.where(upper, 0.8, 0.2)[:, None]
    combined = w_pop * pop + w_emp * emp
    return pd.Series((combined / decay).sum(axis=1), index=df.index)


def normalize_scores(
    df: pd.DataFrame,
    rings: Sequence[int] = (500, 1000, 1500),
    decay_beta: float = 1.5,
    report: RunReport | None = None,
) -> pd.DataFrame:
    """Produce the five ``*_Norm`` criteria (1-10, per HubType) plus ``LogDemand`` and ``PopEmp_Score_Raw``."""
    out = df.copy()
    for col in ("RegionLocation", "score", "bus_terminal"):
        out[f"{col}_Norm"] = normalize_by_type(out, col)
    out["LogDemand"], out["TotalDemand_Norm"] = normalize_log_demand_by_type(out)

    needed = [c for pair in ring_column_names(rings) for c in pair[:2]]
    if all(c in out.columns for c in needed):
        out["PopEmp_Score_Raw"] = pop_emp_raw_score(out, rings, decay_beta)
        out["PopEmp_Score_Norm"] = normalize_by_type(out, "PopEmp_Score_Raw")
    else:
        out["PopEmp_Score_Norm"] = 5.0
        if report is not None:
            report.warn("scoring", "population/employment ring columns missing; PopEmp_Score_Norm set to 5.0", needed=needed)
    return out


# ----------------------------------------------------------------------------------------
# 5. Monte Carlo
# ----------------------------------------------------------------------------------------


def draw_weight_matrix(rng: np.random.RandomState, n_iter: int, n_criteria: int = len(SCORING_COLS), max_weight: float = MAX_CRITERION_WEIGHT) -> np.ndarray:
    """``n_iter x n_criteria`` weights, each row U(0,1) redrawn while any value > max, then normalised.

    Draws are made one row at a time so the random stream is identical to the
    notebook's ``np.random.rand`` loop (bit-for-bit given the same seed).
    """
    rows = np.empty((n_iter, n_criteria), dtype=float)
    for i in range(n_iter):
        w = rng.rand(n_criteria)
        while np.any(w > max_weight):
            w = rng.rand(n_criteria)
        rows[i] = w / w.sum()
    return rows


def monte_carlo(
    df: pd.DataFrame,
    n_iter: int = MONTE_CARLO_ITERATIONS,
    seed: int = MONTE_CARLO_RANDOM_SEED,
    scope: str = "per_hubtype",
    scoring_cols: Sequence[str] = SCORING_COLS,
    report: RunReport | None = None,
) -> pd.DataFrame:
    """Add ``Average_Simulated_Score``, ``Rank_within_HubType`` and ``Overall_Rank``.

    ``scope='per_hubtype'`` reproduces the notebook: one shared random stream seeded
    once, consumed type by type in order of first appearance. ``scope='all_hubs'``
    draws one weight matrix for the whole table.
    """
    missing = [c for c in scoring_cols if c not in df.columns]
    if missing:
        raise ValueError(f"missing scoring columns {missing}")
    out = df.copy()
    rng = np.random.RandomState(seed)
    result = pd.Series(np.nan, index=out.index, dtype=float)

    if scope == "per_hubtype":
        for hub_type in out["HubType"].unique():
            mask = out["HubType"] == hub_type
            weights = draw_weight_matrix(rng, n_iter, len(scoring_cols))
            x = out.loc[mask, list(scoring_cols)].astype(float).to_numpy()
            result[mask] = (x @ weights.T).sum(axis=1) / n_iter
    elif scope == "all_hubs":
        weights = draw_weight_matrix(rng, n_iter, len(scoring_cols))
        x = out[list(scoring_cols)].astype(float).to_numpy()
        result[:] = (x @ weights.T).sum(axis=1) / n_iter
    else:
        raise ValueError("scope must be 'per_hubtype' or 'all_hubs'")

    out["Average_Simulated_Score"] = result
    out["Rank_within_HubType"] = out.groupby("HubType")["Average_Simulated_Score"].rank(method="dense", ascending=False)
    out["Overall_Rank"] = out["Average_Simulated_Score"].rank(method="dense", ascending=False)
    if report is not None:
        report.set_metric("mc_iterations", n_iter)
        report.set_metric("mc_seed", seed)
        report.set_metric("hub_type_counts", out["HubType"].value_counts().to_dict())
    return out


def score_hubs(
    groups: pd.DataFrame,
    *,
    apply_eligibility_filter: bool = True,
    require_non_rail: bool = True,
    mode_weights: Mapping[str, float] = MODE_WEIGHTS,
    alpha: float = 0.1,
    rings: Sequence[int] = (500, 1000, 1500),
    decay_beta: float = 1.5,
    n_iter: int = MONTE_CARLO_ITERATIONS,
    seed: int = MONTE_CARLO_RANDOM_SEED,
    scope: str = "per_hubtype",
    report: RunReport | None = None,
) -> pd.DataFrame:
    """Run steps 1-5 in order on the aggregated groups (sorted by ``group``)."""
    df = prepare_scoring_frame(groups).sort_values("group").reset_index(drop=True)
    df = add_mode_score(df, mode_weights, alpha)
    df = classify(df, require_non_rail)
    df = filter_eligible(df, apply_eligibility_filter, report)
    df = normalize_scores(df, rings, decay_beta, report)
    return monte_carlo(df, n_iter, seed, scope, report=report)
