"""Synthetic planning-agency inputs for the network-comparison tests.

Mirrors the layout of ``MT_Network.gpkg`` (layers ``lines`` and ``stations``, real column
names) and ``MT_Network_MetaData.xlsx``, positioned on the synthetic run of
``tests/synthetic.py`` (hub A nodes 1-3 near ITM 180000/665000, hub B nodes 4-5 near
182000/665000, lone rail node 9 at 190000/665000).

Agency side (ITM, EPSG:2039):

* hub 101 ("hub A"): LRT 1001 + Metro 2001 + Rail A stops within 60 m of nodes 1-3, ``rail_hub``
* hub 102 ("hub B", ``hub_id`` stored as float like the real file): BRT 3001 + LRT 1002
* hub 7 (agency only, x = 195000): LRT 4001 + LRT 4002, only placeholder names ``"- 7"``
* ``Rail`` features with ``line_id = 0``: ``Rail A`` (two features), ``Rail B``
* LRT 5001 has no stations; one rail station is 300 m from every rail feature
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiLineString, Point

CRS_ITM = "EPSG:2039"

HUB_A, HUB_B, HUB_EAST = 101, 102, 7


def _line(*coords: tuple[float, float]) -> MultiLineString:
    return MultiLineString([LineString(coords)])


def _lines_frame() -> gpd.GeoDataFrame:
    rows = [
        # type, line_id, line_name, year_operation, year_cancel, name, plan, source_name, geometry
        ("LRT", 1001, "Red", 2040, None, "Test LRT 1001", "detailed", None,
         _line((179950, 665000), (180100, 665000))),
        ("Metro", 2001, "M1", 2050, None, "Test Metro 2001", "strategic", "tel aviv 2050",
         _line((180030, 664900), (180030, 665100))),
        ("Rail", 0, None, 2026, None, "Rail A", "detailed", None,
         _line((180060, 664900), (180060, 665020))),
        ("Rail", 0, None, 2026, None, "Rail A", "detailed", None,
         _line((180060, 665020), (180060, 665200))),
        ("Rail", 0, None, 2026, None, "Rail B", "detailed", None,
         _line((189800, 665000), (190200, 665000))),
        ("BRT", 3001, "Yellow", 2045, None, "Test BRT 3001", "strategic", "haifa 2050",
         _line((181900, 665000), (182100, 665000))),
        ("LRT", 1002, "Green", 2045, "2060", "Test LRT 1002", "strategic", "tel aviv 2050",
         _line((182040, 664900), (182040, 665100))),
        ("LRT", 4001, None, 2050, None, "East LRT 4001", "strategic", "south 2050",
         _line((194900, 665000), (195100, 665000))),
        ("LRT", 4002, None, 2050, None, "East LRT 4002", "strategic", "south 2050",
         _line((195000, 664900), (195000, 665100))),
        ("LRT", 5001, None, 2050, None, "Lonely LRT 5001", "strategic", None,
         _line((200000, 665000), (200200, 665000))),
    ]
    cols = ["type", "line_id", "line_name", "year_operation", "year_cancel", "name",
            "source_plan", "source_name", "geometry"]
    return gpd.GeoDataFrame(pd.DataFrame(rows, columns=cols), geometry="geometry", crs=CRS_ITM)


def _stations_frame() -> gpd.GeoDataFrame:
    # type, line_id, station_name, hub_id, rail_hub, x, y
    rows = [
        # hub A (rail hub): three stops, one per mode, repeated suffix names
        ("LRT", 1001, "אליעזר בן יהודה - 471", HUB_A, 1.0, 180000, 665000),
        ("Metro", 2001, "אליעזר בן יהודה - 12", HUB_A, 1.0, 180030, 665000),
        ("Rail", 0, "אליעזר בן יהודה - 3", HUB_A, 1.0, 180060, 665020),
        # non-hub stops of the same routes
        ("LRT", 1001, "- 239", None, None, 179950, 665000),
        ("LRT", 1001, "406 - 4", None, None, 180100, 665000),
        ("Metro", 2001, "- 5", None, None, 180030, 664900),
        ("Rail", 0, "תחנה א - 1", None, None, 180060, 665150),
        # hub B: BRT + LRT, no rail
        ("BRT", 3001, "שדרות הנשיא - 5", HUB_B, None, 182000, 665000),
        ("LRT", 1002, "שדרות הנשיא - 9", HUB_B, None, 182040, 665000),
        ("BRT", 3001, "- 2", None, None, 181900, 665000),
        # agency-only hub far east: two LRT routes, placeholder names only
        ("LRT", 4001, "- 7", HUB_EAST, None, 195000, 665000),
        ("LRT", 4002, "- 8", HUB_EAST, None, 195000, 665010),
        ("LRT", 4001, "- 9", None, None, 194900, 665000),
        # rail B: one station on the line, one 300 m from every rail feature
        ("Rail", 0, "תחנה ב - 1", None, None, 190000, 665100),
        ("Rail", 0, "תחנה רחוקה - 2", None, None, 190000, 665300),
    ]
    out = pd.DataFrame(rows, columns=["type", "line_id", "station_name", "hub_id", "rail_hub",
                                      "x", "y"])
    out["hub_id"] = out["hub_id"].astype("float64")
    out["rail_hub"] = out["rail_hub"].astype("float64")
    out["line_name"] = None
    out["year_operation"] = 2040
    out["year_cancel"] = float("nan")
    out["source_plan"] = "strategic"
    out["source_name"] = None
    out["stop_id"] = [f"s{i + 1}" for i in range(len(out))]
    out["hub_stop_id"] = [
        f"hub_{int(h)}" if pd.notna(h) else f"stop_{s}"
        for h, s in zip(out["hub_id"], out["stop_id"])
    ]
    geom = [Point(x, y) for x, y in zip(out.pop("x"), out.pop("y"))]
    return gpd.GeoDataFrame(out, geometry=geom, crs=CRS_ITM)


def make_agency_gpkg(path: Path, crs: str = CRS_ITM) -> Path:
    """Write the synthetic agency GeoPackage (layers ``lines`` and ``stations``).

    Args:
        path: Target ``.gpkg`` file.
        crs: CRS the layers are stored in; the ITM geometry is reprojected to it.

    Returns:
        ``path``.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    for layer, frame in (("lines", _lines_frame()), ("stations", _stations_frame())):
        frame.to_crs(crs).to_file(path, layer=layer, driver="GPKG")
    return path


def make_metadata_xlsx(path: Path) -> Path:
    """Write a copy of the layout of ``MT_Network_MetaData.xlsx`` (code dictionary)."""
    header = ["type", "סוג אמצעי", "line_id", "מספר קו", "year operation", "שנת הפעלה",
              "year cancel", "שנת ביטול", "source plan", "מקור", "source name", "שם תכנית"]
    blank = [None] * 12

    def row(type_, heb, plan=None, plan_heb=None):
        r = list(blank)
        r[0], r[1], r[8], r[9] = type_, heb, plan, plan_heb
        return r

    rows = [
        header,
        row("BRT", 'תאו"מ', "strategic", "תכנית אסטרטגית"),
        row("LRT", 'רק"ל', "detailed", "תכנית מפורטת"),
        row("metro", "מטרו"),
        row("rail", "רכבת כבדה"),
        row("rail fast", "רכבת מהירה"),
    ]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, header=False, index=False)
    return path


def make_tod_gpkg(path: Path, crs: str = "EPSG:4326") -> Path:
    """Write a scraped-TOD-map stand-in: layer ``stations`` with ``hub_id, n_modes, type_sum``.

    Two hubs (ids 11 and 12, two stations each) and two non-hub stations, positions in ITM
    reprojected to ``crs``: hub 11 around (180000, 665000), hub 12 around (182000, 665000).
    """
    rows = [
        (11.0, 3, 3.0, 179990, 665000),
        (11.0, 3, 3.0, 180010, 665020),
        (12.0, 2, 2.0, 181990, 665000),
        (12.0, 2, 2.0, 182030, 665000),
        (None, 1, None, 190000, 665000),
        (None, 1, None, 195000, 665000),
    ]
    df = pd.DataFrame(rows, columns=["hub_id", "n_modes", "type_sum", "x", "y"])
    geom = [Point(x, y) for x, y in zip(df.pop("x"), df.pop("y"))]
    gdf = gpd.GeoDataFrame(df, geometry=geom, crs=CRS_ITM).to_crs(crs)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    gdf.to_file(path, layer="stations", driver="GPKG")
    return path
