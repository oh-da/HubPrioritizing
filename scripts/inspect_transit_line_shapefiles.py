#!/usr/bin/env python3
"""
Transit Line Shapefile Inspection
==================================
Read-only diagnostic for the network centrality analysis. Run this FIRST,
before the full analysis: it catalogs the per-line shapefiles and checks
they can be matched to the LINE_IDs in the nodes CSV.

Usage:
    python scripts/inspect_transit_line_shapefiles.py \
        --lines-dir data/raw/transit_lines \
        --nodes-csv data/raw/All_nodes+lines.csv \
        --lines-modes-csv data/raw/Lines_and_Planned_Mode.csv

Reports:
- Per shapefile: CRS, geometry types, feature count, attribute columns
- Which attribute column (or filename) best matches LINE_ID values
- Coverage: in-scope lines with/without a geometry
- Whether direction pairs (e.g. rail_1_1/rail_1_2) share node IDs
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402

from src.config import (  # noqa: E402
    TRANSIT_LINES_DIR,
    CENTRALITY_MODES,
    LINE_SHAPEFILE_MAPPING_CSV,
    RESULTS_DIR,
)
from src.data.loaders import load_transit_nodes, load_lines_and_modes  # noqa: E402
from src.network.graph_builder import (  # noqa: E402
    load_line_geometries,
    match_lines_to_shapefiles,
)
from src.utils.logging import setup_logger  # noqa: E402

logger = setup_logger(__name__)


def inspect_shapefiles(lines_dir: Path) -> None:
    """Print a per-shapefile catalog."""
    shp_files = sorted(Path(lines_dir).rglob("*.shp"))
    print(f"\n{'=' * 78}\nSHAPEFILE CATALOG ({len(shp_files)} files under "
          f"{lines_dir})\n{'=' * 78}")
    for shp in shp_files:
        try:
            gdf = gpd.read_file(shp)
        except Exception as e:
            print(f"\n✗ {shp.name}: FAILED TO READ ({e})")
            continue
        geom_types = gdf.geometry.geom_type.value_counts().to_dict()
        attrs = [c for c in gdf.columns if c != 'geometry']
        print(f"\n• {shp.relative_to(lines_dir)}")
        print(f"  CRS: {gdf.crs} | features: {len(gdf)} | "
              f"geometry: {geom_types}")
        print(f"  attributes: {attrs}")
        for col in attrs[:6]:
            sample = gdf[col].dropna().astype(str).unique()[:4].tolist()
            print(f"    {col}: {sample}")


def check_direction_pairs(nodes_gdf: gpd.GeoDataFrame) -> None:
    """Check whether *_1/*_2 direction pairs share node IDs."""
    line_ids = sorted(nodes_gdf['LINE_ID'].astype(str).unique())
    pairs = []
    for lid in line_ids:
        if lid.endswith('_1') and (lid[:-2] + '_2') in line_ids:
            pairs.append((lid, lid[:-2] + '_2'))

    print(f"\n{'=' * 78}\nDIRECTION PAIR CHECK ({len(pairs)} pairs found)"
          f"\n{'=' * 78}")
    if not pairs:
        print("No *_1/*_2 direction pairs detected in LINE_ID values.")
        return

    n_shared, n_disjoint = 0, 0
    disjoint_examples = []
    for a, b in pairs:
        nodes_a = set(nodes_gdf.loc[nodes_gdf['LINE_ID'] == a, 'node'])
        nodes_b = set(nodes_gdf.loc[nodes_gdf['LINE_ID'] == b, 'node'])
        overlap = len(nodes_a & nodes_b) / max(min(len(nodes_a),
                                                   len(nodes_b)), 1)
        if overlap >= 0.5:
            n_shared += 1
        else:
            n_disjoint += 1
            if len(disjoint_examples) < 5:
                disjoint_examples.append((a, b, round(overlap, 2)))

    print(f"Pairs sharing ≥50% of node IDs: {n_shared}")
    print(f"Pairs with mostly distinct node IDs: {n_disjoint}")
    if n_disjoint:
        print("⚠️  Distinct-ID direction pairs mean opposite platforms are "
              "separate stations.\n   Non-hub stations will appear as "
              "parallel duplicated chains — consider a\n   pre-contraction "
              "proximity merge (see plan risk #2). Examples: "
              f"{disjoint_examples}")


def main():
    parser = argparse.ArgumentParser(
        description="Inspect transit line shapefiles for centrality analysis")
    parser.add_argument('--lines-dir', type=Path, default=TRANSIT_LINES_DIR)
    parser.add_argument('--nodes-csv', type=Path, required=True)
    parser.add_argument('--lines-modes-csv', type=Path, required=True)
    parser.add_argument('--save-qa', action='store_true',
                        help='Save match report CSV to data/results/')
    args = parser.parse_args()

    inspect_shapefiles(args.lines_dir)

    nodes_gdf = load_transit_nodes(args.nodes_csv)
    lines_modes = load_lines_and_modes(args.lines_modes_csv)

    mode_by_line = lines_modes.set_index(
        lines_modes['Line_ModelName'].astype(str))['Mode_Planned'].to_dict()
    all_lines = set(nodes_gdf['LINE_ID'].astype(str).unique())
    in_scope = {l for l in all_lines
                if mode_by_line.get(l) in CENTRALITY_MODES}

    print(f"\n{'=' * 78}\nLINE COVERAGE\n{'=' * 78}")
    print(f"Lines in nodes CSV: {len(all_lines)}")
    print(f"In-scope (modes {sorted(CENTRALITY_MODES)}): {len(in_scope)}")

    manual = None
    if LINE_SHAPEFILE_MAPPING_CSV.exists():
        manual = pd.read_csv(LINE_SHAPEFILE_MAPPING_CSV)
        print(f"Manual mapping CSV found: {len(manual)} rows")

    line_geoms = load_line_geometries(args.lines_dir)
    geom_by_line, report = match_lines_to_shapefiles(
        in_scope, line_geoms, manual_mapping=manual)

    by_strategy = report['matched_by'].value_counts().to_dict()
    print(f"\nMatch summary: {by_strategy}")
    unmatched = report[report['matched_by'] == 'UNMATCHED']['LINE_ID']
    if len(unmatched):
        print(f"⚠️  {len(unmatched)} unmatched lines: "
              f"{unmatched.tolist()[:20]}"
              f"{'...' if len(unmatched) > 20 else ''}")
        print("   Fix via attribute naming or "
              f"{LINE_SHAPEFILE_MAPPING_CSV.name}")

    check_direction_pairs(nodes_gdf)

    if args.save_qa:
        out = RESULTS_DIR / 'line_shapefile_match_report.csv'
        report.to_csv(out, index=False, encoding='utf-8-sig')
        print(f"\n✓ Match report saved to {out}")


if __name__ == '__main__':
    main()
