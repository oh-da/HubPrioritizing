import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon, box

from src.pipeline.report import RunReport
from src.pipeline.spatial_tags import fix_hebrew_name, get_regions_for_area, tag_area_and_location


@pytest.fixture
def hexes():
    # three small squares in ITM: inside metro core, inside metro ring only, outside metro but in district
    geoms = [box(180000, 665000, 180015, 665015), box(182000, 665000, 182015, 665015), box(190000, 665000, 190015, 665015)]
    return gpd.GeoDataFrame({"h3_index": list("abc"), "node": [[1], [2], [3]]}, geometry=geoms, crs="EPSG:2039")


@pytest.fixture
def metro():
    core = box(179000, 664000, 181000, 666000)
    ring = box(181000, 664000, 183000, 666000)
    return gpd.GeoDataFrame(
        {"METRO_NAME": ["תל אביב", "תל אביב"], "ZONE_NAME": ["גלעין", "טבעת פנימית"]}, geometry=[core, ring], crs="EPSG:2039"
    ).to_crs("EPSG:4326")


@pytest.fixture
def districts():
    return gpd.GeoDataFrame({"MACHOZ": ["מחוז צפון"]}, geometry=[box(170000, 660000, 200000, 670000)], crs="EPSG:2039").to_crs("EPSG:4326")


def test_tagging_metro_then_district_fallback(hexes, metro, districts):
    report = RunReport()
    out = tag_area_and_location(hexes, metro, districts, report)
    assert list(out["area"]) == ["תל אביב", "תל אביב", "צפון"]  # מחוז צפון -> צפון (notebook fix)
    assert list(out["location"]) == [["גלעין"], ["טבעת פנימית"], ["צפון"]]
    assert report.metrics["hexes_without_area"] == 0


def test_unknown_when_no_layer_matches(hexes, metro):
    out = tag_area_and_location(hexes, metro, None)
    assert out.loc[2, "area"] == "Unknown" and out.loc[2, "location"] == ["Unknown"]


def test_district_prefix_is_kept_for_south():
    assert fix_hebrew_name("מחוז דרום") == "מחוז דרום"  # not in the notebook fix table
    assert fix_hebrew_name("מחוז צפון") == "צפון"
    assert fix_hebrew_name("חיפ") == "חיפה"
    assert fix_hebrew_name("טבעת פנימית") == "טבעת פנימית"


@pytest.mark.parametrize(
    "area, expected",
    [
        ("תל אביב", ["Tel Aviv"]),
        ("מחוז דרום", ["Beer Sheva", "Ashdod-Ashkelon"]),
        ("באר שבע", ["Beer Sheva"]),
        ("צפון", ["Haifa"]),
        ("חיפ", ["Haifa"]),
        ("ירושלים", ["Jerusalem"]),
        ("Unknown", []),
        (None, []),
    ],
)
def test_get_regions_for_area(area, expected):
    assert get_regions_for_area(area) == expected
