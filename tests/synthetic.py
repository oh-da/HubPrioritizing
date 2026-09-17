"""Build a complete, tiny synthetic input + reference directory for end-to-end tests.

Two hubs near Tel Aviv (ITM 180000/665000): hub A with LRT + Metro + suburban rail and
high demand, hub B with BRT + LRT and low demand, plus a lone rail-only node.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, box

CRS_ITM = "EPSG:2039"


def make_synthetic_dirs(root: Path, with_base_layer: bool = True) -> tuple[Path, Path]:
    """Write the synthetic run inputs and reference layers; ``with_base_layer`` also builds
    ``h3_base.parquet`` from them so the default (``spatial_source=h3_base``) path runs."""
    input_dir = root / "input"
    ref_dir = root / "reference"
    input_dir.mkdir(parents=True, exist_ok=True)
    ref_dir.mkdir(parents=True, exist_ok=True)

    # --- nodes x lines (EPSG:2039) ---------------------------------------------------------
    rows = [
        # hub A: nodes 1 (LRT Red both directions), 2 (Metro M1 both directions), 3 (rail)
        (1, "Red-N", 180000, 665000), (1, "Red-S", 180000, 665000),
        (2, "Me1-N", 180030, 665000), (2, "Me1-S", 180030, 665000),
        (3, "rail_1_1", 180060, 665020), (3, "rail_1_2", 180060, 665020),
        # hub B: node 4 (BRT) and node 5 (LRT), 2 km east
        (4, "Yelw-N", 182000, 665000), (4, "Yelw-S", 182000, 665000),
        (5, "Grn1-N", 182040, 665000), (5, "Grn1-S", 182040, 665000),
        # far node 9: rail only, single mode
        (9, "rail_2_1", 190000, 665000), (9, "rail_2_2", 190000, 665000),
        # a line with no mode row
        (5, "X9", 182040, 665000),
    ]
    nodes = pd.DataFrame(rows, columns=["node", "LINE_ID", "X", "Y"])
    nodes.insert(0, "עמודה1", range(len(nodes)))
    nodes.to_csv(input_dir / "All_nodeslines_01012030.csv", index=False, encoding="cp1255")

    lines = pd.DataFrame(
        {
            "Line_ModelName": ["Red-N", "Red-S", "Me1-N", "Me1-S", "rail_1_1", "rail_1_2", "Yelw-N", "Yelw-S", "Grn1-N", "Grn1-S", "rail_2_1", "rail_2_2", "m0810a", "m0810a"],
            "Mode_Planned": ["LRT", "LRT", "Metro", "Metro", "Suburban Rail", "Suburban Rail", "BRT", "BRT", "LRT", "LRT", "Interurban Rail", "Interurban Rail", "BRT", "BRT"],
            "Line_Name": ["אדום"] * 2 + ["מטרו"] * 2 + ["רכבת"] * 2 + ["צהוב"] * 2 + ["ירוק"] * 2 + ["רכבת"] * 2 + ["מטרונית"] * 2,
            "Line_Description": ["x"] * 14,
            "Area": ["Tel Aviv"] * 10 + ["National"] * 2 + ["Haifa"] * 2,
        }
    )
    lines.to_csv(input_dir / "Lines_and_Planned_Mode_01-01-2030.csv", index=False, encoding="cp1255")

    with pd.ExcelWriter(input_dir / "Nodes_w_results_01012030.xlsx") as xw:
        pd.DataFrame(
            {"Node": [1, 2, 3, 4, 5], "TotalBoardings": [30000, 20000, 10000, 800, 700], "TotalAlight": [30000, 20000, 10000, 800, 700], "TransferBoardings": [5000, 4000, 0, 0, 0], "TransferAlight": [1000, 0, 0, 0, 0]}
        ).to_excel(xw, sheet_name="Daily_5087", index=False)
        pd.DataFrame({"Node": [9], "TotalBoardings": [100], "TotalAlight": [100]}).to_excel(xw, sheet_name="5040_Daily", index=False)
        pd.DataFrame({"TLV": ["am"], "ini": [1]}).to_excel(xw, sheet_name="Params", index=False)

    pd.DataFrame([["Red-N", 'אדום צפון (רק"ל)'], ["Red-S", 'אדום דרום (רק"ל)'], ["Line_Unique_List", "Line_n_Mode"], ["Yelw-N", "צהוב צפון (BRT)"]]).to_csv(
        input_dir / "linesNames_noDuplicates.csv", index=False, header=False, encoding="cp1255"
    )
    pd.DataFrame({"": [0, 1, 1, 2], "LineName": ["0", "Red-N", " Red-S", "Yelw-N"], "StatusID": [0, 0, 0, 6]}).to_csv(input_dir / "lines_exploded.csv", index=False, encoding="utf-8")
    pd.DataFrame({"ID": [1], "LineName": ["\\Grn1-N\\"], "LineName_Correct": ["Grn1-N"]}).to_csv(input_dir / "BS_lines.csv", index=False, encoding="utf-8-sig")

    # --- reference layers --------------------------------------------------------------------
    metro = gpd.GeoDataFrame(
        {"METRO_NAME": ["תל אביב", "תל אביב"], "ZONE_NAME": ["גלעין", "טבעת פנימית"]},
        geometry=[box(179000, 664000, 181000, 666000), box(181000, 664000, 183000, 666000)],
        crs=CRS_ITM,
    ).to_crs("EPSG:4326")
    metro.to_file(ref_dir / "metro_2008.shp", encoding="utf-8")
    districts = gpd.GeoDataFrame({"MACHOZ": ["מחוז חיפה"]}, geometry=[box(170000, 660000, 200000, 670000)], crs=CRS_ITM).to_crs("EPSG:4326")
    districts.to_file(ref_dir / "Districts.shp", encoding="utf-8")
    terminals = gpd.GeoDataFrame({"id": [1, 2], "term_type": ["מסוף גדול", "חניון לילה"]}, geometry=[Point(180100, 665050), Point(182100, 665000)], crs=CRS_ITM)
    terminals.to_file(ref_dir / "BUS_TERMINAL_STRAT.shp", encoding="utf-8")
    taz = gpd.GeoDataFrame(
        {"POP_2050": [4000.0, 1000.0, 300.0], "EMPL_2050": [2000.0, 500.0, 100.0]},
        geometry=[box(179000, 664000, 181000, 666000), box(181000, 664000, 183000, 666000), box(189000, 664000, 191000, 666000)],
        crs=CRS_ITM,
    )
    taz.to_file(ref_dir / "TAZ_1270.shp")
    pd.DataFrame({"Nodes in group": ["1, 3"]}).to_csv(ref_dir / "is_same_group.csv", index=False)
    pd.DataFrame({"node": [4], "total_demand": [2500], "total_transfers": [""], "station_name": ["hub B override"], "notes": ["test"]}).to_csv(ref_dir / "manual_demand_updates.csv", index=False)
    pd.DataFrame({"LineName": ["Me1-N"], "Line_n_Mode": ["מטרו צפון (מטרו)"], "notes": ["x"]}).to_csv(ref_dir / "line_names_extra.csv", index=False, encoding="utf-8-sig")
    if with_base_layer:
        build_synthetic_base_layer(ref_dir)
    return input_dir, ref_dir


def build_synthetic_base_layer(ref_dir: Path, resolution: int = 10) -> Path:
    """``h3_base.parquet`` (+ manifest) from the synthetic shapefiles in ``ref_dir``."""
    from src.pipeline.base_layer import build_base_layer, build_manifest, write_base_layer
    from src.pipeline.inputs import read_shapefile

    metro, _ = read_shapefile(ref_dir / "metro_2008.shp", hebrew_columns=["METRO_NAME", "ZONE_NAME"])
    districts, _ = read_shapefile(ref_dir / "Districts.shp", hebrew_columns=["MACHOZ"])
    terminals, _ = read_shapefile(ref_dir / "BUS_TERMINAL_STRAT.shp", hebrew_columns=["term_type"])
    taz, _ = read_shapefile(ref_dir / "TAZ_1270.shp")
    layer = build_base_layer(metro, districts, terminals, taz, resolution, 200.0)
    sources = {k: ref_dir / f for k, f in (("metro", "metro_2008.shp"), ("districts", "Districts.shp"), ("bus_terminals", "BUS_TERMINAL_STRAT.shp"), ("taz", "TAZ_1270.shp"))}
    return write_base_layer(layer, ref_dir / "h3_base.parquet", build_manifest(sources, resolution, 200.0, len(layer)))


def write_hub_names(ref_dir: Path, hexes_by_group: dict[int, list[str]], names: dict[int, str]) -> Path:
    rows = [{"name_id": g, "h3_index": h, "HubNameHE": names[g]} for g, hs in hexes_by_group.items() if g in names for h in hs]
    path = ref_dir / "hub_names.csv"
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path
