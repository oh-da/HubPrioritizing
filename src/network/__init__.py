"""
Network Centrality Analysis
============================
Builds a graph of the planned mass-transit network from per-line polyline
shapefiles + the nodes-on-lines CSV, contracts stations into hubs, computes
centrality metrics, and validates them against the Monte Carlo hub rankings.

This package is a standalone validation study — it does not feed into the
scoring pipeline.
"""

from .graph_builder import (
    load_line_geometries,
    match_lines_to_shapefiles,
    prepare_line_geometry,
    order_stops_along_line,
    build_station_graph,
    build_node_to_hub_mapping,
    contract_to_hub_graph,
)
from .centrality import (
    compute_centrality_metrics,
    normalize_centrality,
)
from .validation import (
    compare_with_rankings,
    find_divergent_hubs,
    write_validation_report,
)

__all__ = [
    'load_line_geometries',
    'match_lines_to_shapefiles',
    'prepare_line_geometry',
    'order_stops_along_line',
    'build_station_graph',
    'build_node_to_hub_mapping',
    'contract_to_hub_graph',
    'compute_centrality_metrics',
    'normalize_centrality',
    'compare_with_rankings',
    'find_divergent_hubs',
    'write_validation_report',
]
