"""
Write the results: the display workbook, a CSV twin and the hub identity table.

``FINAL_COLUMNS`` is the exact 70-column order of ``hub_prioritization_results.xlsx``
as consumed by the display page. The workbook holds one sheet with one Excel Table;
values only (no formulas).
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

FINAL_COLUMNS: tuple[str, ...] = (
    "group", "x", "y", "h3_index", "node", "Mode_Planned", "Modes_ForPlot", "Line_Unique", "Line_Names",
    "address", "area", "Metro", "location", "LocationForChart",
    "TotalDemand", "TotalTransfers", "TransferRate",
    "BRT Lines", "Cable Line Lines", "Funicular Lines", "HighSpeed Rail Lines", "Interurban Rail Lines",
    "LRT Lines", "Metro Lines", "Suburban Rail Lines",
    "pop_0_500", "emp_0_500", "pop_500_1000", "emp_500_1000", "pop_1000_1500", "emp_1000_1500",
    "TotalPop_2050", "TotalEmp_2050",
    "Region_category", "Location_category", "RegionLocation", "Num_Modes", "score", "bus_terminal",
    "HubType", "HubType_Filtered", "HubTypeHE", "BusTERMINAL_Clone",
    "RegionLocation_Norm", "score_Norm", "bus_terminal_Norm", "TotalDemand_Norm", "PopEmp_Score_Norm",
    "TotalScore_MC", "Rank_TS_MC", "Rank_By_TS_MC_By_Metro", "TotalNumLines",
    "NumLinesStatus_0", "NumLinesStatus_1", "NumLinesStatus_2", "NumLinesStatus_3",
    "NumLinesStatus_4", "NumLinesStatus_5", "NumLinesStatus_6", "NumLinesStatus_7", "TotalLinesAllStatuses",
    "Line_Nunique", "Average_Simulated_Score", "Overall_Rank", "Rank_within_HubType", "LogDemand", "PopEmp_Score",
    "HubNameHE", "Line_Names_forPlot", "RankByHubTypeMetro",
)

LIST_COLUMNS = ("h3_index", "node", "Mode_Planned", "Line_Unique", "location")


def select_final_columns(df: pd.DataFrame, extra_columns: Sequence[str] = ()) -> pd.DataFrame:
    """Return the 70 display columns in order (missing ones raise) plus any ``extra_columns``."""
    missing = [c for c in FINAL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"final table is missing columns {missing}")
    extras = [c for c in extra_columns if c in df.columns and c not in FINAL_COLUMNS]
    out = df[list(FINAL_COLUMNS) + extras].copy()
    for col in LIST_COLUMNS:
        out[col] = out[col].map(lambda v: str(list(v)) if isinstance(v, (list, tuple)) else ("" if v is None else str(v)))
    return out


def _cell_value(v):
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if pd.api.types.is_scalar(v) and pd.isna(v):
        return None
    if hasattr(v, "item"):  # numpy scalar
        return v.item()
    return v


def write_results_xlsx(
    df: pd.DataFrame,
    path: Path | str,
    *,
    sheet_name: str = "hubs_final_results",
    table_name: str = "טבלה1",
    extra_columns: Sequence[str] = (),
) -> Path:
    """Write the display workbook: one sheet, one Excel Table over all rows, values only."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = select_final_columns(df, extra_columns)

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]
    ws.append(list(table.columns))
    for row in table.itertuples(index=False):
        ws.append([_cell_value(v) for v in row])

    n_rows, n_cols = len(table) + 1, len(table.columns)
    ref = f"A1:{get_column_letter(n_cols)}{max(n_rows, 2)}"
    xl_table = Table(displayName=table_name, ref=ref)
    xl_table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(xl_table)
    ws.freeze_panes = "B2"
    for i, col in enumerate(table.columns, start=1):
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, len(str(col)) + 2), 40)
    wb.save(path)
    return path


def write_results_csv(df: pd.DataFrame, path: Path | str, extra_columns: Sequence[str] = ()) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    select_final_columns(df, extra_columns).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def read_results_xlsx(path: Path | str) -> pd.DataFrame:
    """Read a results workbook back (first sheet) for verification."""
    return pd.read_excel(path)
