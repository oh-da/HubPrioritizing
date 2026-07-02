"""
Transit Network Graph Construction
===================================
Builds an L-space graph of the planned mass-transit network:

1. Match per-line polyline shapefiles to LINE_IDs from the nodes CSV.
2. Order each line's stops by projecting them onto the line's polyline
   (the nodes CSV has no stop-sequence column — the polylines supply it).
3. Create edges between consecutive stops, weighted by along-line distance
   and generalized travel time (distance / mode speed).
4. Contract stations belonging to the same hub group into super-nodes
   (models free intra-hub transfers).

All distance operations are performed in EPSG:2039 (meters).
"""

import ast
from pathlib import Path
from typing import Dict, Optional, Set, Tuple, Union

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString, MultiLineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, unary_union

from ..config import (
    CRS_ISRAEL_TM,
    CENTRALITY_MODES,
    MODE_SPEEDS_KMH,
    DEFAULT_MODE_SPEED_KMH,
    PROJECTION_WARN_DIST_M,
    PROJECTION_MAX_DIST_M,
    MULTILINE_GAP_TOLERANCE_M,
    MIN_EDGE_LENGTH_M,
    LOOP_ENDPOINT_DIST_M,
    CHAINAGE_GAP_RATIO,
    CENTRALITY_ALLOW_HEURISTIC_ORDERING,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


def load_line_geometries(
    lines_dir: Union[str, Path],
    target_crs: str = CRS_ISRAEL_TM,
) -> gpd.GeoDataFrame:
    """Load all line shapefiles from a directory into a single GeoDataFrame.

    Each row is one feature from one shapefile, with `source_file` (stem) and
    `feature_index` columns preserved so features can be matched back to
    LINE_IDs by filename or attribute.

    Args:
        lines_dir: Directory containing per-line .shp files (searched
            recursively)
        target_crs: CRS to reproject all geometries to (default EPSG:2039)

    Returns:
        GeoDataFrame with columns [source_file, feature_index, <original
        attributes>, geometry] in target_crs

    Raises:
        FileNotFoundError: If lines_dir does not exist or contains no .shp
    """
    lines_dir = Path(lines_dir)
    if not lines_dir.exists():
        raise FileNotFoundError(f"Transit lines directory not found: {lines_dir}")

    shp_files = sorted(lines_dir.rglob("*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"No shapefiles found under {lines_dir}")

    logger.info(f"Loading {len(shp_files)} line shapefiles from {lines_dir}")

    frames = []
    for shp in shp_files:
        try:
            # Lazy import: encoding_fix pulls in optional deps
            from ..utils.encoding_fix import read_shapefile_with_encoding

            gdf, encoding = read_shapefile_with_encoding(
                str(shp), name=shp.stem, verbose=False
            )
        except Exception:
            # Fall back to plain read (line shapefiles often have no Hebrew)
            gdf = gpd.read_file(shp)

        if gdf.crs is None:
            logger.warning(
                f"{shp.name}: no CRS defined, assuming {target_crs}"
            )
            gdf = gdf.set_crs(target_crs)
        elif str(gdf.crs) != str(target_crs):
            gdf = gdf.to_crs(target_crs)

        gdf = gdf.reset_index(drop=True)
        gdf['source_file'] = shp.stem
        gdf['feature_index'] = gdf.index
        frames.append(gdf)

    combined = pd.concat(frames, ignore_index=True)
    combined = gpd.GeoDataFrame(combined, geometry='geometry', crs=target_crs)

    n_non_line = (~combined.geometry.geom_type.isin(
        ['LineString', 'MultiLineString'])).sum()
    if n_non_line:
        logger.warning(f"Dropping {n_non_line} non-line features")
        combined = combined[
            combined.geometry.geom_type.isin(['LineString', 'MultiLineString'])
        ].reset_index(drop=True)

    logger.info(f"✓ Loaded {len(combined)} line features "
                f"from {len(shp_files)} shapefiles")
    return combined


def match_lines_to_shapefiles(
    line_ids: Set[str],
    line_geoms: gpd.GeoDataFrame,
    manual_mapping: Optional[pd.DataFrame] = None,
) -> Tuple[Dict[str, BaseGeometry], pd.DataFrame]:
    """Match LINE_IDs to line geometries.

    Strategies, in priority order per line:
    1. `manual` — mapping CSV rows (LINE_ID, shapefile, [feature_index])
    2. `attribute` — the shapefile attribute column whose values best
       overlap the LINE_ID set (chosen once, globally)
    3. `filename` — shapefile stem equals the LINE_ID (case-insensitive)

    When several features match one line they are combined with unary_union
    (split alignments are re-merged later by prepare_line_geometry).

    Args:
        line_ids: LINE_ID values that need a geometry
        line_geoms: Output of load_line_geometries
        manual_mapping: Optional manual override DataFrame

    Returns:
        Tuple of ({LINE_ID: geometry}, match report DataFrame with columns
        [LINE_ID, matched_by, source_file])
    """
    line_ids = {str(l) for l in line_ids}
    geom_by_line: Dict[str, BaseGeometry] = {}
    report_rows = []

    # -- Strategy 1: manual mapping -----------------------------------------
    manual_matched: Set[str] = set()
    if manual_mapping is not None and len(manual_mapping):
        for _, row in manual_mapping.iterrows():
            line_id = str(row['LINE_ID'])
            if line_id not in line_ids:
                continue
            stem = str(row['shapefile']).replace('.shp', '')
            subset = line_geoms[line_geoms['source_file'] == stem]
            if 'feature_index' in row and pd.notna(row.get('feature_index')):
                subset = subset[
                    subset['feature_index'] == int(row['feature_index'])
                ]
            if len(subset):
                geom_by_line[line_id] = unary_union(list(subset.geometry))
                manual_matched.add(line_id)
                report_rows.append(
                    {'LINE_ID': line_id, 'matched_by': 'manual',
                     'source_file': stem})
            else:
                logger.warning(
                    f"Manual mapping for {line_id} points to missing "
                    f"shapefile/feature: {stem}")

    remaining = line_ids - manual_matched

    # -- Strategy 2: best attribute column ----------------------------------
    candidate_cols = [
        c for c in line_geoms.columns
        if c not in ('geometry', 'source_file', 'feature_index')
    ]
    best_col, best_hits = None, 0
    for col in candidate_cols:
        values = set(line_geoms[col].dropna().astype(str))
        hits = len(remaining & values)
        if hits > best_hits:
            best_col, best_hits = col, hits

    attr_matched: Set[str] = set()
    if best_col is not None:
        logger.info(
            f"Best matching attribute column: '{best_col}' "
            f"({best_hits}/{len(remaining)} lines)")
        col_values = line_geoms[best_col].astype(str)
        for line_id in sorted(remaining):
            subset = line_geoms[col_values == line_id]
            if len(subset):
                geom_by_line[line_id] = unary_union(list(subset.geometry))
                attr_matched.add(line_id)
                report_rows.append(
                    {'LINE_ID': line_id, 'matched_by': 'attribute',
                     'source_file': ';'.join(sorted(
                         subset['source_file'].unique()))})

    remaining = remaining - attr_matched

    # -- Strategy 3: filename stem -------------------------------------------
    stems = line_geoms['source_file'].astype(str)
    stems_lower = stems.str.lower()
    for line_id in sorted(remaining):
        subset = line_geoms[stems_lower == line_id.lower()]
        if len(subset):
            geom_by_line[line_id] = unary_union(list(subset.geometry))
            report_rows.append(
                {'LINE_ID': line_id, 'matched_by': 'filename',
                 'source_file': subset['source_file'].iloc[0]})
        else:
            report_rows.append(
                {'LINE_ID': line_id, 'matched_by': 'UNMATCHED',
                 'source_file': None})

    report = pd.DataFrame(report_rows)
    n_matched = len(geom_by_line)
    logger.info(f"✓ Matched {n_matched}/{len(line_ids)} lines to geometries")
    if n_matched < len(line_ids):
        unmatched = sorted(line_ids - set(geom_by_line))
        logger.warning(f"Unmatched lines ({len(unmatched)}): "
                       f"{unmatched[:20]}{'...' if len(unmatched) > 20 else ''}")
    return geom_by_line, report


def prepare_line_geometry(
    geom: BaseGeometry,
    gap_tolerance_m: float = MULTILINE_GAP_TOLERANCE_M,
) -> Tuple[Optional[LineString], str]:
    """Coerce a line geometry into a single LineString.

    MultiLineStrings are merged with shapely linemerge; if parts remain,
    endpoint gaps up to gap_tolerance_m are bridged greedily and the merge
    retried.

    Args:
        geom: LineString or MultiLineString
        gap_tolerance_m: Maximum endpoint gap to bridge between parts

    Returns:
        Tuple of (LineString or None, status) where status is one of
        'ok', 'merged', 'gap_bridged', 'multiline_unmerged', 'invalid'
    """
    if geom is None or geom.is_empty:
        return None, 'invalid'
    if isinstance(geom, LineString):
        return geom, 'ok'
    if not isinstance(geom, MultiLineString):
        return None, 'invalid'

    merged = linemerge(geom)
    if isinstance(merged, LineString):
        return merged, 'merged'

    # Bridge small endpoint gaps between parts, then re-merge
    parts = [LineString(p) for p in merged.geoms]
    bridged = False
    while len(parts) > 1:
        best = None  # (dist, i, j, reverse_i, reverse_j)
        for i in range(len(parts)):
            for j in range(i + 1, len(parts)):
                ends_i = [Point(parts[i].coords[0]), Point(parts[i].coords[-1])]
                ends_j = [Point(parts[j].coords[0]), Point(parts[j].coords[-1])]
                for ei, pt_i in enumerate(ends_i):
                    for ej, pt_j in enumerate(ends_j):
                        d = pt_i.distance(pt_j)
                        if best is None or d < best[0]:
                            # Orient part i to END at the junction and part j
                            # to START at it
                            best = (d, i, j, ei == 0, ej == 1)
        if best is None or best[0] > gap_tolerance_m:
            return None, 'multiline_unmerged'

        _, i, j, rev_i, rev_j = best
        coords_i = list(parts[i].coords)[::-1] if rev_i else list(parts[i].coords)
        coords_j = list(parts[j].coords)[::-1] if rev_j else list(parts[j].coords)
        joined = LineString(coords_i + coords_j)
        parts = [p for k, p in enumerate(parts) if k not in (i, j)] + [joined]
        bridged = True

    return parts[0], 'gap_bridged' if bridged else 'merged'


def order_stops_along_line(
    line: LineString,
    stops: gpd.GeoDataFrame,
    warn_dist_m: float = PROJECTION_WARN_DIST_M,
    max_dist_m: float = PROJECTION_MAX_DIST_M,
) -> pd.DataFrame:
    """Order a line's stops by projecting them onto the line's polyline.

    Args:
        line: The line alignment (EPSG:2039)
        stops: GeoDataFrame with columns [node, geometry] (EPSG:2039), one
            row per stop
        warn_dist_m: Projection offset above which the stop is flagged
        max_dist_m: Projection offset above which the stop is dropped

    Returns:
        DataFrame [node, dist_along_m, proj_offset_m, warn_far, dropped]
        sorted by dist_along_m; dropped stops are included (flagged) but
        should be excluded from edge building
    """
    rows = []
    for _, stop in stops.iterrows():
        pt = stop.geometry
        offset = line.distance(pt)
        rows.append({
            'node': stop['node'],
            'dist_along_m': line.project(pt),
            'proj_offset_m': offset,
            'warn_far': offset > warn_dist_m,
            'dropped': offset > max_dist_m,
        })

    ordered = pd.DataFrame(rows).sort_values('dist_along_m').reset_index(drop=True)
    return ordered


def _order_stops_heuristic(stops: gpd.GeoDataFrame) -> pd.DataFrame:
    """Greedy nearest-neighbour stop ordering for lines without a polyline.

    Approximate: starts from the stop farthest from the centroid (a likely
    terminus) and repeatedly walks to the nearest unvisited stop. Only used
    when CENTRALITY_ALLOW_HEURISTIC_ORDERING is enabled.
    """
    pts = {row['node']: row.geometry for _, row in stops.iterrows()}
    if not pts:
        return pd.DataFrame(
            columns=['node', 'dist_along_m', 'proj_offset_m',
                     'warn_far', 'dropped'])

    centroid = unary_union(list(pts.values())).centroid
    current = max(pts, key=lambda n: pts[n].distance(centroid))

    order, visited, chainage = [], set(), 0.0
    prev_pt = None
    while len(visited) < len(pts):
        if prev_pt is not None:
            chainage += prev_pt.distance(pts[current])
        order.append({'node': current, 'dist_along_m': chainage,
                      'proj_offset_m': 0.0, 'warn_far': False,
                      'dropped': False})
        visited.add(current)
        prev_pt = pts[current]
        unvisited = [n for n in pts if n not in visited]
        if not unvisited:
            break
        current = min(unvisited, key=lambda n: prev_pt.distance(pts[n]))

    return pd.DataFrame(order)


def _line_qa_flags(line: LineString, ordered: pd.DataFrame) -> Dict[str, bool]:
    """QA flags for circular lines and suspicious chainage gaps."""
    endpoints_close = (
        Point(line.coords[0]).distance(Point(line.coords[-1]))
        < LOOP_ENDPOINT_DIST_M
    )
    gap_flag = False
    kept = ordered[~ordered['dropped']]
    if len(kept) > 2:
        gaps = kept['dist_along_m'].diff().dropna()
        median_gap = gaps.median()
        if median_gap > 0:
            gap_flag = bool((gaps > CHAINAGE_GAP_RATIO * median_gap).any())
    return {'loop_flag': bool(endpoints_close), 'chainage_gap_flag': gap_flag}


def build_station_graph(
    nodes_gdf: gpd.GeoDataFrame,
    lines_modes: pd.DataFrame,
    line_geometries: Dict[str, BaseGeometry],
    modes: Set[str] = None,
    allow_heuristic_ordering: bool = CENTRALITY_ALLOW_HEURISTIC_ORDERING,
) -> Tuple[nx.Graph, pd.DataFrame]:
    """Build the undirected station-level L-space graph.

    Edges connect consecutive stops of each line; direction pairs (e.g.
    rail_1_1/rail_1_2) and overlapping lines collapse onto the same edges,
    keeping the minimum weight and the union of line/mode attributes.

    Args:
        nodes_gdf: Transit nodes (from load_transit_nodes), one row per
            stop-on-line with columns [node, LINE_ID, geometry] in EPSG:2039
        lines_modes: Line-to-mode mapping (from load_lines_and_modes) with
            columns [Line_ModelName, Mode_Planned]
        line_geometries: {LINE_ID: geometry} from match_lines_to_shapefiles
        modes: Modes to include (default CENTRALITY_MODES)
        allow_heuristic_ordering: Fall back to nearest-neighbour ordering
            for lines without a usable polyline (approximate)

    Returns:
        Tuple of (graph, per-line QA DataFrame)
    """
    if modes is None:
        modes = CENTRALITY_MODES

    mode_by_line = (
        lines_modes.dropna(subset=['Line_ModelName'])
        .astype({'Line_ModelName': str})
        .set_index('Line_ModelName')['Mode_Planned']
        .to_dict()
    )

    nodes_gdf = nodes_gdf.copy()
    nodes_gdf['LINE_ID'] = nodes_gdf['LINE_ID'].astype(str)

    all_line_ids = sorted(nodes_gdf['LINE_ID'].unique())
    no_mode = [l for l in all_line_ids if l not in mode_by_line]
    if no_mode:
        logger.warning(
            f"{len(no_mode)} lines missing from the modes CSV (excluded): "
            f"{no_mode[:10]}{'...' if len(no_mode) > 10 else ''}")

    in_scope = [
        l for l in all_line_ids
        if mode_by_line.get(l) in modes
    ]
    logger.info(f"Building station graph for {len(in_scope)} in-scope lines "
                f"(of {len(all_line_ids)} total)")

    G = nx.Graph()
    qa_rows = []

    for line_id in in_scope:
        mode = mode_by_line[line_id]
        speed_kmh = MODE_SPEEDS_KMH.get(mode, DEFAULT_MODE_SPEED_KMH)

        stops = (
            nodes_gdf[nodes_gdf['LINE_ID'] == line_id]
            .drop_duplicates(subset='node')
            [['node', 'geometry']]
        )

        qa = {'LINE_ID': line_id, 'mode': mode, 'n_stops': len(stops),
              'n_dropped': 0, 'max_proj_offset_m': None, 'n_warn_far': 0,
              'loop_flag': False, 'chainage_gap_flag': False}

        if len(stops) < 2:
            qa['status'] = 'skipped_too_few_stops'
            qa_rows.append(qa)
            continue

        raw_geom = line_geometries.get(line_id)
        line, geom_status = (
            prepare_line_geometry(raw_geom) if raw_geom is not None
            else (None, 'no_geometry')
        )

        if line is not None:
            ordered = order_stops_along_line(line, stops)
            qa.update(_line_qa_flags(line, ordered))
            qa['status'] = f'ok_{geom_status}' if geom_status != 'ok' else 'ok'
        elif allow_heuristic_ordering:
            ordered = _order_stops_heuristic(stops)
            qa['status'] = 'heuristic_ordering'
            logger.warning(f"{line_id}: no usable polyline, "
                           f"using heuristic stop ordering")
        else:
            qa['status'] = (
                'skipped_multiline' if geom_status == 'multiline_unmerged'
                else 'skipped_no_geometry'
            )
            qa_rows.append(qa)
            continue

        qa['n_dropped'] = int(ordered['dropped'].sum())
        qa['n_warn_far'] = int(ordered['warn_far'].sum())
        qa['max_proj_offset_m'] = round(float(
            ordered['proj_offset_m'].max()), 1)

        kept = ordered[~ordered['dropped']].reset_index(drop=True)

        # Register stop nodes with coordinates
        stop_geoms = stops.set_index('node').geometry
        for node_id in kept['node']:
            if not G.has_node(node_id):
                pt = stop_geoms.loc[node_id]
                G.add_node(node_id, x=pt.x, y=pt.y)

        # Edges between consecutive stops (skip consecutive duplicates)
        for i in range(len(kept) - 1):
            u, v = kept.loc[i, 'node'], kept.loc[i + 1, 'node']
            if u == v:
                continue
            length_m = max(
                kept.loc[i + 1, 'dist_along_m'] - kept.loc[i, 'dist_along_m'],
                MIN_EDGE_LENGTH_M,
            )
            time_min = length_m / (speed_kmh * 1000.0 / 60.0)

            if G.has_edge(u, v):
                edge = G.edges[u, v]
                edge['length_m'] = min(edge['length_m'], length_m)
                edge['time_min'] = min(edge['time_min'], time_min)
                edge['lines'].add(line_id)
                edge['modes'].add(mode)
            else:
                G.add_edge(u, v, length_m=length_m, time_min=time_min,
                           lines={line_id}, modes={mode})

        qa_rows.append(qa)

    qa_df = pd.DataFrame(qa_rows)
    n_ok = int(qa_df['status'].str.startswith(('ok', 'heuristic')).sum()) \
        if len(qa_df) else 0
    n_components = nx.number_connected_components(G) if len(G) else 0
    logger.info(
        f"✓ Station graph: {G.number_of_nodes()} stations, "
        f"{G.number_of_edges()} edges, {n_components} components "
        f"({n_ok}/{len(in_scope)} lines built)")
    return G, qa_df


def build_node_to_hub_mapping(scored_hubs: pd.DataFrame) -> Dict:
    """Map station node IDs to hub IDs from the grouped/scored hubs table.

    The hubs table stores member stations as a stringified list in the
    `node` column (e.g. "[31655]" or "['a', 'b']").

    Args:
        scored_hubs: DataFrame with columns [group, node]

    Returns:
        Dict {node_id: 'hub_<group>'}

    Raises:
        ValueError: If a node appears in more than one hub group
    """
    mapping: Dict = {}
    for _, row in scored_hubs.iterrows():
        hub_id = f"hub_{row['group']}"
        raw = row['node']
        if isinstance(raw, str):
            members = ast.literal_eval(raw)
        elif isinstance(raw, (list, tuple, set)):
            members = list(raw)
        else:
            members = [raw]
        for node_id in members:
            if node_id in mapping and mapping[node_id] != hub_id:
                raise ValueError(
                    f"Node {node_id} appears in both {mapping[node_id]} "
                    f"and {hub_id}")
            mapping[node_id] = hub_id

    logger.info(f"✓ Hub mapping: {len(mapping)} stations in "
                f"{scored_hubs['group'].nunique()} hubs")
    return mapping


def contract_to_hub_graph(G: nx.Graph, node_to_hub: Dict) -> nx.Graph:
    """Contract stations sharing a hub group into super-nodes.

    Intra-hub edges become self-loops and are dropped (transfers within a
    hub are free); parallel inter-hub edges collapse to the minimum weight
    with unioned line/mode sets. Stations not in any hub keep singleton
    'stn_<node>' identities.

    Args:
        G: Station graph from build_station_graph
        node_to_hub: {node_id: hub_id} from build_node_to_hub_mapping

    Returns:
        Contracted undirected graph; node attributes: is_hub, members,
        x, y (member centroid)
    """
    H = nx.Graph()

    def label(node_id):
        return node_to_hub.get(node_id, f"stn_{node_id}")

    for node_id, attrs in G.nodes(data=True):
        lbl = label(node_id)
        if H.has_node(lbl):
            H.nodes[lbl]['members'].append(node_id)
        else:
            H.add_node(lbl, is_hub=lbl.startswith('hub_'),
                       members=[node_id],
                       _xs=[], _ys=[])
        H.nodes[lbl]['_xs'].append(attrs.get('x'))
        H.nodes[lbl]['_ys'].append(attrs.get('y'))

    for lbl, attrs in H.nodes(data=True):
        xs = [x for x in attrs.pop('_xs') if x is not None]
        ys = [y for y in attrs.pop('_ys') if y is not None]
        attrs['x'] = sum(xs) / len(xs) if xs else None
        attrs['y'] = sum(ys) / len(ys) if ys else None

    for u, v, data in G.edges(data=True):
        lu, lv = label(u), label(v)
        if lu == lv:
            continue  # intra-hub transfer: free
        if H.has_edge(lu, lv):
            edge = H.edges[lu, lv]
            edge['length_m'] = min(edge['length_m'], data['length_m'])
            edge['time_min'] = min(edge['time_min'], data['time_min'])
            edge['lines'] |= data['lines']
            edge['modes'] |= data['modes']
        else:
            H.add_edge(lu, lv, length_m=data['length_m'],
                       time_min=data['time_min'],
                       lines=set(data['lines']), modes=set(data['modes']))

    n_hubs = sum(1 for _, d in H.nodes(data=True) if d['is_hub'])
    logger.info(
        f"✓ Contracted graph: {H.number_of_nodes()} nodes "
        f"({n_hubs} hubs, {H.number_of_nodes() - n_hubs} singleton stations), "
        f"{H.number_of_edges()} edges")
    return H
