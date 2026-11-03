"""
Calculation workbook: every scoring step as live Excel formulas, for stakeholder review.

Written next to ``hub_prioritization_results.xlsx`` (which stays values-only for the
display page). Each criterion has its own sheet with one row per scored hub (same row
order on every sheet), the raw inputs from the pipeline in blue and every derived value
as a formula, so a reviewer can follow how a hub got its rank and change a parameter on
``Parameters`` to see the effect.

Sheets, in process order:

- ``README``          what each sheet does, colour legend, run settings
- ``Parameters``      every threshold and weight, as named cells the formulas use
- ``1_Eligibility``   every hub group: eligibility tests and the hub-type (tier) rules
- ``2_Location`` .. ``6_BusTerminal``  the five criteria: raw value -> per-tier 1-10
- ``7_MC_Weights``    mean Monte Carlo weight per criterion and hub type
- ``7b_MC_Draws``     the 10,000 accepted random weight sets (same seed as the run)
- ``8_FinalScore``    weighted sum, contributions, and the three ranks
- ``9_Ranking``       the ranking table, tier by tier
- ``Hub_Explorer``    pick a hub and see its whole calculation on one page
- ``Checks``          workbook formulas vs the pipeline's own values

The Monte Carlo score is linear in the weights, so the mean over the iterations of
``Σ norm x w`` equals ``Σ norm x mean(w)``; the workbook shows the draws, averages them
with formulas, and scores each hub with the averaged weights. Random numbers cannot be
reproduced by Excel, so the draws are stored as values (regenerated here from the seed
with :func:`scoring.draw_weight_matrix`, bit-identical to the run).
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

from ..config import (
    ELIGIBILITY_MIN_PASSENGERS,
    MAX_CRITERION_WEIGHT,
    METRO_HUB_MIN_PASSENGERS,
    MODE_LINE_COLS,
    MODE_WEIGHTS,
    NATIONAL_HUB_MIN_PASSENGERS,
    RAIL_ONLY_MODES,
    TIER_LOCAL,
    TIER_METRO,
    TIER_NATIONAL,
)
from .aggregate import ring_column_names
from .scoring import CENTER_KEYWORDS, SCORING_COLS, add_mode_score, classify, prepare_scoring_frame

FIRST_ROW = 5  # data rows start here on every per-hub sheet (title, note, unit row, header)
ALL_HUBS_BLOCK = "All hubs"

CRITERION_LABELS = {
    "RegionLocation_Norm": "Location",
    "bus_terminal_Norm": "Bus terminal",
    "score_Norm": "Service & modes",
    "TotalDemand_Norm": "Passenger activity",
    "PopEmp_Score_Norm": "Population & jobs",
}

# --- styles -----------------------------------------------------------------------------
FONT = "Arial"
F_INPUT = Font(name=FONT, color="0000FF")
F_FORMULA = Font(name=FONT, color="000000")
F_LINK = Font(name=FONT, color="008000")
F_BOLD = Font(name=FONT, bold=True)
F_HEADER = Font(name=FONT, bold=True, color="FFFFFF")
F_TITLE = Font(name=FONT, bold=True, size=14)
F_NOTE = Font(name=FONT, italic=True, color="595959")
FILL_HEADER = PatternFill("solid", fgColor="1F4E78")
FILL_KEY = PatternFill("solid", fgColor="FFFF00")
FILL_RESULT = PatternFill("solid", fgColor="E2EFDA")
FILL_UNIT = PatternFill("solid", fgColor="F2F2F2")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
NUM2 = "0.00"
NUM3 = "0.000"
NUM4 = "0.0000"
INT = "#,##0"


def _q(sheet: str) -> str:
    return "'" + sheet.replace("'", "''") + "'"


def _v(value):
    """Python / numpy value -> openpyxl cell value (NaN -> blank)."""
    if value is None:
        return None
    if isinstance(value, (list, tuple, np.ndarray)):
        return ", ".join(str(v) for v in value)
    if isinstance(value, float) and np.isnan(value):
        return None
    if pd.api.types.is_scalar(value) and pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _xl_str(s: str) -> str:
    return '"' + str(s).replace('"', '""') + '"'


class _Sheet:
    """Small helper: a per-hub sheet with a title, a note, an optional unit row and headers."""

    def __init__(self, wb: Workbook, name: str, title: str, note: str, n_rows: int):
        self.ws = wb.create_sheet(name)
        self.name = name
        self.n = n_rows
        self.last = FIRST_ROW + max(n_rows, 1) - 1
        self.ws["A1"] = title
        self.ws["A1"].font = F_TITLE
        self.ws["A2"] = note
        self.ws["A2"].font = F_NOTE
        self.ws.freeze_panes = self.ws.cell(row=FIRST_ROW, column=4)
        self.cols: dict[str, int] = {}

    def header(self, col: int, key: str, label: str, width: float = 12, comment: str | None = None) -> str:
        c = self.ws.cell(row=FIRST_ROW - 1, column=col, value=label)
        c.font, c.fill, c.alignment, c.border = F_HEADER, FILL_HEADER, Alignment(wrap_text=True, vertical="center", horizontal="center"), BORDER
        if comment:
            c.comment = Comment(comment, "hubs pipeline", width=320, height=140)
        self.ws.column_dimensions[get_column_letter(col)].width = width
        self.cols[key] = col
        return get_column_letter(col)

    def letter(self, key: str) -> str:
        return get_column_letter(self.cols[key])

    def rng(self, key: str) -> str:
        L = self.letter(key)
        return f"${L}${FIRST_ROW}:${L}${self.last}"

    def ext(self, key: str) -> str:
        """Absolute range of a column for use from another sheet."""
        return f"{_q(self.name)}!{self.rng(key)}"

    def put(self, row: int, key: str, value, font: Font = F_FORMULA, fmt: str | None = None, fill: PatternFill | None = None):
        c = self.ws.cell(row=row, column=self.cols[key], value=value)
        c.font = font
        c.border = BORDER
        if fmt:
            c.number_format = fmt
        if fill:
            c.fill = fill
        return c


def _define(wb: Workbook, name: str, ref: str) -> None:
    wb.defined_names[name] = DefinedName(name, attr_text=ref)


# ----------------------------------------------------------------------------------------
# frames
# ----------------------------------------------------------------------------------------


def eligibility_frame(groups: pd.DataFrame, cfg) -> pd.DataFrame:
    """All groups before the eligibility filter, with ``HubType`` / ``eligible`` as scored."""
    df = prepare_scoring_frame(groups).sort_values("group").reset_index(drop=True)
    df = add_mode_score(df, alpha=cfg.mode_diversity_alpha)
    return classify(df, cfg.require_non_rail_mode)


def mc_blocks(scored: pd.DataFrame, cfg) -> list[tuple[str, np.ndarray]]:
    """The run's accepted raw draws per hub type, in the order the run consumed its random
    stream (``draws / draws.sum(axis=1)`` is exactly :func:`scoring.draw_weight_matrix`)."""
    rng = np.random.RandomState(cfg.mc_seed)
    n = len(SCORING_COLS)
    if cfg.mc_scope == "all_hubs":
        return [(ALL_HUBS_BLOCK, _draw_raw_matrix(rng, cfg.mc_iterations, n, MAX_CRITERION_WEIGHT))]
    return [(str(t), _draw_raw_matrix(rng, cfg.mc_iterations, n, MAX_CRITERION_WEIGHT)) for t in scored["HubType"].unique()]


# ----------------------------------------------------------------------------------------
# sheets
# ----------------------------------------------------------------------------------------


def _write_parameters(wb: Workbook, cfg) -> dict:
    ws = wb.create_sheet("Parameters")
    ws["A1"] = "Parameters - every threshold and weight used by the formulas"
    ws["A1"].font = F_TITLE
    ws["A2"] = "Blue = value from the pipeline configuration. Yellow cells are the key levers: change one and every sheet recalculates."
    ws["A2"].font = F_NOTE
    for col, w in zip("ABCD", (44, 14, 18, 70)):
        ws.column_dimensions[col].width = w
    row = 4
    for i, h in enumerate(("Parameter", "Value", "Name in formulas", "Meaning / source"), start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font, c.fill, c.border = F_HEADER, FILL_HEADER, BORDER
    row += 1

    def param(label, name, value, note, fmt=None, key=False):
        nonlocal row
        ws.cell(row=row, column=1, value=label).font = F_FORMULA
        c = ws.cell(row=row, column=2, value=value)
        c.font, c.border = F_INPUT, BORDER
        if fmt:
            c.number_format = fmt
        if key:
            c.fill = FILL_KEY
        ws.cell(row=row, column=3, value=name).font = F_NOTE
        ws.cell(row=row, column=4, value=note).font = F_NOTE
        _define(wb, name, f"Parameters!$B${row}")
        row += 1

    def section(title):
        nonlocal row
        row += 1
        ws.cell(row=row, column=1, value=title).font = F_BOLD
        row += 1

    section("Step 1 - Eligibility")
    param("Minimum daily passengers (2050)", "MinPassengers", float(ELIGIBILITY_MIN_PASSENGERS), "Hub needs at least this many boardings+alightings per day", INT, True)
    param("Minimum number of planned mass-transit modes", "MinModes", 2, "Pipeline rule: more than one planned mode")
    param("Require a non-rail mode (1 = yes, 0 = no)", "RequireNonRail", 1 if cfg.require_non_rail_mode else 0, "Rail-only groups (Suburban / Interurban rail only) are excluded when 1; setting require_non_rail_mode")

    section("Step 1 - Hub type (tier) rules")
    param("National (ארצי) minimum passengers", "NationalMinDemand", float(NATIONAL_HUB_MIN_PASSENGERS), "And High-speed or Interurban rail, and at least the minimum lines", INT, True)
    param("Metropolitan (מטרופוליני) minimum passengers", "MetroMinDemand", float(METRO_HUB_MIN_PASSENGERS), "And Suburban rail, Metro, Interurban or High-speed rail, and at least the minimum lines", INT, True)
    param("Local (עירוני) minimum passengers", "LocalMinDemand", float(ELIGIBILITY_MIN_PASSENGERS), "And BRT or LRT, and at least the minimum lines", INT)
    param("Minimum unique lines for a hub tier", "MinLinesTier", 3, "Fewer lines -> 'Train Station' (rail) or 'Not Hub'")

    section("Step 2 - Location criterion")
    param("Region weight: Tel Aviv / Center", "RegionWeightCenter", 0, "Center keywords below; the periphery is favoured")
    param("Region weight: all other regions", "RegionWeightOther", 1, "")
    param("Metropolitan position: core (גלעין)", "CoreScore", 3, "")
    param("Metropolitan position: ring (טבעת)", "RingScore", 2, "")
    param("Metropolitan position: outer / other", "OuterScore", 1, "")
    kw_start = row
    for k in CENTER_KEYWORDS:
        param(f"Center keyword {row - kw_start + 1}", f"CenterKeyword{row - kw_start + 1}", k, "Area text containing any keyword is 'Center' (case-sensitive)")
    _define(wb, "CenterKeywords", f"Parameters!$B${kw_start}:$B${row - 1}")

    section("Step 3 - Service & modes criterion")
    param("Diversity bonus per additional mode", "ModeAlpha", float(cfg.mode_diversity_alpha), "score = Σ(lines x mode weight) x (1 + bonus x (modes - 1))", "0%", True)
    mode_refs = {}
    for col in MODE_LINE_COLS:
        mode = col[: -len(" Lines")]
        nm = "W_" + "".join(ch for ch in mode if ch.isalnum())
        mode_refs[col] = nm
        param(f"Mode weight: {mode}", nm, float(MODE_WEIGHTS.get(mode, 1.0)), "Weight per line (each direction counts as a line)", NUM2, True)

    section("Step 5 - Population & jobs criterion")
    param("Distance-decay exponent (beta)", "DecayBeta", float(cfg.distance_decay_beta), "Each ring is divided by midpoint ^ beta", NUM2, True)
    rings = ring_column_names(cfg.influence_rings)
    mids = list(cfg.pop_emp_decay_midpoints) if cfg.pop_emp_decay_midpoints else [(i + o) / 2 for _, _, i, o in rings]
    ring_refs = []
    for (_, _, inner, outer), mid in zip(rings, mids):
        nm = f"RingMid_{inner}_{outer}"
        ring_refs.append(nm)
        param(f"Ring {inner}-{outer} m: decay midpoint (m)", nm, float(mid), "Distance used for the decay of this ring", "0")
    param("Population share, National / Metropolitan hubs", "PopShareUpper", 0.2, "Higher tiers serve employment centres", "0%", True)
    param("Jobs share, National / Metropolitan hubs", "EmpShareUpper", 0.8, "", "0%", True)
    param("Population share, other hub types", "PopShareLower", 0.8, "Local hubs serve residential areas", "0%", True)
    param("Jobs share, other hub types", "EmpShareLower", 0.2, "", "0%", True)

    section("Normalisation (every criterion, within each hub type)")
    param("Lowest normalised score", "NormMin", 1, "Hub with the tier's minimum raw value")
    param("Highest normalised score", "NormMax", 10, "Hub with the tier's maximum raw value")
    param("Score when the whole tier has one value", "NormConst", 5.5, "")

    section("Monte Carlo (values only - the draws are on 7b_MC_Draws)")
    param("Iterations", "MC_Iterations", int(cfg.mc_iterations), "Random weight sets per hub type", INT)
    param("Random seed", "MC_Seed", int(cfg.mc_seed), "numpy RandomState seed")
    param("Maximum raw draw per criterion", "MC_MaxWeight", float(MAX_CRITERION_WEIGHT), "A draw with any value above this is redrawn, then the row is divided by its sum", NUM2)
    param("Scope", "MC_Scope", cfg.mc_scope, "per_hubtype: one weight matrix per hub type; all_hubs: one for every hub")
    return {"mode_refs": mode_refs, "ring_refs": ring_refs, "rings": rings}


def _write_eligibility(wb: Workbook, pre: pd.DataFrame, names: dict) -> _Sheet:
    n = len(pre)
    s = _Sheet(wb, "1_Eligibility", "Step 1 - Eligibility and hub type (tier), every hub group",
               "One row per hub group formed from the H3 hexagons. Blue = pipeline data; black = formula. Only eligible groups go on to scoring (rows of the following sheets).", n)
    has_modes = [("HighSpeed Rail", "has_hs"), ("Interurban Rail", "has_iu"), ("Suburban Rail", "has_sub"), ("Metro", "has_metro"), ("LRT", "has_lrt"), ("BRT", "has_brt")]
    spec = [
        ("group", "Group", 8, None), ("name", "Hub name", 24, None), ("modes", "Planned modes", 30, None),
        ("demand", "Passengers / day (2050)", 13, "TotalDemand: boardings + alightings of every node in the group"),
        ("lines", "Unique lines", 9, "Total_Unique_Lines"),
        ("n_modes", "Planned modes (count)", 9, None), ("n_rail", "Of which rail-only modes", 9, "Suburban / Interurban rail"),
    ] + [(k, f"Has {m}", 9, None) for m, k in has_modes] + [
        ("t_demand", "Passengers >= minimum?", 11, "=demand >= MinPassengers"),
        ("t_modes", "Modes >= minimum?", 11, "=modes >= MinModes"),
        ("t_rail", "Rail only?", 9, "Every planned mode is Suburban / Interurban rail"),
        ("eligible", "ELIGIBLE", 11, "All tests pass (rail-only test only when RequireNonRail = 1)"),
        ("hubtype", "Hub type (tier)", 15, "National: HS/Interurban rail + lines >= 3 + demand >= NationalMinDemand\nMetropolitan: Suburban/Metro/Interurban/HS + lines >= 3 + demand >= MetroMinDemand\nLocal: BRT/LRT + lines >= 3 + demand >= LocalMinDemand\nTrain Station: rail with <= 2 lines\nelse Not Hub"),
    ]
    for i, (k, label, w, com) in enumerate(spec, start=1):
        s.header(i, k, label, w, com)
    rail = set(RAIL_ONLY_MODES)
    for i, r in enumerate(pre.itertuples(index=False)):
        row = FIRST_ROW + i
        rd = r._asdict()
        modes = list(rd["Mode_Planned"]) if isinstance(rd["Mode_Planned"], list) else []
        demand = rd["TotalDemand"]
        s.put(row, "group", _v(rd["group"]), F_INPUT)
        s.put(row, "name", names.get(rd["group"]), F_INPUT)
        s.put(row, "modes", ", ".join(modes), F_INPUT)
        s.put(row, "demand", 0.0 if pd.isna(demand) else float(demand), F_INPUT, INT)
        s.put(row, "lines", int(rd["Total_Unique_Lines"]), F_INPUT)
        s.put(row, "n_modes", len(modes), F_INPUT)
        s.put(row, "n_rail", sum(m in rail for m in modes), F_INPUT)
        for m, k in has_modes:
            s.put(row, k, int(m in modes), F_INPUT)
        L = {k: f"{s.letter(k)}{row}" for k in s.cols}
        s.put(row, "t_demand", f"={L['demand']}>=MinPassengers")
        s.put(row, "t_modes", f"={L['n_modes']}>=MinModes")
        s.put(row, "t_rail", f"=AND({L['n_modes']}>0,{L['n_rail']}={L['n_modes']})")
        s.put(row, "eligible", f"=AND({L['t_demand']},{L['t_modes']},OR(RequireNonRail=0,NOT({L['t_rail']})))", fill=FILL_RESULT)
        nat, met, loc = _xl_str(TIER_NATIONAL), _xl_str(TIER_METRO), _xl_str(TIER_LOCAL)
        s.put(row, "hubtype",
              f"=IF(AND(OR({L['has_hs']}=1,{L['has_iu']}=1),{L['lines']}>=MinLinesTier,{L['demand']}>=NationalMinDemand),{nat},"
              f"IF(AND(OR({L['has_sub']}=1,{L['has_metro']}=1,{L['has_iu']}=1,{L['has_hs']}=1),{L['lines']}>=MinLinesTier,{L['demand']}>=MetroMinDemand),{met},"
              f"IF(AND(OR({L['has_brt']}=1,{L['has_lrt']}=1),{L['lines']}>=MinLinesTier,{L['demand']}>=LocalMinDemand),{loc},"
              f"IF(AND(OR({L['has_iu']}=1,{L['has_hs']}=1,{L['has_sub']}=1),{L['lines']}<MinLinesTier),\"Train Station\",\"Not Hub\"))))",
              fill=FILL_RESULT)
    s.ws.auto_filter.ref = f"A{FIRST_ROW - 1}:{get_column_letter(len(spec))}{s.last}"
    return s


def _hub_columns(s: _Sheet, scored: pd.DataFrame, names: dict, elig: _Sheet) -> None:
    """Columns A-C on every per-hub sheet: group, name (values) and hub type (formula from step 1)."""
    s.header(1, "group", "Group", 8)
    s.header(2, "name", "Hub name", 24)
    s.header(3, "hubtype", "Hub type (from step 1)", 15)
    for i, g in enumerate(scored["group"]):
        row = FIRST_ROW + i
        s.put(row, "group", _v(g), F_INPUT)
        s.put(row, "name", names.get(g), F_INPUT)
        s.put(row, "hubtype", f"=INDEX({elig.ext('hubtype')},MATCH(A{row},{elig.ext('group')},0))", F_LINK)


def _norm_columns(s: _Sheet, col: int, raw_key: str, norm_key: str, norm_label: str, nonzero: bool = False) -> int:
    """Tier min, tier max and the 1-10 normalised value; returns the next free column."""
    s.header(col, "tmin", "Tier minimum" + (" (non-zero)" if nonzero else ""), 11, "Lowest raw value among hubs of the same type")
    s.header(col + 1, "tmax", "Tier maximum" + (" (non-zero)" if nonzero else ""), 11, "Highest raw value among hubs of the same type")
    s.header(col + 2, norm_key, norm_label, 12, "NormMin + (raw - tier min) x (NormMax - NormMin) / (tier max - tier min); NormConst when min = max")
    raw, types = s.rng(raw_key), s.rng("hubtype")
    extra = f',{raw},">0"' if nonzero else ""
    for i in range(s.n):
        row = FIRST_ROW + i
        x, lo, hi = f"{s.letter(raw_key)}{row}", f"{s.letter('tmin')}{row}", f"{s.letter('tmax')}{row}"
        s.put(row, "tmin", f"=_xlfn.MINIFS({raw},{types},C{row}{extra})", fmt=NUM3)
        s.put(row, "tmax", f"=_xlfn.MAXIFS({raw},{types},C{row}{extra})", fmt=NUM3)
        f = f"IF({hi}>{lo},NormMin+({x}-{lo})*(NormMax-NormMin)/({hi}-{lo}),NormConst)"
        if nonzero:
            f = f'IF(COUNTIFS({types},C{row},{raw},">0")=0,NormMin,{f})'
        s.put(row, norm_key, "=" + f, fmt=NUM3, fill=FILL_RESULT)
    return col + 3


def _write_location(wb, scored, names, elig) -> _Sheet:
    s = _Sheet(wb, "2_Location", "Criterion 1 - Location (national region x metropolitan position)",
               "Region: Center / Tel Aviv = RegionWeightCenter, elsewhere = RegionWeightOther (periphery boost). Position: core 3, ring 2, outer 1. Raw = region x position, normalised 1-10 within the hub type.", len(scored))
    _hub_columns(s, scored, names, elig)
    s.header(4, "area", "Area (metro)", 16)
    s.header(5, "location", "Metropolitan position (from base layer)", 18)
    s.header(6, "region", "Region weight", 10, "0 if the area text contains a Center keyword (Parameters), else 1")
    s.header(7, "position", "Position score", 10, "3 core (גלעין / Core), 2 ring (טבעת / Ring), 1 otherwise")
    s.header(8, "raw", "RegionLocation (raw)", 11, "Region weight x position score")
    _norm_columns(s, 9, "raw", "norm", "RegionLocation_Norm (1-10)")
    for i, r in enumerate(scored.itertuples(index=False)):
        row = FIRST_ROW + i
        rd = r._asdict()
        s.put(row, "area", _v(rd.get("area")) or "", F_INPUT)
        s.put(row, "location", _v(rd.get("location")) or "", F_INPUT)
        s.put(row, "region", f"=IF(SUMPRODUCT(--ISNUMBER(FIND(CenterKeywords,D{row})))>0,RegionWeightCenter,RegionWeightOther)")
        s.put(row, "position", f'=IF(OR(ISNUMBER(FIND("גלעין",E{row})),ISNUMBER(FIND("Core",E{row}))),CoreScore,IF(OR(ISNUMBER(FIND("טבעת",E{row})),ISNUMBER(FIND("Ring",E{row}))),RingScore,OuterScore))')
        s.put(row, "raw", f"=F{row}*G{row}")
    return s


def _write_service(wb, scored, names, elig, mode_refs) -> _Sheet:
    s = _Sheet(wb, "3_Service", "Criterion 2 - Service & hierarchy of modes",
               "Raw = Σ(lines of a mode x mode weight) x (1 + ModeAlpha x (number of modes - 1)). Line counts per mode come from the network (each direction is a line). Row 3 = mode weights from Parameters.", len(scored))
    _hub_columns(s, scored, names, elig)
    mode_cols = [c for c in MODE_LINE_COLS if c in scored.columns]
    col = 4
    s.ws.cell(row=3, column=3, value="Mode weight ->").font = F_BOLD
    for c in mode_cols:
        s.header(col, c, c, 10)
        w = s.ws.cell(row=3, column=col, value=f"={mode_refs[c]}")
        w.font, w.fill, w.number_format = F_LINK, FILL_UNIT, NUM2
        col += 1
    first, lastm = get_column_letter(4), get_column_letter(col - 1)
    s.header(col, "nmodes", "Modes with lines", 9, "Number of mode columns with more than 0 lines")
    s.header(col + 1, "weighted", "Weighted lines", 11, "Σ lines x mode weight (row 3)")
    s.header(col + 2, "mult", "Diversity multiplier", 10, "1 + ModeAlpha x (modes - 1)")
    s.header(col + 3, "raw", "Service score (raw)", 11, "Weighted lines x diversity multiplier")
    _norm_columns(s, col + 4, "raw", "norm", "score_Norm (1-10)")
    for i, r in enumerate(scored.itertuples(index=False)):
        row = FIRST_ROW + i
        rd = scored.iloc[i]
        for c in mode_cols:
            s.put(row, c, _v(rd[c]) or 0, F_INPUT, "0.##")
        L = lambda k: f"{s.letter(k)}{row}"  # noqa: E731
        s.put(row, "nmodes", f'=COUNTIF({first}{row}:{lastm}{row},">0")')
        s.put(row, "weighted", f"=SUMPRODUCT({first}{row}:{lastm}{row},${first}$3:${lastm}$3)", fmt=NUM2)
        s.put(row, "mult", f"=IF({L('nmodes')}>0,1+ModeAlpha*({L('nmodes')}-1),1)", fmt=NUM2)
        s.put(row, "raw", f"={L('weighted')}*{L('mult')}", fmt=NUM2)
    return s


def _write_demand(wb, scored, names, elig) -> _Sheet:
    s = _Sheet(wb, "4_Demand", "Criterion 3 - Passenger activity (2050 forecast)",
               "Raw = log10(passengers per day), so a 100,000 station does not score 10x a 10,000 station. Tier min / max are taken over non-zero values.", len(scored))
    _hub_columns(s, scored, names, elig)
    s.header(4, "demand", "Passengers / day (2050)", 13)
    s.header(5, "raw", "log10(passengers)", 11, "0 when passengers = 0")
    _norm_columns(s, 6, "raw", "norm", "TotalDemand_Norm (1-10)", nonzero=True)
    for i, d in enumerate(scored["TotalDemand"]):
        row = FIRST_ROW + i
        s.put(row, "demand", 0.0 if pd.isna(d) else float(d), F_INPUT, INT)
        s.put(row, "raw", f"=IF(D{row}=0,0,LOG10(D{row}))", fmt=NUM4)
    return s


def _write_popjobs(wb, scored, names, elig, rings, ring_refs) -> _Sheet:
    s = _Sheet(wb, "5_PopJobs", "Criterion 4 - Population & jobs 2050 in the catchment rings",
               "Raw = Σ over rings of (pop share x population + jobs share x jobs) / midpoint^DecayBeta. National / Metropolitan hubs weight jobs 80 %, others population 80 %. Row 3 = decay divisor per ring.", len(scored))
    _hub_columns(s, scored, names, elig)
    present = all(p in scored.columns and e in scored.columns for p, e, _, _ in rings)
    col = 4
    for p, e, inner, outer in rings:
        s.header(col, p, f"Population {inner}-{outer} m", 11)
        s.header(col + 1, e, f"Jobs {inner}-{outer} m", 11)
        col += 2
    s.header(col, "wpop", "Population share", 9)
    s.header(col + 1, "wemp", "Jobs share", 9)
    col += 2
    s.ws.cell(row=3, column=col - 1, value="Decay divisor ->").font = F_BOLD
    contrib_keys = []
    for (p, e, inner, outer), ref in zip(rings, ring_refs):
        k = f"c_{inner}_{outer}"
        contrib_keys.append(k)
        s.header(col, k, f"Ring {inner}-{outer} m (decayed)", 12, "(pop share x population + jobs share x jobs) / divisor in row 3")
        d = s.ws.cell(row=3, column=col, value=f"={ref}^DecayBeta")
        d.font, d.fill, d.number_format = F_LINK, FILL_UNIT, "#,##0.0"
        col += 1
    s.header(col, "raw", "PopEmp score (raw)", 11, "Sum of the decayed rings")
    _norm_columns(s, col + 1, "raw", "norm", "PopEmp_Score_Norm (1-10)")
    upper = f"OR(C{{r}}={_xl_str(TIER_NATIONAL)},C{{r}}={_xl_str(TIER_METRO)},C{{r}}=\"National\",C{{r}}=\"Regional\")"
    for i in range(len(scored)):
        row = FIRST_ROW + i
        rd = scored.iloc[i]
        for p, e, _, _ in rings:
            s.put(row, p, float(rd[p]) if present and pd.notna(rd[p]) else 0.0, F_INPUT, INT)
            s.put(row, e, float(rd[e]) if present and pd.notna(rd[e]) else 0.0, F_INPUT, INT)
        u = upper.format(r=row)
        s.put(row, "wpop", f"=IF({u},PopShareUpper,PopShareLower)", fmt="0%")
        s.put(row, "wemp", f"=IF({u},EmpShareUpper,EmpShareLower)", fmt="0%")
        wp, we = f"${s.letter('wpop')}{row}", f"${s.letter('wemp')}{row}"
        for (p, e, _, _), k in zip(rings, contrib_keys):
            s.put(row, k, f"=({wp}*{s.letter(p)}{row}+{we}*{s.letter(e)}{row})/{s.letter(k)}$3", fmt=NUM2)
        s.put(row, "raw", f"=SUM({s.letter(contrib_keys[0])}{row}:{s.letter(contrib_keys[-1])}{row})", fmt=NUM2)
    if not present:
        s.ws["A3"] = "Ring columns were missing in this run: the pipeline set PopEmp_Score_Norm = 5.0 for every hub."
        s.ws["A3"].font = Font(name=FONT, bold=True, color="C00000")
    return s


def _write_terminal(wb, scored, names, elig) -> _Sheet:
    s = _Sheet(wb, "6_BusTerminal", "Criterion 5 - Bus terminal within 200 m",
               "Raw = class of the largest 2050 terminal whose 200 m buffer touches the hub: 0 none, 1 night parking (חניון לילה), 2 small / medium terminal, 3 large terminal / integrated facility.", len(scored))
    _hub_columns(s, scored, names, elig)
    s.header(4, "raw", "Terminal class (0-3)", 11)
    _norm_columns(s, 5, "raw", "norm", "bus_terminal_Norm (1-10)")
    for i, v in enumerate(scored["bus_terminal"]):
        s.put(FIRST_ROW + i, "raw", float(v) if pd.notna(v) else 0.0, F_INPUT, "0")
    return s


def _write_mc(wb, blocks: list[tuple[str, np.ndarray]], cfg) -> None:
    """7b_MC_Draws (raw draws as values, weights as formulas) and 7_MC_Weights (averages,
    exposed as the names ``MC_WeightTable`` / ``MC_WeightTypes``)."""
    ws_w = wb.create_sheet("7_MC_Weights")
    ws_d = wb.create_sheet("7b_MC_Draws")
    n_iter = cfg.mc_iterations
    k = len(SCORING_COLS)

    ws_d["A1"] = "Step 7b - Monte Carlo weight draws (regenerated from the run's seed; identical to the run)"
    ws_d["A1"].font = F_TITLE
    ws_d["A2"] = (f"Each row: {k} uniform random numbers in [0,1); a row with any value above MC_MaxWeight is redrawn (rejected rows are not shown). "
                  "The accepted row is divided by its sum so the weights add to 1. Draw columns are values (Excel cannot replay numpy's generator); weight columns are formulas.")
    ws_d["A2"].font = F_NOTE
    ws_d.freeze_panes = "B5"
    ws_d.cell(row=4, column=1, value="Iteration").font = F_BOLD
    first_data, last_data = 5, 5 + n_iter - 1
    for i in range(n_iter):
        ws_d.cell(row=first_data + i, column=1, value=i + 1)
    block_cols: dict[str, int] = {}
    col = 2
    for name, w in blocks:
        block_cols[name] = col
        ws_d.cell(row=3, column=col, value=f"Hub type: {name}").font = F_BOLD
        for j, c in enumerate(SCORING_COLS):
            h = ws_d.cell(row=4, column=col + j, value=f"draw: {CRITERION_LABELS[c]}")
            h.font, h.fill = F_HEADER, FILL_HEADER
            h2 = ws_d.cell(row=4, column=col + k + j, value=f"weight: {CRITERION_LABELS[c]}")
            h2.font, h2.fill = F_HEADER, FILL_HEADER
            ws_d.column_dimensions[get_column_letter(col + j)].width = 11
            ws_d.column_dimensions[get_column_letter(col + k + j)].width = 11
        a, b = get_column_letter(col), get_column_letter(col + k - 1)
        for i in range(n_iter):
            r = first_data + i
            for j in range(k):
                ws_d.cell(row=r, column=col + j, value=float(w[i, j])).font = F_INPUT
                c = ws_d.cell(row=r, column=col + k + j, value=f"={get_column_letter(col + j)}{r}/SUM(${a}{r}:${b}{r})")
                c.number_format = NUM4
        col += 2 * k + 1

    ws_w["A1"] = "Step 7 - Monte Carlo weights: average of the random weight sets per hub type"
    ws_w["A1"].font = F_TITLE
    notes = [
        f"The run scores each hub {n_iter:,} times, each time with a different random weight set (no criterion above {MAX_CRITERION_WEIGHT:.0%} of the raw draw), and keeps the mean score.",
        "Each iteration's score is Σ (normalised criterion x weight). The mean of a weighted sum is the weighted sum with the mean weights, so",
        "    mean over iterations of Σ norm x w   =   Σ norm x (mean w)        -> the final score on 8_FinalScore uses the averages below.",
        "Scope per_hubtype: each hub type has its own random weight set (one seeded stream, consumed type by type in the order below).",
    ]
    for i, t in enumerate(notes, start=2):
        ws_w.cell(row=i, column=1, value=t).font = F_NOTE
    hdr_row = 7
    headers = ["Hub type", *[f"Mean weight: {CRITERION_LABELS[c]}" for c in SCORING_COLS], "Sum of means", "Iterations", "Highest raw draw (<= MC_MaxWeight)"]
    for j, h in enumerate(headers, start=1):
        c = ws_w.cell(row=hdr_row, column=j, value=h)
        c.font, c.fill, c.alignment, c.border = F_HEADER, FILL_HEADER, Alignment(wrap_text=True, horizontal="center"), BORDER
        ws_w.column_dimensions[get_column_letter(j)].width = 16 if j > 1 else 18
    for bi, (name, _) in enumerate(blocks):
        r = hdr_row + 1 + bi
        bc = block_cols[name]
        ws_w.cell(row=r, column=1, value=name).font = F_INPUT
        for j in range(k):
            L = get_column_letter(bc + k + j)
            c = ws_w.cell(row=r, column=2 + j, value=f"=AVERAGE('7b_MC_Draws'!{L}{first_data}:{L}{last_data})")
            c.font, c.number_format, c.fill, c.border = F_LINK, "0.00%", FILL_RESULT, BORDER
        ws_w.cell(row=r, column=2 + k, value=f"=SUM(B{r}:{get_column_letter(1 + k)}{r})").number_format = "0.00%"
        ws_w.cell(row=r, column=3 + k, value=f"=COUNT('7b_MC_Draws'!{get_column_letter(bc)}{first_data}:{get_column_letter(bc)}{last_data})").number_format = INT
        a, b = get_column_letter(bc), get_column_letter(bc + k - 1)
        ws_w.cell(row=r, column=4 + k, value=f"=MAX('7b_MC_Draws'!{a}{first_data}:{b}{last_data})").number_format = NUM4
    last_w = hdr_row + len(blocks)
    table = f"'7_MC_Weights'!$A${hdr_row + 1}:${get_column_letter(1 + k)}${last_w}"
    _define(wb, "MC_WeightTable", table)
    _define(wb, "MC_WeightTypes", f"'7_MC_Weights'!$A${hdr_row + 1}:$A${last_w}")


def _draw_raw_matrix(rng: np.random.RandomState, n_iter: int, n_criteria: int, max_weight: float) -> np.ndarray:
    """Same loop as :func:`scoring.draw_weight_matrix`, keeping the accepted raw draws."""
    rows = np.empty((n_iter, n_criteria), dtype=float)
    for i in range(n_iter):
        w = rng.rand(n_criteria)
        while np.any(w > max_weight):
            w = rng.rand(n_criteria)
        rows[i] = w
    return rows


def _write_final(wb, scored, names, elig, crit_sheets: dict[str, _Sheet], mc_scope: str) -> _Sheet:
    s = _Sheet(wb, "8_FinalScore", "Step 8 - Final score and ranks",
               "Score = Σ normalised criterion x mean Monte Carlo weight of the hub's type (7_MC_Weights). Contribution columns show how many points each criterion adds. Ranks: higher score = better.", len(scored))
    _hub_columns(s, scored, names, elig)
    col = 4
    for c in SCORING_COLS:
        s.header(col, f"n_{c}", f"{CRITERION_LABELS[c]} (1-10)", 11)
        col += 1
    for c in SCORING_COLS:
        s.header(col, f"w_{c}", f"Weight: {CRITERION_LABELS[c]}", 10)
        col += 1
    for c in SCORING_COLS:
        s.header(col, f"p_{c}", f"Points: {CRITERION_LABELS[c]}", 10, "normalised value x weight")
        col += 1
    s.header(col, "score", "TOTAL SCORE (TotalScore_MC)", 12, "Sum of the points")
    s.header(col + 1, "metro", "Metro area", 14)
    s.header(col + 2, "rank_overall", "Overall rank (Rank_TS_MC)", 10, "Dense rank over every scored hub")
    s.header(col + 3, "rank_type", "Rank within hub type", 10, "Dense rank among hubs of the same type (Rank_By_TS_MC_By_Metro)")
    s.header(col + 4, "rank_final", "RANK (RankByHubTypeMetro)", 11, "National hubs ranked nationwide; other types within their hub type and metro area: 1 + number of hubs in the same group with a higher score")
    score_r, type_r, metro_r = s.rng("score"), s.rng("hubtype"), s.rng("metro")
    for i in range(len(scored)):
        row = FIRST_ROW + i
        for c, sheet in crit_sheets.items():
            s.put(row, f"n_{c}", f"={_q(sheet.name)}!{sheet.letter('norm')}{row}", F_LINK, NUM3)
        key = f'"{ALL_HUBS_BLOCK}"' if mc_scope == "all_hubs" else f"C{row}"
        for j, c in enumerate(SCORING_COLS):
            s.put(row, f"w_{c}", f"=INDEX(MC_WeightTable,MATCH({key},MC_WeightTypes,0),{j + 2})", F_LINK, "0.0%")
        for c in SCORING_COLS:
            s.put(row, f"p_{c}", f"={s.letter('n_' + c)}{row}*{s.letter('w_' + c)}{row}", fmt=NUM3)
        p0, p1 = s.letter(f"p_{SCORING_COLS[0]}"), s.letter(f"p_{SCORING_COLS[-1]}")
        x = f"{s.letter('score')}{row}"
        s.put(row, "score", f"=SUM({p0}{row}:{p1}{row})", fmt=NUM4, fill=FILL_RESULT).font = F_BOLD
        s.put(row, "metro", _v(scored.iloc[i].get("area")) or "", F_INPUT)
        s.put(row, "rank_overall", f"=SUMPRODUCT(({score_r}>{x})/COUNTIF({score_r},{score_r}))+1", fmt="0")
        s.put(row, "rank_type", f"=SUMPRODUCT(({type_r}=C{row})*({score_r}>{x})/COUNTIFS({type_r},{type_r},{score_r},{score_r}))+1", fmt="0")
        m = f"{s.letter('metro')}{row}"
        s.put(row, "rank_final",
              f"=IF(C{row}={_xl_str(TIER_NATIONAL)},SUMPRODUCT(({type_r}=C{row})*({score_r}>{x}))+1,SUMPRODUCT(({type_r}=C{row})*({metro_r}={m})*({score_r}>{x}))+1)",
              fmt="0", fill=FILL_RESULT).font = F_BOLD
    s.ws.auto_filter.ref = f"A{FIRST_ROW - 1}:{get_column_letter(col + 4)}{s.last}"
    return s


_TIER_ORDER = {TIER_NATIONAL: 0, TIER_METRO: 1, TIER_LOCAL: 2, "Train Station": 3, "Not Hub": 4}


def _write_ranking(wb, scored: pd.DataFrame, results: pd.DataFrame, final: _Sheet) -> _Sheet:
    order = scored[["group", "HubType", "area"]].copy()
    rank = results.set_index("group")["RankByHubTypeMetro"] if "RankByHubTypeMetro" in results.columns else pd.Series(dtype=float)
    order["tier_ord"] = order["HubType"].map(_TIER_ORDER).fillna(9)
    # national hubs are ranked nationwide, so they are not grouped by metro area
    order["metro_s"] = [("" if t == TIER_NATIONAL else (_v(a) or "")) for t, a in zip(order["HubType"], order["area"])]
    order["rank"] = order["group"].map(rank).astype(float)
    order = order.sort_values(["tier_ord", "metro_s", "rank", "group"]).reset_index(drop=True)
    s = _Sheet(wb, "9_Ranking", "Step 9 - Ranking (national hubs nationwide; others within hub type and metro area)",
               "Every value is looked up from 8_FinalScore by group, so it follows any change made on Parameters. Row order is the run's ranking (re-sort with the filter if you change parameters).", len(order))
    cols = [("group", "Group", 8), ("name", "Hub name", 26), ("hubtype", "Hub type", 15), ("metro", "Metro area", 14), ("rank_final", "RANK", 8), ("score", "Total score", 11)]
    cols += [(f"p_{c}", f"Points: {CRITERION_LABELS[c]}", 11) for c in SCORING_COLS]
    cols += [(f"n_{c}", f"{CRITERION_LABELS[c]} (1-10)", 11) for c in SCORING_COLS]
    cols += [("rank_overall", "Overall rank", 9), ("rank_type", "Rank within hub type", 10)]
    for j, (k, label, w) in enumerate(cols, start=1):
        s.header(j, k, label, w)
    grp = final.ext("group")
    for i, g in enumerate(order["group"]):
        row = FIRST_ROW + i
        s.put(row, "group", _v(g), F_INPUT)
        for k, _, _ in cols[1:]:
            fmt = NUM4 if k == "score" else ("0" if k.startswith("rank") else (NUM3 if k[:2] in ("p_", "n_") else None))
            c = s.put(row, k, f"=INDEX({final.ext(k)},MATCH($A{row},{grp},0))", F_LINK, fmt)
            if k in ("rank_final", "score"):
                c.fill = FILL_RESULT
    s.ws.auto_filter.ref = f"A{FIRST_ROW - 1}:{get_column_letter(len(cols))}{s.last}"
    return s


def _write_explorer(wb, scored, sheets: dict[str, _Sheet], final: _Sheet, elig: _Sheet) -> None:
    ws = wb.create_sheet("Hub_Explorer")
    ws["A1"] = "Hub explorer - the whole calculation for one hub"
    ws["A1"].font = F_TITLE
    ws["A2"] = "Type or pick a group number in the yellow cell; every line below is looked up from the step sheets."
    ws["A2"].font = F_NOTE
    for col, w in zip("ABCDEFG", (34, 18, 14, 14, 16, 12, 12)):
        ws.column_dimensions[col].width = w
    ws["A4"] = "Group"
    ws["A4"].font = F_BOLD
    ws["B4"] = _v(scored["group"].iloc[0])
    ws["B4"].fill, ws["B4"].font, ws["B4"].border = FILL_KEY, F_INPUT, BORDER
    dv = DataValidation(type="list", formula1=f"={final.ext('group')}", allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("B4")

    def look(sheet: _Sheet, key: str) -> str:
        return f"=INDEX({sheet.ext(key)},MATCH($B$4,{sheet.ext('group')},0))"

    rows = [
        ("Hub name", look(final, "name"), None),
        ("Hub type (tier)", look(final, "hubtype"), None),
        ("Metro area", look(final, "metro"), None),
        ("Passengers / day (2050)", look(elig, "demand"), INT),
        ("Planned modes", look(elig, "modes"), None),
        ("Unique lines", look(elig, "lines"), None),
        ("Eligible", look(elig, "eligible"), None),
    ]
    r = 5
    for label, f, fmt in rows:
        ws.cell(row=r, column=1, value=label).font = F_FORMULA
        c = ws.cell(row=r, column=2, value=f)
        c.font, c.border = F_LINK, BORDER
        if fmt:
            c.number_format = fmt
        r += 1
    r += 1
    heads = ["Criterion", "Raw value", "Tier minimum", "Tier maximum", "Normalised (1-10)", "Weight", "Points"]
    for j, h in enumerate(heads, start=1):
        c = ws.cell(row=r, column=j, value=h)
        c.font, c.fill, c.border = F_HEADER, FILL_HEADER, BORDER
    r += 1
    first = r
    for c in SCORING_COLS:
        sh = sheets[c]
        ws.cell(row=r, column=1, value=f"{CRITERION_LABELS[c]} ({sh.name})").font = F_FORMULA
        for j, (sheet, key, fmt) in enumerate(
            [(sh, "raw", NUM3), (sh, "tmin", NUM3), (sh, "tmax", NUM3), (sh, "norm", NUM3), (final, f"w_{c}", "0.0%"), (final, f"p_{c}", NUM3)], start=2
        ):
            cell = ws.cell(row=r, column=j, value=look(sheet, key))
            cell.font, cell.number_format, cell.border = F_LINK, fmt, BORDER
        r += 1
    ws.cell(row=r, column=1, value="TOTAL SCORE").font = F_BOLD
    c = ws.cell(row=r, column=7, value=f"=SUM(G{first}:G{r - 1})")
    c.font, c.fill, c.number_format, c.border = F_BOLD, FILL_RESULT, NUM4, BORDER
    r += 2
    for label, key in (("RANK (national: nationwide; others: within hub type and metro)", "rank_final"), ("Rank within hub type", "rank_type"), ("Overall rank", "rank_overall")):
        ws.cell(row=r, column=1, value=label).font = F_BOLD if key == "rank_final" else F_FORMULA
        c = ws.cell(row=r, column=2, value=look(final, key))
        c.font, c.border = F_LINK, BORDER
        if key == "rank_final":
            c.fill = FILL_RESULT
        r += 1


def _write_checks(wb, scored: pd.DataFrame, results: pd.DataFrame, sheets: dict[str, _Sheet], final: _Sheet) -> None:
    s = _Sheet(wb, "Checks", "Checks - workbook formulas vs the pipeline's own values",
               "Pipeline values are fixed numbers from this run (blue). A difference means a parameter was changed in this workbook, or a formula disagrees with the code.", len(scored))
    s.header(1, "group", "Group", 8)
    res = results.set_index("group")
    pairs = [(c, f"{CRITERION_LABELS[c]} norm") for c in SCORING_COLS] + [("TotalScore_MC", "Total score"), ("RankByHubTypeMetro", "RANK")]
    col = 2
    for key, label in pairs:
        s.header(col, f"pipe_{key}", f"Pipeline: {label}", 11)
        s.header(col + 1, f"book_{key}", f"Workbook: {label}", 11)
        s.header(col + 2, f"diff_{key}", f"Difference: {label}", 11)
        col += 3
    s.header(col, "pipe_type", "Pipeline: hub type", 14)
    s.header(col + 1, "type_ok", "Hub type matches", 9)
    for i, r in enumerate(scored.itertuples(index=False)):
        row = FIRST_ROW + i
        rd = scored.iloc[i]
        s.put(row, "group", _v(rd["group"]), F_INPUT)
        for key, _ in pairs:
            if key in SCORING_COLS:
                pv, book = rd[key], f"={_q(sheets[key].name)}!{sheets[key].letter('norm')}{row}"
            elif key == "TotalScore_MC":
                pv, book = rd["Average_Simulated_Score"], f"={_q(final.name)}!{final.letter('score')}{row}"
            else:
                pv = res[key].get(rd["group"]) if key in res.columns else None
                book = f"={_q(final.name)}!{final.letter('rank_final')}{row}"
            fmt = "0" if key == "RankByHubTypeMetro" else NUM4
            s.put(row, f"pipe_{key}", _v(pv), F_INPUT, fmt)
            s.put(row, f"book_{key}", book, F_LINK, fmt)
            s.put(row, f"diff_{key}", f"={s.letter('book_' + key)}{row}-{s.letter('pipe_' + key)}{row}", fmt="0.0000E+00" if fmt == NUM4 else "0")
        s.put(row, "pipe_type", _v(rd["HubType"]), F_INPUT)
        s.put(row, "type_ok", f"={_q(final.name)}!C{row}={s.letter('pipe_type')}{row}")
    s.ws["H3"] = "Largest |score difference|:"
    s.ws["H3"].font = F_BOLD
    d = s.rng("diff_TotalScore_MC")
    s.ws["K3"] = f"=MAX(MAX({d}),-MIN({d}))"
    s.ws["K3"].number_format = "0.0000E+00"
    s.ws["M3"] = "Rank mismatches:"
    s.ws["M3"].font = F_BOLD
    s.ws["O3"] = f'=COUNTIF({s.rng("diff_RankByHubTypeMetro")},"<>0")'
    s.ws["Q3"] = "Hub type mismatches:"
    s.ws["Q3"].font = F_BOLD
    s.ws["S3"] = f"=COUNTIF({s.rng('type_ok')},FALSE)"


def _write_readme(ws, cfg, n_groups: int, n_scored: int, version: str | None) -> None:
    ws["A1"] = "Hub prioritisation - calculation workbook (מתח\"מים)"
    ws["A1"].font = Font(name=FONT, bold=True, size=16)
    lines = [
        ("", None),
        ("This workbook reproduces how every hub got its score and rank, with Excel formulas you can inspect and change.", None),
        ("The display workbook (hub_prioritization_results.xlsx) is unchanged; this file is an additional output of `hubs run`.", None),
        ("", None),
        ("Run", F_BOLD),
        (f"Version: {version or '-'}    Hub groups: {n_groups}    Scored hubs: {n_scored}    Monte Carlo: {cfg.mc_iterations:,} iterations, seed {cfg.mc_seed}, scope {cfg.mc_scope}", None),
        ("", None),
        ("Sheets (in process order)", F_BOLD),
        ("Parameters      every threshold and weight; the formulas refer to these cells by name (yellow = key levers)", None),
        ("1_Eligibility   every hub group: >= MinPassengers, >= MinModes planned modes, not rail-only -> eligible; tier rules -> hub type", None),
        ("2_Location      criterion 1: region weight x metropolitan position", None),
        ("3_Service       criterion 2: Σ lines x mode weight x diversity bonus", None),
        ("4_Demand        criterion 3: log10 of 2050 passengers", None),
        ("5_PopJobs       criterion 4: population and jobs 2050 in catchment rings with distance decay", None),
        ("6_BusTerminal   criterion 5: class of the 2050 bus terminal within 200 m", None),
        ("                each criterion: raw value -> 1-10 within the hub type: 1 + (raw - tier min) x 9 / (tier max - tier min)", None),
        ("7_MC_Weights    mean of the random weight sets per hub type (7b_MC_Draws holds the draws)", None),
        ("8_FinalScore    Σ normalised criterion x mean weight = TotalScore_MC; points per criterion; the three ranks", None),
        ("9_Ranking       the ranking: national hubs nationwide, metropolitan and local hubs within their metro area", None),
        ("Hub_Explorer    choose a hub and read its whole calculation on one page", None),
        ("Checks          workbook values next to the pipeline's values (differences should be ~0)", None),
        ("", None),
        ("Colours", F_BOLD),
        ("Blue text = data from the pipeline run (inputs) · black = formula · green = formula linking another sheet · yellow fill = key parameter · green fill = result", None),
        ("", None),
        ("Notes", F_BOLD),
        ("The rows (which hubs are scored) are fixed by the run. Changing an eligibility threshold updates the ELIGIBLE flag and hub types but does not add or remove rows.", None),
        ("A changed tier rule that creates a hub type with no Monte Carlo weight set shows a not-available error on 8_FinalScore (each type has its own draws).", None),
        ("Requires Excel 2019 / Microsoft 365 (MINIFS / MAXIFS). Raw inputs (line counts, demand, population/jobs per ring, area, terminal class) come from the network, demand model and H3 base layer stages of the pipeline.", None),
    ]
    if cfg.renormalize_globally:
        lines.append(("renormalize_globally=true: the display workbook's *_Norm columns are global; this workbook shows the per-tier values the Monte Carlo actually used.", Font(name=FONT, bold=True, color="C00000")))
    for i, (t, f) in enumerate(lines, start=2):
        c = ws.cell(row=i, column=1, value=t)
        c.font = f or F_FORMULA
    ws.column_dimensions["A"].width = 140


# ----------------------------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------------------------


def write_calculation_workbook(
    groups: pd.DataFrame,
    scored: pd.DataFrame,
    results: pd.DataFrame,
    cfg,
    path: Path | str,
    version: str | None = None,
) -> Path:
    """Write the formula workbook that recomputes eligibility, the five criteria, the Monte
    Carlo weights, the final score and the ranks.

    ``groups`` are the aggregated hub groups as passed to :func:`scoring.score_hubs`
    (geometry dropped), ``scored`` its output, ``results`` the final display table.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    scored = scored.sort_values("group").reset_index(drop=True)
    pre = eligibility_frame(pd.DataFrame(groups), cfg)
    names = {}
    if "HubNameHE" in results.columns:
        names = {g: (_v(n) if _v(n) else None) for g, n in zip(results["group"], results["HubNameHE"])}

    wb = Workbook()
    wb._named_styles["Normal"].font = Font(name=FONT, size=10)
    readme = wb.active
    readme.title = "README"
    _write_readme(readme, cfg, len(pre), len(scored), version)
    refs = _write_parameters(wb, cfg)
    elig = _write_eligibility(wb, pre, names)
    sheets = {
        "RegionLocation_Norm": _write_location(wb, scored, names, elig),
        "score_Norm": _write_service(wb, scored, names, elig, refs["mode_refs"]),
        "TotalDemand_Norm": _write_demand(wb, scored, names, elig),
        "PopEmp_Score_Norm": _write_popjobs(wb, scored, names, elig, refs["rings"], refs["ring_refs"]),
        "bus_terminal_Norm": _write_terminal(wb, scored, names, elig),
    }

    _write_mc(wb, mc_blocks(scored, cfg), cfg)

    final = _write_final(wb, scored, names, elig, sheets, cfg.mc_scope)
    _write_ranking(wb, scored, results, final)
    _write_explorer(wb, scored, sheets, final, elig)
    _write_checks(wb, scored, results, sheets, final)
    order = ["README", "Parameters", "1_Eligibility", "2_Location", "3_Service", "4_Demand", "5_PopJobs", "6_BusTerminal",
             "7_MC_Weights", "8_FinalScore", "9_Ranking", "Hub_Explorer", "Checks", "7b_MC_Draws"]
    wb._sheets = [wb[n] for n in order]
    wb.active = 0
    wb.save(path)
    return path
