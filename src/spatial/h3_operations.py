"""
H3 Hexagonal Spatial Operations
================================
Functions for H3 hexagon creation, assignment, and aggregation.
"""

import h3
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
from typing import List, Tuple

from ..config import (
    H3_RESOLUTION,
    CRS_WGS84,
    CRS_ISRAEL_TM,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


def assign_h3_to_points(
    gdf: gpd.GeoDataFrame,
    resolution: int = H3_RESOLUTION
) -> gpd.GeoDataFrame:
    """
    Assign H3 hexagonal indices to point geometries.

    Args:
        gdf: GeoDataFrame with point geometries
        resolution: H3 resolution level (default from config)

    Returns:
        GeoDataFrame with added 'h3_index' column
    """
    logger.info(f"Assigning H3 indices at resolution {resolution}")

    # Ensure WGS84 CRS for H3
    gdf_wgs84 = gdf.to_crs(CRS_WGS84)

    # Extract lat/lon
    gdf_wgs84['_lat'] = gdf_wgs84.geometry.y
    gdf_wgs84['_lon'] = gdf_wgs84.geometry.x

    # Assign H3 index
    gdf_wgs84['h3_index'] = gdf_wgs84.apply(
        lambda row: h3.latlng_to_cell(row['_lat'], row['_lon'], resolution),
        axis=1
    )

    # Clean up temporary columns
    gdf_wgs84 = gdf_wgs84.drop(columns=['_lat', '_lon'])

    logger.info(f"✓ Assigned H3 indices to {len(gdf_wgs84)} points")
    logger.info(f"✓ Created {gdf_wgs84['h3_index'].nunique()} unique hexagons")

    return gdf_wgs84


def h3_to_polygon(h3_index: str) -> Polygon:
    """
    Convert H3 index to Shapely Polygon.

    Args:
        h3_index: H3 hexagon index

    Returns:
        Shapely Polygon representing the hexagon
    """
    boundary = h3.cell_to_boundary(h3_index)
    # H3 returns (lat, lon), need (lon, lat) for Shapely
    return Polygon([(lon, lat) for lat, lon in boundary])


def create_h3_hexagons(
    gdf: gpd.GeoDataFrame,
    group_columns: List[str],
    aggregation_columns: dict,
) -> gpd.GeoDataFrame:
    """
    Create H3 hexagon geometries and aggregate data by hexagon.

    Args:
        gdf: GeoDataFrame with h3_index column
        group_columns: Columns to group by (including h3_index)
        aggregation_columns: Dictionary of column -> aggregation function

    Returns:
        GeoDataFrame with hexagon geometries
    """
    logger.info("Creating H3 hexagon geometries and aggregating data")

    # Group and aggregate
    grouped = gdf.groupby(group_columns).agg(aggregation_columns).reset_index()

    # Create hexagon geometries
    grouped['geometry'] = grouped['h3_index'].apply(h3_to_polygon)

    # Convert to GeoDataFrame
    result = gpd.GeoDataFrame(grouped, geometry='geometry', crs=CRS_WGS84)

    logger.info(f"✓ Created {len(result)} hexagons with aggregated data")

    return result


def aggregate_by_h3(
    gdf: gpd.GeoDataFrame,
    resolution: int = H3_RESOLUTION,
    mode_column: str = 'Mode_Planned',
    line_column: str = 'LINE_ID',
    node_column: str = 'node',
) -> gpd.GeoDataFrame:
    """
    Complete H3 aggregation pipeline: assign indices, aggregate lines and modes.

    This function:
    1. Assigns H3 indices to points
    2. Groups by H3 index and mode
    3. Aggregates line counts and lists
    4. Further aggregates by H3 index (combining all modes)
    5. Creates hexagon geometries

    Args:
        gdf: GeoDataFrame with transit nodes
        resolution: H3 resolution
        mode_column: Column containing mode information
        line_column: Column containing line IDs
        node_column: Column containing node IDs

    Returns:
        GeoDataFrame with H3 hexagons and aggregated transit data
    """
    logger.info("Running complete H3 aggregation pipeline")

    # Step 1: Assign H3 indices
    gdf_with_h3 = assign_h3_to_points(gdf, resolution=resolution)

    # Step 2: Group by h3_index, node, and mode
    logger.info("Aggregating lines by H3, node, and mode")

    h3_mode_grouped = gdf_with_h3.groupby(['h3_index', node_column, mode_column]).agg({
        line_column: ['nunique', lambda x: list(x.unique())]
    }).reset_index()

    # Flatten column names
    h3_mode_grouped.columns = [
        'h3_index', node_column, mode_column, 'Line_Nunique', 'Line_Unique'
    ]

    # Step 3: Further aggregate by h3_index only (combining all modes)
    logger.info("Aggregating by H3 index (combining modes)")

    h3_final = h3_mode_grouped.groupby('h3_index').agg({
        node_column: 'first',
        mode_column: lambda x: list(x.unique()),
        'Line_Nunique': 'sum',
        'Line_Unique': lambda x: list(set([item for sublist in x for item in sublist]))
    }).reset_index()

    # Rename mode column to plural
    h3_final = h3_final.rename(columns={mode_column: 'modes'})

    # Step 4: Create hexagon geometries
    h3_final['geometry'] = h3_final['h3_index'].apply(h3_to_polygon)

    # Convert to GeoDataFrame
    result = gpd.GeoDataFrame(h3_final, geometry='geometry', crs=CRS_WGS84)

    logger.info(f"✓ H3 aggregation complete")
    logger.info(f"✓ Result: {len(result)} hexagons")
    logger.info(f"✓ Total unique lines: {sum([len(x) for x in result['Line_Unique']])}")

    # Log mode distribution
    all_modes = [mode for modes_list in result['modes'] for mode in modes_list]
    mode_counts = pd.Series(all_modes).value_counts()
    logger.info("Mode distribution:")
    for mode, count in mode_counts.items():
        logger.info(f"  {mode}: {count}")

    return result


def get_h3_neighbors(h3_index: str, ring: int = 1) -> List[str]:
    """
    Get neighboring H3 hexagons.

    Args:
        h3_index: H3 hexagon index
        ring: Distance ring (1 = immediate neighbors)

    Returns:
        List of neighboring H3 indices
    """
    return list(h3.grid_disk(h3_index, ring))


def calculate_h3_centroids(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Calculate centroids of H3 hexagons.

    Args:
        gdf: GeoDataFrame with H3 hexagons

    Returns:
        GeoDataFrame with centroids added as 'centroid' column
    """
    logger.debug("Calculating H3 hexagon centroids")

    gdf_copy = gdf.copy()

    # Convert to projected CRS for accurate centroids
    gdf_proj = gdf_copy.to_crs(CRS_ISRAEL_TM)
    gdf_copy['centroid'] = gdf_proj.geometry.centroid

    logger.debug(f"✓ Calculated centroids for {len(gdf_copy)} hexagons")

    return gdf_copy
