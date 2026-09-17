"""
Shared pytest fixtures: small synthetic datasets that exercise every pipeline
stage without any external files.

Coordinates are in EPSG:2039 (Israel TM Grid) around Tel Aviv so that metre
based buffers behave like they do on real data.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "real"

CRS_ITM = "EPSG:2039"
CRS_WGS84 = "EPSG:4326"


@pytest.fixture
def itm_crs() -> str:
    return CRS_ITM


@pytest.fixture
def synthetic_hub_points() -> gpd.GeoDataFrame:
    """Three hub centres in EPSG:2039: two 300 m apart, one 5 km away."""
    pts = [Point(180000, 665000), Point(180300, 665000), Point(185000, 665000)]
    return gpd.GeoDataFrame(
        {"group": [0, 1, 2], "TotalDemand": [60000.0, 8000.0, 1500.0]},
        geometry=pts,
        crs=CRS_ITM,
    )


@pytest.fixture
def synthetic_taz() -> gpd.GeoDataFrame:
    """Two square TAZ polygons (2 km x 2 km) with known population and jobs.

    The first square is centred on the first synthetic hub, so a 500 m circle
    around that hub lies entirely inside it.
    """
    def square(cx, cy, half):
        return Polygon(
            [(cx - half, cy - half), (cx + half, cy - half), (cx + half, cy + half), (cx - half, cy + half)]
        )

    return gpd.GeoDataFrame(
        {
            "TAZ_ID": [1, 2],
            "POP_2050": [4000.0, 1000.0],
            "EMPL_2050": [2000.0, 500.0],
        },
        geometry=[square(180000, 665000, 1000), square(185000, 665000, 1000)],
        crs=CRS_ITM,
    )


@pytest.fixture
def real_fixtures_dir() -> Path:
    """Directory holding the user's real sample inputs and the golden workbook.

    Tests that need it call ``pytest.skip`` when it is absent so the unit suite
    stays runnable on a clean checkout.
    """
    if not REAL_FIXTURES_DIR.exists():
        pytest.skip(f"real fixtures not present at {REAL_FIXTURES_DIR}")
    return REAL_FIXTURES_DIR
