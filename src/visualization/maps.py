"""
Interactive Map Visualization
==============================
Create interactive maps to visualize hub locations and scores.
"""

import geopandas as gpd
import pandas as pd
from typing import Optional

try:
    import folium
    from folium import plugins
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

from ..config import (
    MAP_TILES,
    MAP_CENTER_ISRAEL,
    MAP_ZOOM_DEFAULT,
    TIER_COLORS,
    TIER_NATIONAL,
    TIER_METRO,
    TIER_LOCAL,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


def create_hub_map(
    gdf: gpd.GeoDataFrame,
    color_by: str = 'tier',
    popup_columns: Optional[list] = None,
    output_file: Optional[str] = None,
) -> Optional[object]:
    """
    Create interactive map of hubs.

    Args:
        gdf: GeoDataFrame with hubs
        color_by: Column to use for coloring ('tier' or 'final_score')
        popup_columns: Columns to include in popup (if None, uses defaults)
        output_file: Path to save HTML file (if None, returns map object)

    Returns:
        Folium map object (if output_file is None)
    """
    if not FOLIUM_AVAILABLE:
        logger.error("Folium not installed, cannot create maps")
        logger.info("Install with: pip install folium")
        return None

    logger.info("Creating interactive hub map...")

    # Ensure WGS84 CRS for web mapping
    gdf_wgs84 = gdf.to_crs('EPSG:4326')

    # Create map
    m = folium.Map(
        location=MAP_CENTER_ISRAEL,
        zoom_start=MAP_ZOOM_DEFAULT,
        tiles=MAP_TILES
    )

    # Default popup columns
    if popup_columns is None:
        popup_columns = ['group', 'tier', 'TotalDemand', 'final_score', 'rank']
        popup_columns = [col for col in popup_columns if col in gdf_wgs84.columns]

    # Add hubs to map
    for idx, row in gdf_wgs84.iterrows():
        # Get centroid for marker
        centroid = row.geometry.centroid

        # Determine color
        if color_by == 'tier' and 'tier' in row:
            color = TIER_COLORS.get(row['tier'], '#gray')
        elif color_by == 'final_score' and 'final_score' in row:
            # Color by score (red=high, yellow=mid, green=low)
            score = row['final_score']
            if score >= 7:
                color = '#d62728'  # Red
            elif score >= 4:
                color = '#ff7f0e'  # Orange
            else:
                color = '#2ca02c'  # Green
        else:
            color = '#1f77b4'  # Blue (default)

        # Create popup text
        popup_html = "<b>Hub Information</b><br>"
        for col in popup_columns:
            if col in row:
                value = row[col]
                if isinstance(value, float):
                    value = f"{value:.2f}"
                elif isinstance(value, list):
                    value = ", ".join(map(str, value[:3]))  # Show first 3 items
                popup_html += f"{col}: {value}<br>"

        # Add marker
        folium.CircleMarker(
            location=[centroid.y, centroid.x],
            radius=5,
            popup=folium.Popup(popup_html, max_width=300),
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.7
        ).add_to(m)

    logger.info(f"✓ Added {len(gdf_wgs84)} hubs to map")

    # Save or return
    if output_file:
        m.save(output_file)
        logger.info(f"✓ Map saved to {output_file}")
        return None
    else:
        return m
