"""
Data Loading Functions
=======================
Functions for loading transit nodes, demand data, spatial layers, and other datasets.
"""

import pandas as pd
import geopandas as gpd
from pathlib import Path
from typing import Dict, Optional, Union
from shapely import wkt
from shapely.geometry import Point

from ..config import (
    DEFAULT_ENCODING,
    CRS_WGS84,
    CRS_ISRAEL_TM,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


def load_transit_nodes(
    filepath: Union[str, Path],
    encoding: str = DEFAULT_ENCODING,
) -> gpd.GeoDataFrame:
    """
    Load transit nodes from CSV file.

    Expected columns: node, LINE_ID, X, Y (or geometry)

    Args:
        filepath: Path to CSV file
        encoding: File encoding

    Returns:
        GeoDataFrame with transit nodes

    Raises:
        ValueError: If required columns are missing
    """
    logger.info(f"Loading transit nodes from {filepath}")

    # Read CSV
    df = pd.read_csv(filepath, encoding=encoding)
    logger.debug(f"Loaded {len(df)} rows from CSV")

    # Check for geometry or coordinates
    if 'geometry' in df.columns:
        # Parse WKT geometry
        logger.debug("Parsing geometry from WKT")
        df['geometry'] = df['geometry'].apply(
            lambda x: wkt.loads(x) if pd.notna(x) else None
        )
        gdf = gpd.GeoDataFrame(df, geometry='geometry', crs=CRS_ISRAEL_TM)

    elif 'X' in df.columns and 'Y' in df.columns:
        # Create geometry from coordinates
        logger.debug("Creating geometry from X, Y coordinates")
        geometry = [Point(x, y) for x, y in zip(df['X'], df['Y'])]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=CRS_ISRAEL_TM)

    else:
        raise ValueError("CSV must contain either 'geometry' column or both 'X' and 'Y' columns")

    # Validate required columns
    required_cols = ['node', 'LINE_ID']
    missing_cols = [col for col in required_cols if col not in gdf.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    logger.info(f"✓ Loaded {len(gdf)} transit nodes")
    logger.debug(f"CRS: {gdf.crs}")
    logger.debug(f"Columns: {list(gdf.columns)}")

    return gdf


def load_lines_and_modes(
    filepath: Union[str, Path],
    encoding: str = DEFAULT_ENCODING,
) -> pd.DataFrame:
    """
    Load line-to-mode mapping from CSV.

    Expected columns: Line_ModelName, Mode_Planned, Area

    Args:
        filepath: Path to CSV file
        encoding: File encoding

    Returns:
        DataFrame with line and mode information
    """
    logger.info(f"Loading lines and modes from {filepath}")

    df = pd.read_csv(filepath, encoding=encoding)

    # Validate columns
    expected_cols = ['Line_ModelName', 'Mode_Planned']
    missing_cols = [col for col in expected_cols if col not in df.columns]
    if missing_cols:
        logger.warning(f"Missing expected columns: {missing_cols}")

    logger.info(f"✓ Loaded {len(df)} line records")

    return df


def load_demand_data(
    filepath: Union[str, Path],
    sheet_names: Optional[list] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Load demand data from Excel file with multiple model sheets.

    Args:
        filepath: Path to Excel file
        sheet_names: List of sheet names to load (if None, loads common ones)

    Returns:
        Dictionary mapping model names to DataFrames
    """
    logger.info(f"Loading demand data from {filepath}")

    if sheet_names is None:
        sheet_names = [
            'Haifa', 'TelAviv', 'Jerusalem', 'BeerSheva',
            'Ashdod', 'Hadera', 'HaifaMetronit', 'Ashkelon'
        ]

    demand_data = {}

    for sheet in sheet_names:
        try:
            df = pd.read_excel(filepath, sheet_name=sheet)
            demand_data[sheet] = df
            logger.debug(f"✓ Loaded {sheet}: {len(df)} records")
        except Exception as e:
            logger.warning(f"Could not load sheet '{sheet}': {e}")

    logger.info(f"✓ Loaded demand data from {len(demand_data)} models")

    return demand_data


def load_spatial_layer(
    filepath: Union[str, Path],
    layer_name: str = "spatial layer",
    encoding: str = DEFAULT_ENCODING,
    target_crs: Optional[str] = None,
) -> gpd.GeoDataFrame:
    """
    Load a spatial layer (shapefile, GeoJSON, etc.).

    Args:
        filepath: Path to spatial file
        layer_name: Descriptive name for logging
        encoding: File encoding
        target_crs: Target CRS to reproject to (if None, keeps original)

    Returns:
        GeoDataFrame
    """
    logger.info(f"Loading {layer_name} from {filepath}")

    try:
        gdf = gpd.read_file(filepath, encoding=encoding)
        logger.debug(f"Loaded {len(gdf)} features")
        logger.debug(f"CRS: {gdf.crs}")

        # Reproject if requested
        if target_crs and gdf.crs != target_crs:
            logger.debug(f"Reprojecting to {target_crs}")
            gdf = gdf.to_crs(target_crs)

        logger.info(f"✓ Loaded {layer_name}: {len(gdf)} features")

        return gdf

    except Exception as e:
        logger.error(f"Failed to load {layer_name}: {e}")
        raise


def load_metro_areas(filepath: Union[str, Path]) -> gpd.GeoDataFrame:
    """
    Load metropolitan areas shapefile.

    Args:
        filepath: Path to metro areas shapefile

    Returns:
        GeoDataFrame with metro areas
    """
    return load_spatial_layer(
        filepath,
        layer_name="metro areas",
        target_crs=CRS_ISRAEL_TM
    )


def load_districts(filepath: Union[str, Path]) -> gpd.GeoDataFrame:
    """
    Load administrative districts shapefile.

    Args:
        filepath: Path to districts shapefile

    Returns:
        GeoDataFrame with districts
    """
    return load_spatial_layer(
        filepath,
        layer_name="districts",
        target_crs=CRS_ISRAEL_TM
    )


def load_taz_zones(filepath: Union[str, Path]) -> gpd.GeoDataFrame:
    """
    Load Traffic Analysis Zones (TAZ) with population and employment data.

    Expected columns: POP_2050, EMPL_2050

    Args:
        filepath: Path to TAZ shapefile

    Returns:
        GeoDataFrame with TAZ data
    """
    logger.info(f"Loading TAZ data from {filepath}")

    gdf = load_spatial_layer(filepath, layer_name="TAZ zones", target_crs=CRS_ISRAEL_TM)

    # Validate expected columns
    expected_cols = ['POP_2050', 'EMPL_2050']
    missing_cols = [col for col in expected_cols if col not in gdf.columns]

    if missing_cols:
        logger.warning(f"Missing TAZ columns: {missing_cols}")
        logger.info(f"Available columns: {list(gdf.columns)}")
        # Create dummy columns
        for col in missing_cols:
            gdf[col] = 0

    # Ensure numeric types
    gdf['POP_2050'] = pd.to_numeric(gdf['POP_2050'], errors='coerce').fillna(0)
    gdf['EMPL_2050'] = pd.to_numeric(gdf['EMPL_2050'], errors='coerce').fillna(0)

    logger.info(f"✓ Total population: {gdf['POP_2050'].sum():,.0f}")
    logger.info(f"✓ Total employment: {gdf['EMPL_2050'].sum():,.0f}")

    return gdf


def load_bus_terminals(
    filepath: Optional[Union[str, Path]] = None
) -> Optional[gpd.GeoDataFrame]:
    """
    Load bus terminals shapefile (optional).

    Args:
        filepath: Path to bus terminals shapefile (can be None)

    Returns:
        GeoDataFrame with terminals or None
    """
    if filepath is None:
        logger.info("No bus terminals file provided (optional)")
        return None

    try:
        return load_spatial_layer(
            filepath,
            layer_name="bus terminals",
            target_crs=CRS_ISRAEL_TM
        )
    except Exception as e:
        logger.warning(f"Could not load bus terminals: {e}")
        return None


def load_processed_hubs(
    filepath: Union[str, Path],
    encoding: str = 'utf-8-sig',
) -> gpd.GeoDataFrame:
    """
    Load previously processed hubs from CSV or GeoJSON.

    Args:
        filepath: Path to hubs file
        encoding: File encoding (for CSV)

    Returns:
        GeoDataFrame with hub data
    """
    logger.info(f"Loading processed hubs from {filepath}")

    filepath = Path(filepath)

    if filepath.suffix == '.csv':
        # Load from CSV
        df = pd.read_csv(filepath, encoding=encoding)

        # Parse geometry if it's WKT string
        if 'geometry' in df.columns and df['geometry'].dtype == 'object':
            df['geometry'] = df['geometry'].apply(
                lambda x: wkt.loads(x) if pd.notna(x) and isinstance(x, str) else x
            )

        gdf = gpd.GeoDataFrame(df, geometry='geometry', crs=CRS_WGS84)

    elif filepath.suffix in ['.geojson', '.json']:
        # Load from GeoJSON
        gdf = gpd.read_file(filepath)

    elif filepath.suffix in ['.shp', '.gpkg']:
        # Load from shapefile or geopackage
        gdf = gpd.read_file(filepath)

    else:
        raise ValueError(f"Unsupported file format: {filepath.suffix}")

    logger.info(f"✓ Loaded {len(gdf)} hub records")

    return gdf
