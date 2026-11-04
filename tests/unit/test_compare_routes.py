"""Tests for the route comparison (spec section 4)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.compare.modes import load_mode_map
from src.compare.routes import (
    PAIR_COLUMNS,
    ROUTE_COMPARISON_COLUMNS,
    build_our_routes,
    line_route_map,
    match_routes,
    order_points,
)
from src.compare.settings import CompareConfig
from src.pipeline.report import RunReport
from tests.compare_helpers import (
    make_agency_network,
    make_network_nodes,
    make_our_routes,
    pts,
)

CFG = CompareConfig()


def _lrt(coords, **extra):
    return {"mode": "LRT", "coords": coords, **extra}


def _row(result, our_key):
    rows = result.routes[result.routes["our_route_key"] == our_key]
    assert len(rows) == 1, rows
    return rows.iloc[0]


def _run(lines, agency_routes, report=None):
    return match_routes(make_our_routes(lines), make_agency_network(agency_routes), CFG, report)


# ----------------------------------------------------------------------------------------
# Route units
# ----------------------------------------------------------------------------------------


def test_direction_pair_collapses_to_one_route():
    line = pts(0, 1000, 200)
    ours = make_our_routes({
        "LRT12": _lrt(line[::-1], name="קו אדום"),
        "LRT11": _lrt(line, name="קו אדום"),
        "BRT5": {"mode": "BRT", "coords": line},
    })
    assert sorted(ours["route_key"]) == ["BRT5", "LRT11+LRT12"]
    lrt = ours.set_index("route_key").loc["LRT11+LRT12"]
    assert lrt["line_ids"] == ["LRT11", "LRT12"]
    assert lrt["line_names"] == ["קו אדום", "קו אדום"]
    assert lrt["mode"] == "LRT" and lrt["agency_type"] == "LRT"
    assert lrt["n_nodes"] == 6 and not lrt["short_route"]
    assert lrt["xy"].shape == (6, 2) and lrt["xy_raw"].shape == (6, 2)
    assert line_route_map(ours) == {"LRT11": "LRT11+LRT12", "LRT12": "LRT11+LRT12",
                                    "BRT5": "BRT5"}


# ----------------------------------------------------------------------------------------
# Statuses
# ----------------------------------------------------------------------------------------


def test_matched():
    res = _run(
        {"LRT11": _lrt(pts(0, 1000, 200, y=20))},
        {"LRT:1": {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 200)}},
    )
    row = _row(res, "LRT11")
    assert row["status"] == "matched"
    assert row["agency_route_key"] == "LRT:1"
    assert row["cov_ours"] >= 0.8 and row["cov_agency"] >= 0.8
    assert row["score"] == pytest.approx(1.0)
    assert row["source_plan"] == "מפורטת"
    assert row["agency_n_our_routes"] == 1
    assert list(res.routes.columns) == ROUTE_COMPARISON_COLUMNS
    assert list(res.pairs.columns) == PAIR_COLUMNS


def test_full_match_wins_over_trunk_sharing():
    trunk = pts(0, 2000, 250)
    branch_a = [(2000 + d, d) for d in range(250, 1001, 250)]
    branch_b = [(2000 + d, -d) for d in range(250, 1001, 250)]
    res = _run(
        {"R1": {"mode": "Suburban Rail", "coords": trunk + branch_a}},
        {
            "Rail:0:A": {"coords": trunk + branch_a, "stops": trunk + branch_a},
            "Rail:0:B": {"coords": trunk + branch_b, "stops": trunk + branch_b},
        },
    )
    row = _row(res, "R1")
    assert row["status"] == "matched"
    assert row["agency_route_key"] == "Rail:0:A"
    assert "Rail:0:B" in row["candidates"]  # the trunk sharer is a candidate, not a split


def test_split():
    res = _run(
        {"LRT11": _lrt(pts(0, 2000, 200))},
        {
            "LRT:1": {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 200)},
            "LRT:2": {"coords": pts(1000, 2000, 1000), "stops": pts(1000, 2000, 200)},
        },
    )
    row = _row(res, "LRT11")
    assert row["status"] == "split_merge"
    assert "LRT:1 (" in row["candidates"] and "LRT:2 (" in row["candidates"]


def test_merge():
    res = _run(
        {"LRT11": _lrt(pts(0, 1000, 200)), "LRT21": _lrt(pts(1000, 2000, 200))},
        {"LRT:1": {"coords": pts(0, 2000, 2000), "stops": pts(0, 2000, 200)}},
    )
    for key in ("LRT11", "LRT21"):
        row = _row(res, key)
        assert row["status"] == "split_merge"
        assert row["agency_route_key"] == "LRT:1"
        assert row["agency_n_our_routes"] == 2
    assert not (res.routes["status"] == "agency_only").any()


def test_partial():
    res = _run(
        {"LRT11": _lrt(pts(0, 1000, 200))},
        {"LRT:1": {"coords": pts(0, 2000, 2000), "stops": pts(0, 2000, 200)}},
    )
    row = _row(res, "LRT11")
    assert row["status"] == "partial"
    assert row["cov_ours"] == pytest.approx(1.0)
    assert row["cov_agency"] == pytest.approx(6 / 11)
    assert CFG.match_min_score <= row["score"] < 1.0


def test_weak():
    on_line = pts(0, 2000, 1000)
    off_line = pts(3000, 9000, 1000, y=5000)
    res = _run(
        {"LRT11": _lrt(on_line + off_line)},
        {"LRT:1": {"coords": pts(0, 9000, 9000), "stops": pts(0, 9000, 1000)}},
    )
    row = _row(res, "LRT11")
    assert row["status"] == "weak"
    assert row["score"] == pytest.approx(0.3)
    # a weak candidate does not count as matching the agency route
    assert (res.routes["status"] == "agency_only").sum() == 1


def test_mode_differs():
    res = _run(
        {"BRT5": {"mode": "BRT", "coords": pts(0, 1000, 200)}},
        {"LRT:1": {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 200)}},
    )
    row = _row(res, "BRT5")
    assert row["status"] == "mode_differs"
    assert row["agency_route_key"] == "LRT:1"
    assert row["agency_type"] == "LRT"
    pair = res.pairs.iloc[0]
    assert not pair["same_mode"]
    # a cross-mode match leaves the agency route unmatched
    assert (res.routes["status"] == "agency_only").sum() == 1


def test_ours_only_for_unmapped_mode():
    res = _run(
        {"C1": {"mode": "Cable Line", "coords": pts(0, 1000, 200)}},
        {"LRT:1": {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 200)}},
    )
    row = _row(res, "C1")
    assert row["status"] == "ours_only"
    assert row["reason"] == "no agency mode"
    assert pd.isna(row["agency_route_key"])


def test_agency_only_row():
    res = _run(
        {"LRT11": _lrt(pts(0, 1000, 200))},
        {
            "LRT:1": {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 200)},
            "LRT:9": {"coords": pts(0, 1000, 1000, y=50000), "stops": pts(0, 1000, 200, y=50000),
                      "name": "far away", "line_name": "סגול"},
        },
    )
    only = res.routes[res.routes["status"] == "agency_only"]
    assert list(only["agency_route_key"]) == ["LRT:9"]
    row = only.iloc[0]
    assert pd.isna(row["our_route_key"])
    assert row["agency_name"] == "far away" and row["agency_line_name"] == "סגול"
    assert row["agency_n_stops"] == 6
    assert row["agency_n_our_routes"] == 0
    assert len(res.routes) == 2


def test_rail_uses_rail_tolerance():
    # stations sit 200 m beside the drawn geometry, our nodes on the stations
    res = _run(
        {
            "R1": {"mode": "Suburban Rail", "coords": pts(0, 1000, 200, y=200)},
            "LRT11": _lrt(pts(0, 1000, 200, y=10200)),
        },
        {
            "Rail:0:A": {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 200, y=200)},
            "LRT:1": {"coords": pts(0, 1000, 1000, y=10000),
                      "stops": pts(0, 1000, 200, y=10200)},
        },
    )
    assert _row(res, "R1")["status"] == "matched"
    assert _row(res, "LRT11")["status"] == "ours_only"


def test_agency_route_without_stops_uses_sampled_vertices():
    agency = {"LRT:1": {"coords": pts(0, 1000, 1000)}}  # no stations
    full = _run({"LRT11": _lrt(pts(0, 1000, 100))}, agency)
    row = _row(full, "LRT11")
    assert row["status"] == "matched"
    assert row["cov_agency"] == pytest.approx(1.0)
    assert row["agency_n_stops"] == 0

    half = _run({"LRT11": _lrt(pts(0, 500, 100))}, agency)
    assert _row(half, "LRT11")["cov_agency"] == pytest.approx(7 / 11)


def test_single_node_route_is_flagged_not_fatal():
    res = _run(
        {"LRT11": _lrt([(0, 0)])},
        {"LRT:1": {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 200)}},
    )
    row = _row(res, "LRT11")
    assert bool(row["short_route"]) is True
    assert row["our_n_nodes"] == 1
    assert row["cov_ours"] == pytest.approx(1.0)
    assert row["status"] == "weak"  # 2 * 1 * 1/6 / (1 + 1/6) = 0.286
    assert order_points(np.empty((0, 2))) == []
    assert order_points(np.array([[5.0, 5.0]])) == [0]
    assert order_points(np.array([[5.0, 5.0], [0.0, 0.0]])) == [0, 1]


def test_order_points_follows_a_line():
    xy = np.array([[300.0, 0.0], [0.0, 0.0], [200.0, 0.0], [100.0, 0.0], [400.0, 0.0]])
    order = order_points(xy)
    assert sorted(order) == [0, 1, 2, 3, 4]
    xs = xy[order, 0]
    assert list(xs) in (sorted(xs), sorted(xs, reverse=True))


def test_no_agency_routes_gives_all_ours_only():
    report = RunReport()
    res = _run({"LRT11": _lrt(pts(0, 1000, 200)), "C1": {"mode": "Cable Line",
                                                       "coords": [(5, 5)]}}, {}, report)
    assert list(res.routes.columns) == ROUTE_COMPARISON_COLUMNS
    assert list(res.pairs.columns) == PAIR_COLUMNS
    assert res.pairs.empty
    assert set(res.routes["status"]) == {"ours_only"}
    assert report.metrics["routes_ours_only"] == 2
    assert report.metrics["routes_matched"] == 0


def test_no_routes_of_ours_gives_all_agency_only():
    ours = build_our_routes(make_network_nodes({}), load_mode_map())
    assert ours.empty and "route_key" in ours.columns
    assert line_route_map(ours) == {}
    res = match_routes(
        ours,
        make_agency_network({"LRT:1": {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 200)}}),
        CFG,
    )
    assert list(res.routes.columns) == ROUTE_COMPARISON_COLUMNS
    assert list(res.routes["status"]) == ["agency_only"]
    empty = match_routes(ours, make_agency_network({}), CFG)
    assert empty.routes.empty and list(empty.routes.columns) == ROUTE_COMPARISON_COLUMNS
    assert empty.pairs.empty and list(empty.pairs.columns) == PAIR_COLUMNS


def test_distance_columns_raw_vs_corrected():
    line = pts(0, 1000, 200)
    res = _run(
        {"LRT11": _lrt([(x, 60) for x, _ in line], corr=line)},
        {"LRT:1": {"coords": pts(0, 1000, 1000), "stops": line}},
    )
    pair = res.pairs.set_index(["our_route_key", "agency_route_key"]).loc[("LRT11", "LRT:1")]
    assert pair["median_dist_raw_m"] == pytest.approx(60.0)
    assert pair["median_dist_corr_m"] == pytest.approx(0.0)
    assert pair["max_dist_corr_m"] == pytest.approx(0.0)
    assert pair["median_dist_corr_m"] < pair["median_dist_raw_m"]


def test_deterministic_ties():
    spec = {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 200)}
    lines = {"LRT11": _lrt(pts(0, 1000, 200))}
    a = _run(lines, {"LRT:2": spec, "LRT:1": spec})
    b = _run(lines, {"LRT:1": spec, "LRT:2": spec})
    row = _row(a, "LRT11")
    assert row["status"] == "matched"
    assert row["agency_route_key"] == "LRT:1"
    assert row["candidates"] == "LRT:1 (1.00); LRT:2 (1.00)"
    pd.testing.assert_frame_equal(a.routes, b.routes)
    pd.testing.assert_frame_equal(a.pairs, b.pairs)


def test_short_variant_of_a_matched_route_is_partial_not_merge():
    # LRT11 runs the whole agency route, LRT21 only its first half: the agency route is not
    # "shared" because one of the pairs is a full match
    res = _run(
        {"LRT11": _lrt(pts(0, 2000, 200)), "LRT21": _lrt(pts(0, 1000, 200, y=10))},
        {"LRT:1": {"coords": pts(0, 2000, 2000), "stops": pts(0, 2000, 200)}},
    )
    assert _row(res, "LRT11")["status"] == "matched"
    variant = _row(res, "LRT21")
    assert variant["status"] == "partial"
    assert variant["agency_n_our_routes"] == 2


def test_unparseable_coordinates_are_dropped_and_counted():
    nodes = make_network_nodes({"LRT11": _lrt(pts(0, 1000, 200))})
    nodes["x_itm"] = nodes["x_itm"].astype(object)
    nodes.loc[0, "x_itm"] = "n/a"
    ours = build_our_routes(nodes, load_mode_map())
    assert ours.attrs["dropped_nodes"] == 1
    assert ours.iloc[0]["n_nodes"] == 5
    report = RunReport()
    match_routes(ours, make_agency_network({}), CFG, report)
    assert any("unparseable" in e.message for e in report.warnings)


def test_score_exactly_on_match_min_score_is_partial():
    # cov_ours = 7/8, cov_agency = 7/20: harmonic mean 0.5 (0.4999999999999999 unrounded)
    nodes = pts(0, 6000, 1000) + [(0, 5000)]
    res = _run(
        {"LRT11": _lrt(nodes)},
        {"LRT:1": {"coords": pts(0, 19000, 19000), "stops": pts(0, 19000, 1000)}},
    )
    row = _row(res, "LRT11")
    assert row["cov_ours"] == pytest.approx(7 / 8)
    assert row["cov_agency"] == pytest.approx(7 / 20)
    assert row["score"] == 0.5
    assert row["status"] == "partial"
    assert not (res.routes["status"] == "agency_only").any()


def test_score_exactly_on_only_max_score_is_a_candidate():
    # cov_ours = 1, cov_agency = 1/9: harmonic mean 0.2 (0.19999999999999998 unrounded)
    res = _run(
        {"LRT11": _lrt([(0, 0)])},
        {"LRT:1": {"coords": pts(0, 8000, 8000), "stops": pts(0, 8000, 1000)}},
    )
    assert list(res.pairs["agency_route_key"]) == ["LRT:1"]
    assert res.pairs.iloc[0]["score"] == 0.2
    row = _row(res, "LRT11")
    assert row["candidates"] == "LRT:1 (0.20)"
    assert row["status"] == "weak"
