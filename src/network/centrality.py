"""
Centrality Metrics
===================
Computes centrality metrics on the (hub-contracted) transit network graph.

Primary metric: weighted betweenness centrality — the share of shortest
paths passing through a node. This operationalizes the framework's
definition of a hub as the "operational heart" of the network (transfer /
interchange importance), which none of the five scoring criteria measure.

Secondary metrics: weighted closeness (accessibility) and degree/line/mode
counts (expected to track the existing Service & Modes score — a
construction cross-check, not new information).

Edge weights are costs (time_min or length_m): networkx shortest paths
minimize them directly, no inversion needed.
"""

from typing import List, Optional

import networkx as nx
import pandas as pd

from ..config import (
    CENTRALITY_EDGE_WEIGHT,
    MONTE_CARLO_RANDOM_SEED,
    SCORE_MIN,
    SCORE_MAX,
)
from ..scoring.normalization import normalize_minmax
from ..utils.logging import get_logger

logger = get_logger(__name__)


def compute_centrality_metrics(
    G: nx.Graph,
    weight: str = CENTRALITY_EDGE_WEIGHT,
) -> pd.DataFrame:
    """Compute centrality metrics for every node in the graph.

    Args:
        G: Undirected graph with cost edge attribute `weight`
            (e.g. time_min) and node attributes is_hub/x/y (optional)
        weight: Edge attribute to use as shortest-path cost

    Returns:
        DataFrame indexed by graph node id with columns:
        betweenness, closeness, degree, n_lines, n_modes,
        component_id, component_size, is_hub, x, y
    """
    if len(G) == 0:
        raise ValueError("Graph is empty — nothing to compute")

    logger.info(f"Computing centrality on {G.number_of_nodes()} nodes / "
                f"{G.number_of_edges()} edges (weight='{weight}')")

    # Exact Brandes betweenness; seed only affects tie-breaking sampling
    betweenness = nx.betweenness_centrality(
        G, weight=weight, normalized=True, seed=MONTE_CARLO_RANDOM_SEED)

    # Wasserman-Faust variant scales per component size — sane for
    # disconnected graphs (isolated cable/funicular systems are expected)
    closeness = nx.closeness_centrality(G, distance=weight, wf_improved=True)

    components = list(nx.connected_components(G))
    component_of = {}
    for comp_id, comp in enumerate(
            sorted(components, key=len, reverse=True)):
        for node in comp:
            component_of[node] = (comp_id, len(comp))

    rows = []
    for node, attrs in G.nodes(data=True):
        lines, modes = set(), set()
        for _, _, edata in G.edges(node, data=True):
            lines |= edata.get('lines', set())
            modes |= edata.get('modes', set())
        comp_id, comp_size = component_of[node]
        rows.append({
            'node_id': node,
            'betweenness': betweenness[node],
            'closeness': closeness[node],
            'degree': G.degree(node),
            'n_lines': len(lines),
            'n_modes': len(modes),
            'component_id': comp_id,
            'component_size': comp_size,
            'is_hub': bool(attrs.get('is_hub', False)),
            'x': attrs.get('x'),
            'y': attrs.get('y'),
        })

    df = pd.DataFrame(rows).set_index('node_id')
    logger.info(f"✓ Centrality computed; top betweenness: "
                f"{df['betweenness'].max():.4f}")
    return df


def normalize_centrality(
    df: pd.DataFrame,
    cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Add 1-10 normalized columns (<col>_Norm) for centrality metrics.

    Normalization is GLOBAL (all nodes together), not per tier: centrality
    is a network-wide structural property; per-tier views belong in the
    ranking comparison, not in the metric itself.

    Args:
        df: Output of compute_centrality_metrics
        cols: Columns to normalize (default: betweenness, closeness, degree)

    Returns:
        Copy of df with added <col>_Norm columns
    """
    if cols is None:
        cols = ['betweenness', 'closeness', 'degree']

    result = df.copy()
    for col in cols:
        result[f'{col}_Norm'] = normalize_minmax(
            result[col].astype(float), min_val=SCORE_MIN, max_val=SCORE_MAX)
    return result
