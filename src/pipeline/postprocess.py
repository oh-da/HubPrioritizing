"""
Final table: the columns the display page reads.

Ports ``create_results_csv.ipynb`` (cells 6-49) and the two Excel formulas that were
typed by hand into ``hub_prioritization_results.xlsx``:

- ``Line_Names_forPlot``      Hebrew line names, comma-joined
- ``RankByHubTypeMetro``      national hubs ranked nationally, all others within
                              (HubType, Metro); COUNTIFS semantics = competition rank

Lookup tables are parsed by :func:`load_line_names`, :func:`load_line_status`,
:func:`load_line_corrections` and :func:`hub_name_lookup`; :func:`finalize_columns`
derives everything else from the scored hubs.
"""

from __future__ import annotations

import ast
import re
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from ..config import MODE_LINE_COLS
from .report import RunReport
from .scoring import normalize_log_demand_by_type

MODE_HEBREW_MAP = {
    "BRT": "BRT",
    "Cable": "רכבל",
    "Cable Line": "רכבל",
    "Funicular": "פוניקולר",
    "HighSpeed Rail": "רכבת מהירה",
    "Interurban Rail": "רכבת בינעירונית",
    "LRT": 'רק"ל',
    "Metro": "מטרו",
    "Suburban Rail": "רכבת פרברית",
}
HUBTYPE_HEBREW_MAP = {"Train Station": "ארצי", "Metropolitan": "מטרופוליני", "Local": "עירוני"}
LOCATION_HEBREW_MAP = {1: "חוץ", 2: "טבעת", 3: "גלעין"}
STATUS_IDS = tuple(range(8))
SCORE_RENAMES = {
    "Average_Simulated_Score": "TotalScore_MC",
    "Overall_Rank": "Rank_TS_MC",
    "Rank_within_HubType": "Rank_By_TS_MC_By_Metro",
}
POP_COLS = ("pop_0_500", "pop_500_1000", "pop_1000_1500")
EMP_COLS = ("emp_0_500", "emp_500_1000", "emp_1000_1500")


# ----------------------------------------------------------------------------------------
# lookup tables
# ----------------------------------------------------------------------------------------


def _clean_key(value) -> str:
    return str(value).strip().strip("\\").strip()


def load_line_names(df: pd.DataFrame, report: RunReport | None = None) -> dict[str, str]:
    """``LineName -> Hebrew display name`` from a headed or headerless two-column file.

    Accepts header names ``Line_Unique_List``/``LineName`` and ``Line_n_Mode``, tolerates
    a stray header row anywhere in the file (the June 2026 export has one mid-file).
    """
    if df.shape[1] < 2:
        raise ValueError("line names file needs two columns: line id, Hebrew name")
    frame = df.iloc[:, :2].copy()
    frame.columns = ["LineName", "Line_n_Mode"]
    header_like = frame["LineName"].astype(str).str.strip().isin(["Line_Unique_List", "LineName", "Line_ModelName"])
    if header_like.any() and report is not None:
        report.info("postprocess", f"line names: dropped {int(header_like.sum())} header-like row(s)")
    frame = frame[~header_like]
    frame = frame[frame["LineName"].notna() & frame["Line_n_Mode"].notna()]
    out: dict[str, str] = {}
    for k, v in zip(frame["LineName"], frame["Line_n_Mode"]):
        key = _clean_key(k)
        if key:
            out[key] = str(v).strip()
    return out


def load_line_status(df: pd.DataFrame, report: RunReport | None = None) -> dict[str, int]:
    """``LineName -> status id`` from the clean (``LineName,StatusID``) or legacy exploded format.

    Legacy files repeat a line with different statuses (they were exploded from a per-hub
    table); the last value wins, as in the notebook, and conflicts are reported.
    """
    cols = {c.strip().lower().replace(" ", "").replace("_", ""): c for c in df.columns.astype(str)}
    name_col = cols.get("linename")
    status_col = cols.get("statusid")
    if name_col is None or status_col is None:
        raise ValueError(f"line status file needs LineName and StatusID columns; has {list(df.columns)}")
    frame = df[[name_col, status_col]].copy()
    frame.columns = ["LineName", "StatusID"]
    frame["LineName"] = frame["LineName"].astype(str).str.replace(r"[\r\n]", "", regex=True).map(_clean_key)
    frame["StatusID"] = pd.to_numeric(frame["StatusID"], errors="coerce")
    frame = frame[(frame["LineName"] != "") & (frame["LineName"] != "0") & frame["StatusID"].notna()]

    conflicts = frame.groupby("LineName")["StatusID"].nunique()
    conflicts = conflicts[conflicts > 1]
    if len(conflicts) and report is not None:
        report.warn(
            "postprocess",
            f"line status: {len(conflicts)} lines carry more than one status in the file; the last value is used",
            lines=conflicts.index.tolist()[:40],
        )
    return {k: int(v) for k, v in zip(frame["LineName"], frame["StatusID"])}


def load_line_corrections(df: pd.DataFrame) -> dict[str, str]:
    """``misspelled LineName -> correct LineName`` (stray backslashes and spaces removed)."""
    if not {"LineName", "LineName_Correct"} <= set(df.columns):
        raise ValueError("line corrections need LineName and LineName_Correct columns")
    return {
        _clean_key(a): _clean_key(b)
        for a, b in zip(df["LineName"], df["LineName_Correct"])
        if pd.notna(a) and pd.notna(b) and _clean_key(a)
    }


def hub_name_lookup(
    hubs: pd.DataFrame,
    hub_names: pd.DataFrame | None,
    report: RunReport | None = None,
) -> pd.Series:
    """``HubNameHE`` per hub row from an ``h3_index -> HubNameHE`` table (legacy ``group`` key accepted)."""
    names = pd.Series([None] * len(hubs), index=hubs.index, dtype=object)
    if hub_names is None or hub_names.empty:
        return names
    if "HubNameHE" not in hub_names.columns:
        raise ValueError("hub names file needs a HubNameHE column")

    if "h3_index" in hub_names.columns:
        by_h3 = {str(k).strip(): str(v).strip() for k, v in zip(hub_names["h3_index"], hub_names["HubNameHE"]) if pd.notna(k) and pd.notna(v)}
        ambiguous = []
        for idx, hexes in zip(hubs.index, hubs["h3_index"]):
            hex_list = hexes if isinstance(hexes, list) else parse_line_unique(hexes)
            found = [by_h3[h] for h in hex_list if h in by_h3]
            if found:
                names[idx] = found[0]
                if len(set(found)) > 1:
                    ambiguous.append((int(hubs.loc[idx, "group"]), sorted(set(found))))
        if ambiguous and report is not None:
            report.warn("postprocess", f"hub names: {len(ambiguous)} groups match more than one name; first kept", groups=ambiguous[:20])
    elif "group" in hub_names.columns:
        if report is not None:
            report.warn("postprocess", "hub names keyed by 'group' are deprecated (group IDs change between runs); key them by h3_index")
        by_group = {int(k): str(v).strip() for k, v in zip(hub_names["group"], hub_names["HubNameHE"]) if pd.notna(k) and pd.notna(v)}
        names[:] = [by_group.get(int(g)) for g in hubs["group"]]
    else:
        raise ValueError("hub names file needs an h3_index (preferred) or group column")

    if report is not None:
        missing = hubs.loc[names.isna(), "group"].tolist()
        report.set_metric("hubs_without_name", len(missing))
        if missing:
            report.warn("postprocess", f"{len(missing)} hubs have no HubNameHE", groups=missing[:40])
    return names


# ----------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------

_QUOTED = re.compile(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"")


def parse_line_unique(value) -> list[str]:
    """Flatten a list, a stringified list, or the CSV artifact list-of-stringified-lists.

    Quoted tokens are extracted with a regex rather than ``ast.literal_eval`` because the
    notebook's numpy-style inner lists (``"['a' 'b']"``, no commas) would otherwise be
    read as one concatenated string.
    """
    if isinstance(value, list):
        out: list[str] = []
        for el in value:
            if isinstance(el, str) and el.strip().startswith("["):
                out.extend(parse_line_unique(el))
            else:
                out.append(str(el).strip())
        return _dedupe([t for t in out if t])
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    s = str(value).strip()
    if not s or s == "[]":
        return []
    if s.startswith("["):
        quoted = [a or b for a, b in _QUOTED.findall(s)]
        if quoted:
            return parse_line_unique([q.replace("\\'", "'").replace('\\"', '"') for q in quoted])
        bare = s.strip("[]")
        return _dedupe([t for t in re.split(r"[,\s]+", bare) if t])
    return [s]


def _dedupe(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def modes_to_hebrew(modes) -> str:
    items = modes if isinstance(modes, list) else parse_line_unique(modes)
    return ", ".join(MODE_HEBREW_MAP.get(m, m) for m in items)


def rank_by_hubtype_metro(df: pd.DataFrame, score_col: str = "TotalScore_MC", national_label: str = "ארצי") -> pd.Series:
    """Excel ``COUNTIFS(...,">"&score)+1``: competition rank, national hubs nationwide, others per (HubType, Metro)."""
    rank = pd.Series(np.nan, index=df.index, dtype=float)
    is_national = df["HubType"] == national_label
    if is_national.any():
        rank[is_national] = df.loc[is_national, score_col].rank(method="min", ascending=False)
    rest = ~is_national
    if rest.any():
        rank[rest] = df[rest].groupby(["HubType", "Metro"])[score_col].rank(method="min", ascending=False)
    return rank.astype("Int64")


def line_names_for_plot(names) -> str:
    """Comma-join a list of names (duplicates kept: two lines may share a display name)."""
    if isinstance(names, str):
        try:
            lit = ast.literal_eval(names)
            names = list(lit) if isinstance(lit, (list, tuple)) else parse_line_unique(names)
        except (ValueError, SyntaxError):
            names = parse_line_unique(names)
    return ", ".join(str(n) for n in names)


def _global_minmax_1_10(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(5.5, index=series.index)
    return 1 + 9 * (series - lo) / (hi - lo)


# ----------------------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------------------


def finalize_columns(
    scored: pd.DataFrame,
    *,
    line_names: Mapping[str, str] | None = None,
    line_status: Mapping[str, int] | None = None,
    line_corrections: Mapping[str, str] | None = None,
    hub_names: pd.DataFrame | None = None,
    renormalize_globally: bool = False,
    report: RunReport | None = None,
) -> pd.DataFrame:
    """Derive every display column from the scored hubs.

    ``scored`` must carry the scoring output (``Average_Simulated_Score`` ...), the
    aggregates (``Mode_Planned``, ``Line_Unique``, ``h3_index`` as lists) and ``x``/``y``.
    With ``renormalize_globally=True`` the ``*_Norm`` columns are recomputed globally as
    ``create_results_csv.ipynb`` did (inconsistent with the Monte Carlo score; kept as an
    option for comparisons with old outputs).
    """
    df = scored.copy()
    line_names = dict(line_names or {})
    line_status = dict(line_status or {})
    line_corrections = dict(line_corrections or {})

    # --- location / demand derived ------------------------------------------------------
    df["Metro"] = df["area"]
    df["LocationForChart"] = df["Location_category"].map(LOCATION_HEBREW_MAP)
    demand = df["TotalDemand"].astype(float).replace(0, np.nan)
    df["TransferRate"] = (df["TotalTransfers"].astype(float) / demand).fillna(0.0)

    pop_cols = [c for c in POP_COLS if c in df.columns]
    emp_cols = [c for c in EMP_COLS if c in df.columns]
    df["TotalPop_2050"] = df[pop_cols].sum(axis=1) if pop_cols else 0.0
    df["TotalEmp_2050"] = df[emp_cols].sum(axis=1) if emp_cols else 0.0

    # --- modes / hub type ----------------------------------------------------------------
    df["Modes_ForPlot"] = df["Mode_Planned"].map(modes_to_hebrew)
    df["HubTypeHE"] = df["HubType"].map(HUBTYPE_HEBREW_MAP).fillna(df["HubType"])
    metro_lower = df["Metro"].astype(str).str.lower()
    is_tlv = metro_lower.str.contains("tlv") | df["Metro"].astype(str).str.contains("מרכז") | metro_lower.str.contains("center")
    total_lines = df["Total_Unique_Lines"] if "Total_Unique_Lines" in df.columns else df["Line_Unique"].map(len)
    df["HubType_Filtered"] = (is_tlv & (df["TransferRate"] < 0.8) & (total_lines <= 2)).astype(int)
    df["BusTERMINAL_Clone"] = df["bus_terminal"]

    mode_cols = [c for c in MODE_LINE_COLS if c in df.columns]
    df["TotalNumLines"] = df[mode_cols].sum(axis=1) if mode_cols else total_lines

    # --- PopEmp_Score (simple mix, as create_results_csv computed it) --------------------
    # Only local hubs weight population 80 %; every other label (national, metropolitan,
    # 'Train Station', 'Not Hub') weights jobs 80 %, exactly like the notebook.
    is_local = df["HubType"].astype(str).map(lambda t: "local" in t.lower() or "עירוני" in t)
    df["PopEmp_Score"] = np.where(is_local, 0.8 * df["TotalPop_2050"] + 0.2 * df["TotalEmp_2050"], 0.2 * df["TotalPop_2050"] + 0.8 * df["TotalEmp_2050"])

    if renormalize_globally:
        for col in ("RegionLocation", "score", "bus_terminal"):
            df[f"{col}_Norm"] = _global_minmax_1_10(df[col].astype(float).fillna(0))
        df["LogDemand"], df["TotalDemand_Norm"] = normalize_log_demand_by_type(df)
        df["PopEmp_Score_Norm"] = _global_minmax_1_10(df["PopEmp_Score"].astype(float))
        if report is not None:
            report.warn("postprocess", "*_Norm columns were re-normalised globally (renormalize_globally=True); they no longer match the Monte Carlo inputs")

    # --- score renames (keep the originals too, as the golden workbook does) -------------
    for src, dst in SCORE_RENAMES.items():
        if src in df.columns:
            df[dst] = df[src]

    # --- line names ----------------------------------------------------------------------
    lines = df["Line_Unique"].map(parse_line_unique)
    unnamed: set[str] = set()

    def names_for(ids: list[str]) -> list[str]:
        out = []
        for lid in ids:
            fixed = line_corrections.get(lid, lid)
            name = line_names.get(fixed, line_names.get(lid))
            if name is None:
                unnamed.add(lid)
                name = lid
            out.append(name)
        return out

    name_lists = lines.map(names_for)
    df["Line_Names"] = name_lists.map(str)
    df["Line_Names_forPlot"] = name_lists.map(line_names_for_plot)
    if unnamed and report is not None:
        report.warn("postprocess", f"{len(unnamed)} lines have no Hebrew name (line ID used instead)", lines=sorted(unnamed))

    # --- line status ---------------------------------------------------------------------
    unknown_status: set[str] = set()

    def status_counts(ids: list[str]) -> dict[int, int]:
        counts: dict[int, int] = {}
        for lid in ids:
            fixed = line_corrections.get(lid, lid)
            st = line_status.get(fixed, line_status.get(lid))
            if st is None:
                unknown_status.add(lid)
                continue
            counts[int(st)] = counts.get(int(st), 0) + 1
        return counts

    counts = lines.map(status_counts)
    for sid in STATUS_IDS:
        df[f"NumLinesStatus_{sid}"] = counts.map(lambda d, s=sid: d.get(s, 0)).astype(int)
    df["TotalLinesAllStatuses"] = df[[f"NumLinesStatus_{s}" for s in STATUS_IDS]].sum(axis=1)
    if line_status and unknown_status and report is not None:
        report.warn("postprocess", f"{len(unknown_status)} lines have no status code", lines=sorted(unknown_status))

    # --- hub names and the former Excel formula ranks -----------------------------------
    df["HubNameHE"] = hub_name_lookup(df, hub_names, report)
    if "TotalScore_MC" in df.columns:
        df["RankByHubTypeMetro"] = rank_by_hubtype_metro(df)

    if "Rank_TS_MC" in df.columns:
        df = df.sort_values(["Rank_TS_MC", "group"]).reset_index(drop=True)
    return df
