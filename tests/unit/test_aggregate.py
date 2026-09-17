import math

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from src.pipeline.aggregate import (
    add_influence_area,
    aggregate_to_groups,
    bus_terminal_score,
    ring_column_names,
    tag_bus_terminals,
)
from src.pipeline.report import RunReport


@pytest.fixture
def hexes():
    geoms = [box(180000, 665000, 180015, 665015), box(180020, 665000, 180035, 665015), box(190000, 665000, 190015, 665015)]
    return gpd.GeoDataFrame(
        {
            "h3_index": ["b", "a", "c"],
            "node": [[2, 1], [3], [9]],
            "Mode_Planned": [["LRT", "BRT"], ["Metro", "LRT"], ["BRT"]],
            "Line_Unique": [["L2", "L1"], ["M1", "L3"], ["B9"]],
            "Line_Nunique": [3, 2, 1],
            "Lines_by_Mode": [{"LRT": 2, "BRT": 1}, {"Metro": 1, "LRT": 1}, {"BRT": 1}],
            "BRT Lines": [1.5, 0.0, 1.0],
            "LRT Lines": [1.5, 1.0, 0.0],
            "Metro Lines": [0.0, 1.0, 0.0],
            "TotalDemand": [100.0, 50.0, 7.0],
            "TotalTransfers": [10.0, 5.0, 0.0],
            "area": ["תל אביב", "תל אביב", "חיפה"],
            "location": [["גלעין"], ["גלעין"], ["חיפה"]],
            "address": ["Not geocoded"] * 3,
            "group": [0, 0, 1],
            "hub_id": ["Hx", "Hx", "Hy"],
        },
        geometry=geoms,
        crs="EPSG:2039",
    )


def test_aggregate_to_groups(hexes):
    g = aggregate_to_groups(hexes).set_index("group")
    assert len(g) == 2
    assert g.loc[0, "node"] == [1, 2, 3]
    assert g.loc[0, "h3_index"] == ["a", "b"]
    assert g.loc[0, "Mode_Planned"] == ["LRT", "BRT", "Metro"]  # first appearance order
    assert g.loc[0, "Line_Unique"] == ["L1", "L2", "L3", "M1"]
    assert g.loc[0, "Line_Nunique"] == 5 and g.loc[0, "TotalDemand"] == 150.0
    assert g.loc[0, "LRT Lines"] == 2.5 and g.loc[0, "Metro Lines"] == 1.0
    assert g.loc[0, "Num_Modes"] == 3 and g.loc[1, "Num_Modes"] == 1
    assert g.loc[0, "location"] == ["גלעין"] and g.loc[0, "area"] == "תל אביב"
    assert g.loc[0, "Lines_by_Mode"] == {"LRT": 3, "BRT": 1, "Metro": 1}
    assert g.loc[0, "geometry"].area == pytest.approx(2 * 15 * 15)
    assert g.crs.to_epsg() == 2039


@pytest.mark.parametrize(
    "term_type, score",
    [(None, 0), (float("nan"), 0), ("חניון לילה", 1), ("מסוף קטן", 2), ("מסוף בינוני ", 2), ("מסוף גדול", 3), ("מתקן משולב", 3), ("other", 0)],
)
def test_bus_terminal_score(term_type, score):
    assert bus_terminal_score(term_type) == score


def test_tag_bus_terminals_keeps_best_within_buffer(hexes):
    groups = aggregate_to_groups(hexes)
    terminals = gpd.GeoDataFrame(
        {"id": [1, 2, 3], "term_type": ["מסוף קטן", "מסוף גדול", "חניון לילה"]},
        geometry=[Point(180100, 665000), Point(180150, 665100), Point(195000, 665000)],
        crs="EPSG:2039",
    )
    report = RunReport()
    out = tag_bus_terminals(groups, terminals, buffer_m=200, report=report).set_index("group")
    assert out.loc[0, "term_type"] == "מסוף גדול" and out.loc[0, "bus_terminal"] == 3 and out.loc[0, "term_id"] == 2
    assert out.loc[1, "bus_terminal"] == 0 and out.loc[1, "term_type"] is None
    assert report.metrics["hubs_near_terminal"] == 1
    assert any("more than one terminal" in e.message for e in report.entries)


def test_tag_bus_terminals_without_layer(hexes):
    out = tag_bus_terminals(aggregate_to_groups(hexes), None)
    assert (out["bus_terminal"] == 0).all()


def test_ring_column_names():
    assert ring_column_names([500, 1000, 1500]) == [
        ("pop_0_500", "emp_0_500", 0, 500),
        ("pop_500_1000", "emp_500_1000", 500, 1000),
        ("pop_1000_1500", "emp_1000_1500", 1000, 1500),
    ]


def test_add_influence_area_proportional_allocation(hexes, synthetic_taz):
    groups = aggregate_to_groups(hexes)
    report = RunReport()
    out = add_influence_area(groups, synthetic_taz, (500, 1000, 1500), report).set_index("group")
    taz_area = 2000.0 * 2000.0
    # group 0 centroid ~ (180017, 665007): 500 m circle fully inside TAZ 1 (4000 pop)
    assert out.loc[0, "pop_0_500"] == pytest.approx(4000 * math.pi * 500**2 / taz_area, rel=0.02)
    assert out.loc[0, "emp_0_500"] == pytest.approx(2000 * math.pi * 500**2 / taz_area, rel=0.02)
    # the 1000-1500 ring pokes outside the 2 km square, so it gets less than the full ring share
    full_ring = 4000 * math.pi * (1500**2 - 1000**2) / taz_area
    assert 0 < out.loc[0, "pop_1000_1500"] < full_ring
    # group 1 (x=190000) is 5 km from both squares -> nothing
    assert out.loc[1, "pop_0_500"] == 0 and out.loc[1, "emp_1000_1500"] == 0
    assert report.metrics["hubs_without_taz_coverage"] == 1


def test_add_influence_area_custom_rings_and_missing_layer(hexes, synthetic_taz):
    groups = aggregate_to_groups(hexes)
    out = add_influence_area(groups, synthetic_taz, (600, 1000, 1200)).set_index("group")
    assert "pop_0_600" in out.columns and "emp_1000_1200" in out.columns
    assert out.loc[0, "pop_0_600"] > 0
    none = add_influence_area(groups, None)
    assert (none["pop_0_500"] == 0).all()
    with pytest.raises(ValueError):
        add_influence_area(groups, synthetic_taz, (1000, 500))
