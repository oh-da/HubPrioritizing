"""
Test suite for the network centrality analysis package.

Run with: pytest tests/test_network.py -v

Uses a small synthetic network built in-memory (no shapefiles):
an east-west Metro line and a north-south LRT line crossing at node 3,
plus mode-filter / missing-geometry cases.
"""

import sys
from pathlib import Path

import pytest

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import geopandas as gpd  # noqa: E402
import networkx as nx  # noqa: E402
import pandas as pd  # noqa: E402
from shapely.geometry import LineString, MultiLineString, Point  # noqa: E402

from src.config import CRS_ISRAEL_TM, MIN_EDGE_LENGTH_M  # noqa: E402
from src.network.graph_builder import (  # noqa: E402
    build_node_to_hub_mapping,
    build_station_graph,
    contract_to_hub_graph,
    order_stops_along_line,
    prepare_line_geometry,
)
from src.network.centrality import (  # noqa: E402
    compute_centrality_metrics,
    normalize_centrality,
)
from src.network.validation import (  # noqa: E402
    compare_with_rankings,
    find_divergent_hubs,
)


# ============================================================================
# FIXTURES
# ============================================================================

def _make_nodes_gdf(rows):
    """rows: list of (node, line_id, x, y)"""
    df = pd.DataFrame(rows, columns=['node', 'LINE_ID', 'x', 'y'])
    geometry = [Point(x, y) for x, y in zip(df['x'], df['y'])]
    return gpd.GeoDataFrame(
        df[['node', 'LINE_ID']], geometry=geometry, crs=CRS_ISRAEL_TM)


@pytest.fixture
def cross_network():
    """EW Metro line and NS LRT line crossing at node 3, plus a Bus line
    (out of scope) and a BRT line without geometry."""
    ew_stops = [(1, 0, 0), (2, 1000, 0), (3, 2000, 0),
                (4, 3000, 0), (5, 4000, 0)]
    ns_stops = [(6, 2000, -2000), (7, 2000, -1000), (3, 2000, 0),
                (8, 2000, 1000), (9, 2000, 2000)]

    rows = []
    for node, x, y in ew_stops:
        rows.append((node, 'ew_1', x, y))
        rows.append((node, 'ew_2', x, y))  # direction pair, same node IDs
    for node, x, y in ns_stops:
        rows.append((node, 'ns_1', x, y))
    rows.append((1, 'bus_9', 0, 0))       # Bus mode: filtered out
    rows.append((2, 'bus_9', 1000, 0))
    rows.append((10, 'brt_1', 5000, 5000))  # BRT without geometry: skipped
    rows.append((11, 'brt_1', 6000, 5000))

    nodes_gdf = _make_nodes_gdf(rows)
    lines_modes = pd.DataFrame({
        'Line_ModelName': ['ew_1', 'ew_2', 'ns_1', 'bus_9', 'brt_1'],
        'Mode_Planned': ['Metro', 'Metro', 'LRT', 'Bus', 'BRT'],
    })
    line_geometries = {
        'ew_1': LineString([(0, 0), (4000, 0)]),
        'ew_2': LineString([(4000, 0), (0, 0)]),
        'ns_1': LineString([(2000, -2000), (2000, 2000)]),
        # brt_1 deliberately missing
    }
    return nodes_gdf, lines_modes, line_geometries


# ============================================================================
# STOP ORDERING
# ============================================================================

class TestStopOrdering:

    def test_shuffled_stops_ordered_by_chainage(self):
        line = LineString([(0, 0), (5000, 0)])
        stops = _make_nodes_gdf([
            (3, 'l', 2000, 10),
            (1, 'l', 0, -10),
            (5, 'l', 4000, 0),
            (2, 'l', 1000, 5),
            (4, 'l', 3000, 0),
        ])
        ordered = order_stops_along_line(line, stops)
        assert ordered['node'].tolist() == [1, 2, 3, 4, 5]
        assert ordered['dist_along_m'].is_monotonic_increasing

    def test_far_stop_dropped_and_flagged(self):
        line = LineString([(0, 0), (5000, 0)])
        stops = _make_nodes_gdf([
            (1, 'l', 0, 0),
            (2, 'l', 2000, 1500),  # 1.5 km off the line -> dropped
            (3, 'l', 4000, 0),
        ])
        ordered = order_stops_along_line(line, stops)
        row = ordered[ordered['node'] == 2].iloc[0]
        assert row['dropped']
        assert row['warn_far']

    def test_moderately_far_stop_warned_not_dropped(self):
        line = LineString([(0, 0), (5000, 0)])
        stops = _make_nodes_gdf([
            (1, 'l', 0, 0),
            (2, 'l', 2000, 250),  # 250 m off -> warn only
        ])
        ordered = order_stops_along_line(line, stops)
        row = ordered[ordered['node'] == 2].iloc[0]
        assert row['warn_far']
        assert not row['dropped']

    def test_multilinestring_merged(self):
        geom = MultiLineString([
            [(0, 0), (1000, 0)],
            [(1000, 0), (2000, 0)],
        ])
        line, status = prepare_line_geometry(geom)
        assert isinstance(line, LineString)
        assert status == 'merged'
        assert line.length == pytest.approx(2000)

    def test_multilinestring_gap_bridged(self):
        # 30 m gap between parts, below the 50 m tolerance
        geom = MultiLineString([
            [(0, 0), (1000, 0)],
            [(1030, 0), (2000, 0)],
        ])
        line, status = prepare_line_geometry(geom)
        assert isinstance(line, LineString)
        assert status == 'gap_bridged'
        assert line.length == pytest.approx(2000)

    def test_multilinestring_large_gap_fails(self):
        geom = MultiLineString([
            [(0, 0), (1000, 0)],
            [(2000, 0), (3000, 0)],  # 1 km gap
        ])
        line, status = prepare_line_geometry(geom)
        assert line is None
        assert status == 'multiline_unmerged'


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

class TestGraphBuild:

    def test_cross_network_structure(self, cross_network):
        G, qa = build_station_graph(*cross_network)
        # 9 stations (BRT skipped, Bus filtered), 8 edges (4 EW + 4 NS)
        assert G.number_of_nodes() == 9
        assert G.number_of_edges() == 8
        assert nx.number_connected_components(G) == 1

    def test_direction_pair_no_duplicate_edges(self, cross_network):
        G, _ = build_station_graph(*cross_network)
        # ew_1 and ew_2 cover the same stops: edges carry both lines
        edge = G.edges[1, 2]
        assert edge['lines'] == {'ew_1', 'ew_2'}
        assert edge['modes'] == {'Metro'}
        assert edge['length_m'] == pytest.approx(1000)

    def test_mode_filter_drops_bus(self, cross_network):
        G, qa = build_station_graph(*cross_network)
        assert 'bus_9' not in set(qa['LINE_ID'])
        for _, _, data in G.edges(data=True):
            assert 'bus_9' not in data['lines']

    def test_missing_geometry_skipped_with_qa_row(self, cross_network):
        G, qa = build_station_graph(*cross_network)
        brt_row = qa[qa['LINE_ID'] == 'brt_1'].iloc[0]
        assert brt_row['status'] == 'skipped_no_geometry'
        assert 10 not in G

    def test_heuristic_ordering_fallback(self, cross_network):
        nodes_gdf, lines_modes, line_geometries = cross_network
        G, qa = build_station_graph(
            nodes_gdf, lines_modes, line_geometries,
            allow_heuristic_ordering=True)
        brt_row = qa[qa['LINE_ID'] == 'brt_1'].iloc[0]
        assert brt_row['status'] == 'heuristic_ordering'
        assert G.has_edge(10, 11)

    def test_edge_weights_time_reflects_mode_speed(self, cross_network):
        G, _ = build_station_graph(*cross_network)
        # Metro 35 km/h: 1000 m -> 1000 / (35000/60) minutes
        assert G.edges[1, 2]['time_min'] == pytest.approx(
            1000 / (35 * 1000 / 60))
        # LRT 25 km/h is slower per meter
        assert G.edges[6, 7]['time_min'] > G.edges[1, 2]['time_min']

    def test_zero_length_edge_floored(self):
        # Two distinct nodes projecting onto the same chainage
        nodes_gdf = _make_nodes_gdf([
            (1, 'l_1', 0, 0),
            (2, 'l_1', 1000, 50),
            (3, 'l_1', 1000, -50),
            (4, 'l_1', 2000, 0),
        ])
        lines_modes = pd.DataFrame({
            'Line_ModelName': ['l_1'], 'Mode_Planned': ['Metro']})
        geoms = {'l_1': LineString([(0, 0), (2000, 0)])}
        G, _ = build_station_graph(nodes_gdf, lines_modes, geoms)
        assert G.edges[2, 3]['length_m'] == MIN_EDGE_LENGTH_M

    def test_consecutive_duplicate_node_deduped(self):
        nodes_gdf = _make_nodes_gdf([
            (1, 'l_1', 0, 0),
            (1, 'l_1', 10, 0),  # same node again (double entry)
            (2, 'l_1', 1000, 0),
        ])
        lines_modes = pd.DataFrame({
            'Line_ModelName': ['l_1'], 'Mode_Planned': ['Metro']})
        geoms = {'l_1': LineString([(0, 0), (1000, 0)])}
        G, _ = build_station_graph(nodes_gdf, lines_modes, geoms)
        assert G.number_of_edges() == 1
        assert not G.has_edge(1, 1)


# ============================================================================
# HUB CONTRACTION
# ============================================================================

class TestContraction:

    def _simple_graph(self):
        G = nx.Graph()
        for n, x in [(1, 0), (2, 1000), (3, 2000), (4, 3000)]:
            G.add_node(n, x=float(x), y=0.0)
        for u, v in [(1, 2), (2, 3), (3, 4)]:
            G.add_edge(u, v, length_m=1000.0, time_min=2.0,
                       lines={'l_1'}, modes={'Metro'})
        return G

    def test_hub_contraction_merges_and_drops_self_loop(self):
        G = self._simple_graph()
        H = contract_to_hub_graph(G, {2: 'hub_A', 3: 'hub_A'})
        assert H.number_of_nodes() == 3  # stn_1, hub_A, stn_4
        assert H.has_node('hub_A')
        assert not H.has_edge('hub_A', 'hub_A')
        assert sorted(H.nodes['hub_A']['members']) == [2, 3]
        assert H.nodes['hub_A']['x'] == pytest.approx(1500.0)

    def test_parallel_edges_collapse_to_min_weight(self):
        G = nx.Graph()
        for n in (1, 2, 3):
            G.add_node(n, x=0.0, y=0.0)
        G.add_edge(1, 2, length_m=500.0, time_min=1.0,
                   lines={'a_1'}, modes={'Metro'})
        G.add_edge(1, 3, length_m=2000.0, time_min=4.0,
                   lines={'b_1'}, modes={'LRT'})
        H = contract_to_hub_graph(G, {2: 'hub_X', 3: 'hub_X'})
        edge = H.edges['stn_1', 'hub_X']
        assert edge['length_m'] == 500.0
        assert edge['lines'] == {'a_1', 'b_1'}
        assert edge['modes'] == {'Metro', 'LRT'}

    def test_node_in_two_hubs_raises(self):
        scored = pd.DataFrame({
            'group': [0, 1],
            'node': ["[1, 2]", "[2, 3]"],  # node 2 in both
        })
        with pytest.raises(ValueError, match="appears in both"):
            build_node_to_hub_mapping(scored)

    def test_node_list_parsing_variants(self):
        scored = pd.DataFrame({
            'group': [0, 1, 2],
            'node': ["[31655]", "['a', 'b']", [7]],  # str-int, str-str, list
        })
        mapping = build_node_to_hub_mapping(scored)
        assert mapping[31655] == 'hub_0'
        assert mapping['a'] == 'hub_1'
        assert mapping['b'] == 'hub_1'
        assert mapping[7] == 'hub_2'


# ============================================================================
# CENTRALITY
# ============================================================================

def _graph_from_edges(edges):
    G = nx.Graph()
    for u, v, t in edges:
        G.add_edge(u, v, time_min=float(t), length_m=float(t),
                   lines={'l'}, modes={'Metro'})
    return G


class TestCentrality:

    def test_star_center_has_max_betweenness(self):
        G = _graph_from_edges([('c', f'l{i}', 1) for i in range(4)])
        df = compute_centrality_metrics(G, weight='time_min')
        assert df.loc['c', 'betweenness'] == pytest.approx(1.0)
        for i in range(4):
            assert df.loc[f'l{i}', 'betweenness'] == pytest.approx(0.0)

    def test_path_endpoints_zero_betweenness(self):
        G = _graph_from_edges([('a', 'b', 1), ('b', 'c', 1)])
        df = compute_centrality_metrics(G, weight='time_min')
        assert df.loc['a', 'betweenness'] == pytest.approx(0.0)
        assert df.loc['c', 'betweenness'] == pytest.approx(0.0)
        assert df.loc['b', 'betweenness'] > 0

    def test_weighted_shortest_path_wins(self):
        # a-b-c is metrically short (2), a-d-c is long (10):
        # traffic between a and c routes via b
        G = _graph_from_edges([
            ('a', 'b', 1), ('b', 'c', 1),
            ('a', 'd', 5), ('d', 'c', 5),
        ])
        df = compute_centrality_metrics(G, weight='time_min')
        assert df.loc['b', 'betweenness'] > df.loc['d', 'betweenness']
        assert df.loc['d', 'betweenness'] == pytest.approx(0.0)

    def test_disconnected_graph_handled(self):
        G = _graph_from_edges([('a', 'b', 1), ('c', 'd', 1)])
        df = compute_centrality_metrics(G, weight='time_min')
        assert set(df['component_id']) == {0, 1}
        assert (df['component_size'] == 2).all()
        assert df['closeness'].notna().all()

    def test_normalization_range(self):
        G = _graph_from_edges([('a', 'b', 1), ('b', 'c', 1), ('c', 'd', 1)])
        df = normalize_centrality(compute_centrality_metrics(G))
        for col in ('betweenness_Norm', 'closeness_Norm', 'degree_Norm'):
            assert df[col].between(1, 10).all()


# ============================================================================
# VALIDATION
# ============================================================================

def _make_validation_inputs(reverse=False):
    """12 hubs; centrality and MC score aligned (or reversed)."""
    n = 12
    groups = list(range(n))
    betweenness = [round(1.0 - i * 0.05, 3) for i in range(n)]
    scores = list(betweenness) if not reverse else list(betweenness[::-1])

    centrality = pd.DataFrame({
        'node_id': [f'hub_{g}' for g in groups],
        'betweenness': betweenness,
        'closeness': betweenness,
        'degree': [n - i for i in range(n)],
        'n_lines': 2, 'n_modes': 2,
        'component_id': 0, 'component_size': n,
        'is_hub': True, 'x': 180000.0, 'y': 660000.0,
    }).set_index('node_id')

    scored = pd.DataFrame({
        'group': groups,
        'node': [f"[{100 + g}]" for g in groups],
        'HubType': ['מטרופוליני'] * n,
        'Average_Simulated_Score': scores,
        'Overall_Rank': pd.Series(scores).rank(ascending=False).astype(int),
    })
    return centrality, scored


class TestValidation:

    def test_identical_rankings_perfect_correlation(self):
        centrality, scored = _make_validation_inputs()
        results = compare_with_rankings(centrality, scored)
        corr = results['correlations']['betweenness_vs_score']
        assert corr['spearman_rho'] == pytest.approx(1.0)
        assert results['top_n_overlap'][10]['recall'] == pytest.approx(1.0)

    def test_reversed_rankings_negative_correlation(self):
        centrality, scored = _make_validation_inputs(reverse=True)
        results = compare_with_rankings(centrality, scored)
        corr = results['correlations']['betweenness_vs_score']
        assert corr['spearman_rho'] == pytest.approx(-1.0)

    def test_coverage_reports_unmatched(self):
        centrality, scored = _make_validation_inputs()
        scored_extra = pd.concat([scored, pd.DataFrame({
            'group': [99], 'node': ["[999]"], 'HubType': ['עירוני'],
            'Average_Simulated_Score': [0.1], 'Overall_Rank': [13],
        })], ignore_index=True)
        results = compare_with_rankings(centrality, scored_extra)
        assert results['coverage']['scored_without_centrality'] == ['99']

    def test_not_hub_excluded_from_stats(self):
        centrality, scored = _make_validation_inputs()
        scored.loc[0, 'HubType'] = 'Not Hub'
        results = compare_with_rankings(centrality, scored)
        assert len(results['eligible']) == 11
        assert results['correlations']['betweenness_vs_score']['n'] == 11

    def test_divergent_hubs_direction(self):
        centrality, scored = _make_validation_inputs()
        # Make hub 11 (lowest MC rank) most central in the network
        centrality.loc['hub_11', 'betweenness'] = 2.0
        results = compare_with_rankings(centrality, scored)
        divergent = find_divergent_hubs(
            results['eligible'], results['rank_col'], top_n=3)
        top = divergent.iloc[0]
        assert top['group'] == '11'
        assert top['rank_diff'] > 0  # network says it matters more than MC
        # No duplicated hubs when top_n exceeds half the hub count
        assert not divergent['group'].duplicated().any()


# ============================================================================
# END-TO-END (synthetic)
# ============================================================================

class TestEndToEnd:

    def test_full_flow_on_cross_network(self, cross_network):
        nodes_gdf, lines_modes, line_geometries = cross_network
        G, qa = build_station_graph(nodes_gdf, lines_modes, line_geometries)

        scored = pd.DataFrame({
            'group': [0, 1],
            'node': ["[3]", "[1]"],  # crossing node vs EW terminus
            'HubType': ['מטרופוליני', 'עירוני'],
            'Average_Simulated_Score': [8.0, 3.0],
            'Overall_Rank': [1, 2],
        })
        mapping = build_node_to_hub_mapping(scored)
        H = contract_to_hub_graph(G, mapping)
        df = normalize_centrality(compute_centrality_metrics(H))

        # The crossing hub must dominate betweenness
        assert df['betweenness'].idxmax() == 'hub_0'

        results = compare_with_rankings(df, scored)
        assert results['coverage']['n_matched'] == 2
        corr = results['correlations']['betweenness_vs_score']
        assert corr['n'] == 2  # too few for correlation, reported as such
        assert corr['spearman_rho'] is None
