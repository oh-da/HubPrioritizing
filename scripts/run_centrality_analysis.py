#!/usr/bin/env python3
"""
Network Centrality Analysis Runner
===================================
Standalone validation study: builds the planned mass-transit network graph
from per-line polyline shapefiles, contracts stations into hubs, computes
weighted betweenness/closeness/degree, and compares against the Monte Carlo
hub rankings.

Usage:
    # Run the shapefile inspection first:
    python scripts/inspect_transit_line_shapefiles.py --nodes-csv ... --lines-modes-csv ...

    # Then the full analysis:
    python scripts/run_centrality_analysis.py \
        --nodes-csv data/raw/All_nodes+lines.csv \
        --lines-modes-csv data/raw/Lines_and_Planned_Mode.csv \
        --scored-hubs data/results/scored_hubs_final.csv \
        --lines-dir data/raw/transit_lines

Outputs (data/results/):
    network_centrality_by_hub.csv       hub-level metrics joined to rankings
    network_centrality_stations.csv     station/singleton-level metrics
    graph_build_qa.csv                  per-line construction QA
    centrality_validation_report.md     correlations, overlaps, divergences
    centrality_vs_ranking_scatter.png   betweenness vs MC score
    network_centrality_map.html         interactive Folium map
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd  # noqa: E402

from src.config import (  # noqa: E402
    TRANSIT_LINES_DIR,
    LINE_SHAPEFILE_MAPPING_CSV,
    CENTRALITY_MODES,
    CENTRALITY_EDGE_WEIGHT,
    RESULTS_DIR,
)
from src.data.loaders import (  # noqa: E402
    load_transit_nodes,
    load_lines_and_modes,
)
from src.network import (  # noqa: E402
    load_line_geometries,
    match_lines_to_shapefiles,
    build_station_graph,
    build_node_to_hub_mapping,
    contract_to_hub_graph,
    compute_centrality_metrics,
    normalize_centrality,
    compare_with_rankings,
    find_divergent_hubs,
    write_validation_report,
)
from src.network.validation import (  # noqa: E402
    plot_centrality_vs_score,
    create_centrality_map,
)
from src.utils.logging import setup_logger  # noqa: E402

logger = setup_logger(__name__)


def _sets_to_str(df: pd.DataFrame) -> pd.DataFrame:
    """Convert set-valued columns to sorted ';'-joined strings for CSV."""
    out = df.copy()
    for col in out.columns:
        if out[col].apply(lambda v: isinstance(v, (set, frozenset))).any():
            out[col] = out[col].apply(
                lambda v: ';'.join(sorted(map(str, v)))
                if isinstance(v, (set, frozenset)) else v)
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Network centrality validation analysis")
    parser.add_argument('--nodes-csv', type=Path, required=True,
                        help='All_nodes+lines CSV (node, LINE_ID, X/Y)')
    parser.add_argument('--lines-modes-csv', type=Path, required=True,
                        help='Lines_and_Planned_Mode CSV')
    parser.add_argument('--scored-hubs', type=Path, required=True,
                        help='scored_hubs_final.csv (or grouped hubs CSV '
                             'with group/node columns)')
    parser.add_argument('--lines-dir', type=Path, default=TRANSIT_LINES_DIR,
                        help='Directory of per-line shapefiles')
    parser.add_argument('--weight', choices=['time_min', 'length_m'],
                        default=CENTRALITY_EDGE_WEIGHT,
                        help='Edge cost for shortest paths')
    parser.add_argument('--modes', type=str, default=None,
                        help='Comma-separated mode list '
                             '(default: CENTRALITY_MODES)')
    parser.add_argument('--no-brt', action='store_true',
                        help='Sensitivity run excluding BRT')
    parser.add_argument('--allow-heuristic-ordering', action='store_true',
                        help='Nearest-neighbour stop ordering for lines '
                             'without a usable polyline (approximate)')
    parser.add_argument('--out-dir', type=Path, default=RESULTS_DIR)
    args = parser.parse_args()

    modes = (set(m.strip() for m in args.modes.split(','))
             if args.modes else set(CENTRALITY_MODES))
    if args.no_brt:
        modes.discard('BRT')
    logger.info(f"Modes: {sorted(modes)} | weight: {args.weight}")

    # ------------------------------------------------------------------ load
    nodes_gdf = load_transit_nodes(args.nodes_csv)
    lines_modes = load_lines_and_modes(args.lines_modes_csv)
    scored_hubs = pd.read_csv(args.scored_hubs, encoding='utf-8-sig')

    manual = None
    if LINE_SHAPEFILE_MAPPING_CSV.exists():
        manual = pd.read_csv(LINE_SHAPEFILE_MAPPING_CSV)
        logger.info(f"Using manual line-shapefile mapping "
                    f"({len(manual)} rows)")

    # ----------------------------------------------------------- build graph
    mode_by_line = lines_modes.set_index(
        lines_modes['Line_ModelName'].astype(str))['Mode_Planned'].to_dict()
    in_scope = {
        l for l in nodes_gdf['LINE_ID'].astype(str).unique()
        if mode_by_line.get(l) in modes
    }
    line_geoms = load_line_geometries(args.lines_dir)
    geom_by_line, match_report = match_lines_to_shapefiles(
        in_scope, line_geoms, manual_mapping=manual)

    G_stations, qa_df = build_station_graph(
        nodes_gdf, lines_modes, geom_by_line, modes=modes,
        allow_heuristic_ordering=args.allow_heuristic_ordering)
    qa_df = qa_df.merge(match_report, on='LINE_ID', how='left')

    node_to_hub = build_node_to_hub_mapping(scored_hubs)
    G_hubs = contract_to_hub_graph(G_stations, node_to_hub)

    # ------------------------------------------------------------ centrality
    centrality = compute_centrality_metrics(G_hubs, weight=args.weight)
    centrality = normalize_centrality(centrality)

    # ------------------------------------------------------------ validation
    results = compare_with_rankings(centrality, scored_hubs)
    divergent = find_divergent_hubs(results['eligible'], results['rank_col'])

    top_stations = (
        centrality[~centrality['is_hub']]
        .nlargest(20, 'betweenness')
        [['betweenness', 'closeness', 'degree', 'n_lines', 'n_modes']]
    )

    # --------------------------------------------------------------- outputs
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results['eligible'].pipe(_sets_to_str).to_csv(
        out_dir / 'network_centrality_by_hub.csv',
        index=False, encoding='utf-8-sig')
    centrality[~centrality['is_hub']].pipe(_sets_to_str).to_csv(
        out_dir / 'network_centrality_stations.csv', encoding='utf-8-sig')
    qa_df.to_csv(out_dir / 'graph_build_qa.csv',
                 index=False, encoding='utf-8-sig')

    write_validation_report(results, divergent, qa_df, out_dir=out_dir,
                            weight=args.weight, top_stations=top_stations)
    plot_centrality_vs_score(
        results, out_dir / 'centrality_vs_ranking_scatter.png')
    create_centrality_map(
        centrality, out_dir / 'network_centrality_map.html',
        line_geometries=geom_by_line, merged=results['merged'])

    # --------------------------------------------------------------- summary
    corr = results['correlations']['betweenness_vs_score']
    n_ok = int(qa_df['status'].str.startswith(('ok', 'heuristic')).sum())
    logger.info("=" * 70)
    logger.info(f"Lines built: {n_ok}/{len(qa_df)} | "
                f"hubs matched: {results['coverage']['n_matched']}")
    logger.info(f"Betweenness vs MC score: Spearman ρ = "
                f"{corr['spearman_rho']} (n={corr['n']})")
    logger.info(f"Outputs written to {out_dir}")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
