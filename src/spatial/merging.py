"""
Hexagon Merging and Grouping Operations
========================================
Functions for grouping nearby hexagons into hub areas.
"""

import geopandas as gpd
import pandas as pd
from typing import List

from ..config import (
    HUB_MERGE_THRESHOLD_M,
    HUB_MERGE_TOLERANCE_M,
    CRS_ISRAEL_TM,
    PROGRESS_REPORT_INTERVAL,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class UnionFind:
    """
    Union-Find (Disjoint Set) data structure for efficient grouping.

    Used to find connected components where hexagons are "connected"
    if they are within merge threshold distance.
    """

    def __init__(self, n: int):
        """
        Initialize Union-Find structure.

        Args:
            n: Number of elements
        """
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        """
        Find root of element x with path compression.

        Args:
            x: Element index

        Returns:
            Root index
        """
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # Path compression
        return self.parent[x]

    def union(self, x: int, y: int) -> None:
        """
        Union two elements.

        Args:
            x: First element index
            y: Second element index
        """
        root_x = self.find(x)
        root_y = self.find(y)

        if root_x != root_y:
            # Union by rank
            if self.rank[root_x] < self.rank[root_y]:
                self.parent[root_x] = root_y
            elif self.rank[root_x] > self.rank[root_y]:
                self.parent[root_y] = root_x
            else:
                self.parent[root_y] = root_x
                self.rank[root_x] += 1

    def get_groups(self) -> dict:
        """
        Get mapping from root to group ID.

        Returns:
            Dictionary mapping root index to group ID
        """
        roots = {}
        group_id = 0
        for i in range(len(self.parent)):
            root = self.find(i)
            if root not in roots:
                roots[root] = group_id
                group_id += 1
        return roots


def create_proximity_groups(
    gdf: gpd.GeoDataFrame,
    distance_threshold: float = HUB_MERGE_THRESHOLD_M,
    tolerance: float = HUB_MERGE_TOLERANCE_M,
) -> gpd.GeoDataFrame:
    """
    Group hexagons based on edge-to-edge proximity using Union-Find.

    Hexagons are grouped if their edges are within distance_threshold.
    Uses transitive grouping: if A is near B, and B is near C, then
    A, B, and C are all in the same group.

    Args:
        gdf: GeoDataFrame with hexagon geometries
        distance_threshold: Maximum edge-to-edge distance in meters
        tolerance: Additional tolerance for floating point precision

    Returns:
        GeoDataFrame with added 'group' column
    """
    logger.info(f"Creating proximity groups (threshold: {distance_threshold}m)")

    # Convert to projected CRS for meter-based operations
    gdf_proj = gdf.to_crs(CRS_ISRAEL_TM).copy()
    gdf_proj = gdf_proj.reset_index(drop=True)

    n = len(gdf_proj)
    logger.info(f"Processing {n} hexagons...")

    # Build spatial index for efficient querying
    logger.debug("Building spatial index...")
    sindex = gdf_proj.sindex

    # Initialize Union-Find
    uf = UnionFind(n)

    # Effective distance with tolerance
    effective_distance = distance_threshold + tolerance

    # Find all pairs within threshold
    pairs_found = 0

    for idx1 in range(n):
        geom1 = gdf_proj.iloc[idx1].geometry

        # Query spatial index for potential neighbors
        minx, miny, maxx, maxy = geom1.bounds
        search_bounds = (
            minx - distance_threshold,
            miny - distance_threshold,
            maxx + distance_threshold,
            maxy + distance_threshold
        )

        possible_neighbors = list(sindex.intersection(search_bounds))

        # Check actual edge-to-edge distance
        for idx2 in possible_neighbors:
            if idx2 <= idx1:  # Avoid checking pairs twice
                continue

            geom2 = gdf_proj.iloc[idx2].geometry
            distance = geom1.distance(geom2)

            if distance <= effective_distance:
                uf.union(idx1, idx2)
                pairs_found += 1

        # Progress reporting
        if (idx1 + 1) % PROGRESS_REPORT_INTERVAL == 0:
            logger.debug(f"  Processed {idx1 + 1}/{n} hexagons...")

    logger.info(f"✓ Found {pairs_found} neighbor pairs within {distance_threshold}m")

    # Assign group labels
    logger.debug("Assigning group IDs...")
    root_to_group = uf.get_groups()
    labels = [root_to_group[uf.find(idx)] for idx in range(n)]

    gdf['group'] = labels

    # Statistics
    group_sizes = gdf.groupby('group').size()
    n_groups = len(group_sizes)

    logger.info(f"✓ Created {n_groups} groups from {n} hexagons")
    logger.info(f"  Single hexagon groups: {(group_sizes == 1).sum()}")
    logger.info(f"  Multi-hexagon groups: {(group_sizes > 1).sum()}")
    logger.info(f"  Largest group: {group_sizes.max()} hexagons")
    logger.info(f"  Average group size: {group_sizes.mean():.2f} hexagons")

    return gdf


def aggregate_groups(
    gdf: gpd.GeoDataFrame,
    group_column: str = 'group',
) -> gpd.GeoDataFrame:
    """
    Aggregate hexagons into hub groups.

    Groups hexagons by group ID and:
    - Dissolves geometries into multipolygon
    - Sums demand and line counts
    - Creates lists of nodes, modes, and lines
    - Calculates number of unique modes

    Args:
        gdf: GeoDataFrame with group assignments
        group_column: Column name for groups

    Returns:
        Aggregated hub groups GeoDataFrame
    """
    logger.info("Aggregating hexagons into hub groups...")

    if group_column not in gdf.columns:
        logger.warning(f"No '{group_column}' column found, skipping aggregation")
        return gdf

    # Build aggregation dictionary based on available columns
    agg_dict = {}

    # H3 indices (list)
    if 'h3_index' in gdf.columns:
        agg_dict['h3_index'] = lambda x: list(x.unique())

    # Nodes (list of Python integers, not numpy)
    if 'node' in gdf.columns:
        def clean_nodes(x):
            nodes = []
            for node in x.unique():
                if pd.notna(node):
                    try:
                        nodes.append(int(node))
                    except (ValueError, TypeError):
                        nodes.append(node)
            return nodes
        agg_dict['node'] = clean_nodes

    # Modes (list)
    if 'modes' in gdf.columns:
        def flatten_modes(x):
            all_modes = []
            for item in x:
                if isinstance(item, list):
                    all_modes.extend(item)
                else:
                    all_modes.append(item)
            return list(set(all_modes))
        agg_dict['modes'] = flatten_modes
    elif 'Mode_Planned' in gdf.columns:
        def flatten_modes_alt(x):
            all_modes = []
            for item in x:
                if isinstance(item, list):
                    all_modes.extend(item)
                else:
                    all_modes.append(item)
            return list(set(all_modes))
        agg_dict['Mode_Planned'] = flatten_modes_alt

    # Lines
    if 'Line_Nunique' in gdf.columns:
        agg_dict['Line_Nunique'] = 'sum'

    if 'Line_Unique' in gdf.columns:
        def flatten_lines(x):
            all_lines = []
            for item in x:
                if isinstance(item, list):
                    all_lines.extend(item)
                else:
                    all_lines.append(item)
            return list(set(all_lines))
        agg_dict['Line_Unique'] = flatten_lines

    # Demand columns
    if 'TotalDemand' in gdf.columns:
        agg_dict['TotalDemand'] = 'sum'

    if 'TotalTransfers' in gdf.columns:
        agg_dict['TotalTransfers'] = 'sum'

    # Spatial/categorical columns - take first value
    for col in ['address', 'area', 'district', 'metro_area']:
        if col in gdf.columns:
            agg_dict[col] = 'first'

    # Perform aggregation
    logger.debug(f"Aggregating {len(agg_dict)} columns")

    try:
        grouped = gdf.groupby(group_column).agg(agg_dict).reset_index()
    except Exception as e:
        logger.error(f"Error during aggregation: {e}")
        logger.debug(f"Available columns: {list(gdf.columns)}")
        logger.debug(f"Aggregation dict: {agg_dict}")
        raise

    # Calculate number of modes
    if 'modes' in grouped.columns:
        grouped['num_modes'] = grouped['modes'].apply(
            lambda x: len(x) if isinstance(x, list) else 1
        )
    elif 'Mode_Planned' in grouped.columns:
        grouped['num_modes'] = grouped['Mode_Planned'].apply(
            lambda x: len(x) if isinstance(x, list) else 1
        )

    # Dissolve geometries by group
    try:
        logger.debug("Dissolving geometries...")
        dissolved = gdf.dissolve(by=group_column, as_index=False)
        grouped['geometry'] = dissolved['geometry'].values
    except Exception as e:
        logger.warning(f"Error dissolving geometries: {e}")
        # Use first geometry as fallback
        grouped['geometry'] = gdf.groupby(group_column)['geometry'].first().values

    # Create GeoDataFrame
    grouped_gdf = gpd.GeoDataFrame(grouped, geometry='geometry', crs=gdf.crs)

    logger.info(f"✓ Created {len(grouped_gdf)} hub groups from {len(gdf)} hexagons")

    # Calculate and log group statistics
    if 'TotalDemand' in grouped_gdf.columns:
        total_demand = grouped_gdf['TotalDemand'].sum()
        logger.info(f"✓ Total demand: {total_demand:,.0f}")

    if 'num_modes' in grouped_gdf.columns:
        mode_dist = grouped_gdf['num_modes'].value_counts().sort_index()
        logger.info("Mode count distribution:")
        for n_modes, count in mode_dist.items():
            logger.info(f"  {n_modes} modes: {count} hubs")

    return grouped_gdf


def filter_single_mode_hubs(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Filter out hub groups that have only one mode.

    Hubs must have at least 2 mass-transit modes to qualify.

    Args:
        gdf: GeoDataFrame with hub groups

    Returns:
        Filtered GeoDataFrame
    """
    logger.info("Filtering out single-mode hubs...")

    initial_count = len(gdf)

    if 'num_modes' in gdf.columns:
        filtered = gdf[gdf['num_modes'] >= 2].copy()
    elif 'modes' in gdf.columns:
        filtered = gdf[gdf['modes'].apply(lambda x: len(x) >= 2)].copy()
    elif 'Mode_Planned' in gdf.columns:
        filtered = gdf[gdf['Mode_Planned'].apply(lambda x: len(x) >= 2 if isinstance(x, list) else False)].copy()
    else:
        logger.warning("No mode column found, cannot filter single-mode hubs")
        return gdf

    removed_count = initial_count - len(filtered)
    logger.info(f"✓ Filtered out {removed_count} single-mode hubs")
    logger.info(f"✓ Remaining hubs: {len(filtered)}")

    return filtered
