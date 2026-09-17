import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon

from src.pipeline.grouping import (
    apply_manual_groups,
    assign_hub_ids,
    group_hexes,
    hub_identity_table,
    parse_manual_groups,
    stable_hub_id,
)
from src.pipeline.report import RunReport


def _square(x, y, size=15):
    return Polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size)])


@pytest.fixture
def hexes():
    # squares A,B touch within 100 m; C is 119 m from B (edge to edge); D is 500 m away
    geoms = [_square(0, 0), _square(115, 0), _square(115 + 15 + 119, 0), _square(1000, 0)]
    gdf = gpd.GeoDataFrame(
        {"h3_index": list("abcd"), "node": [[1], [2], [3, 4], [5]]}, geometry=geoms, crs="EPSG:2039"
    )
    return gdf.to_crs("EPSG:4326")


def test_group_hexes_is_transitive_within_threshold(hexes):
    g = group_hexes(hexes, threshold_m=120)
    assert list(g["group"]) == [0, 0, 0, 1]


def test_group_hexes_respects_threshold(hexes):
    g = group_hexes(hexes, threshold_m=110)
    assert list(g["group"]) == [0, 0, 1, 2]


def test_parse_manual_groups():
    df = pd.DataFrame({"Nodes in group": ['"400018, 521063, 523019"'.strip('"'), "7", None, "1;2"]})
    assert parse_manual_groups(df) == [[400018, 521063, 523019], [1, 2]]


def test_apply_manual_groups_merges_and_renumbers(hexes):
    g = group_hexes(hexes, threshold_m=110)  # groups 0,0,1,2
    report = RunReport()
    manual = pd.DataFrame({"Nodes in group": ["4, 5", "99, 1"]})
    out = apply_manual_groups(g, manual, report)
    assert list(out["group"]) == [0, 0, 1, 1]
    assert any("not found" in w.message for w in report.warnings)
    assert report.metrics["groups_merged_manually"] == 1


def test_apply_manual_groups_without_file_is_noop(hexes):
    g = group_hexes(hexes, threshold_m=110)
    out = apply_manual_groups(g, None)
    assert list(out["group"]) == list(g["group"])


def test_hub_ids_are_stable_and_order_independent(hexes):
    g = assign_hub_ids(group_hexes(hexes, threshold_m=120))
    assert stable_hub_id([4, 3, 1, 2]) == stable_hub_id([1, 2, 3, 4])
    assert g["hub_id"].str.match(r"^H[0-9a-f]{10}$").all()
    assert g.loc[0, "hub_id"] == stable_hub_id([1, 2, 3, 4])
    table = hub_identity_table(g)
    assert table.loc[0, "nodes"] == "1,2,3,4" and table.loc[0, "n_hexes"] == 3
