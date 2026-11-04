"""Tests for the route comparison (spec section 4)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.compare.modes import load_mode_map
from src.compare.routes import (
    AGENCY_ROW_STATUSES,
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
NO_CONTAINMENT = CompareConfig(containment=False)


def _lrt(coords, **extra):
    return {"mode": "LRT", "coords": coords, **extra}


def _row(result, our_key):
    """The status row of one of our routes (a ``covered`` row may also carry its key)."""
    r = result.routes
    rows = r[(r["our_route_key"] == our_key) & ~r["status"].isin(AGENCY_ROW_STATUSES)]
    assert len(rows) == 1, rows
    return rows.iloc[0]


def _run(lines, agency_routes, report=None):
    return match_routes(make_our_routes(lines), make_agency_network(agency_routes), CFG, report)


def _run_cfg(lines, agency_routes, cfg, report=None):
    return match_routes(make_our_routes(lines), make_agency_network(agency_routes), cfg, report)


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
    lines = {
            "R1": {"mode": "Suburban Rail", "coords": pts(0, 1000, 200, y=200)},
            "LRT11": _lrt(pts(0, 1000, 200, y=10200)),
    }
    agency = {
        "Rail:0:A": {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 200, y=200)},
        "LRT:1": {"coords": pts(0, 1000, 1000, y=10000), "stops": pts(0, 1000, 200, y=10200)},
    }
    res = _run_cfg(lines, agency, NO_CONTAINMENT)
    assert _row(res, "R1")["status"] == "matched"
    assert _row(res, "LRT11")["status"] == "ours_only"  # 200 m > route_tol_m: cov_ours 0
    # with containment the LRT stops (all on our nodes) still make it a contained route
    lrt = _row(_run(lines, agency), "LRT11")
    assert lrt["status"] == "agency_within_ours" and lrt["cov_ours"] == 0.0


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
    assert row["status"] == "ours_within_agency"  # its one node lies on the agency route
    off = _run_cfg({"LRT11": _lrt([(0, 0)])},
                   {"LRT:1": {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 200)}},
                   NO_CONTAINMENT)
    assert _row(off, "LRT11")["status"] == "weak"  # 2 * 1 * 1/6 / (1 + 1/6) = 0.286
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
    lines = {"LRT11": _lrt([(0, 0)])}
    agency = {"LRT:1": {"coords": pts(0, 8000, 8000), "stops": pts(0, 8000, 1000)}}
    assert _row(_run(lines, agency), "LRT11")["status"] == "ours_within_agency"
    res = _run_cfg(lines, agency, NO_CONTAINMENT)  # the score threshold alone
    assert list(res.pairs["agency_route_key"]) == ["LRT:1"]
    assert res.pairs.iloc[0]["score"] == 0.2
    row = _row(res, "LRT11")
    assert row["candidates"] == "LRT:1 (0.20)"
    assert row["status"] == "weak"


# ----------------------------------------------------------------------------------------
# Fix wave: split pair choice, empty lines, covered agency routes, containment
# ----------------------------------------------------------------------------------------

def test_split_merge_shows_a_contributing_pair_not_the_best_score():
    # LRT:1 covers all our nodes but few of its stops (1.0 / 0.25, score 0.4); LRT:2 and LRT:3
    # each share 3 of our 10 nodes and 3 of their 10 stops (0.3 / 0.3): those two make the split
    far = [(0, 500 + 100 * i) for i in range(7)]
    res = _run(
        {"LRT11": _lrt(pts(0, 900, 100))},
        {
            "LRT:1": {"coords": pts(0, 4600, 4600), "stops": pts(0, 4600, 200)},
            "LRT:2": {"coords": [(100, 0), (100, 1200)],
                      "stops": [(100, 0), (100, 50), (100, 100)] + [(100, y) for _, y in far]},
            "LRT:3": {"coords": [(700, 0), (700, 1200)],
                      "stops": [(700, 0), (700, 50), (700, 100)] + [(700, y) for _, y in far]},
        },
    )
    by_key = res.pairs.set_index("agency_route_key")
    assert by_key.loc["LRT:1", "cov_ours"] == pytest.approx(1.0)
    assert by_key.loc["LRT:1", "cov_agency"] == pytest.approx(0.25)
    assert by_key.loc["LRT:1", "score"] == pytest.approx(0.4)
    assert by_key.loc["LRT:2", "cov_ours"] == pytest.approx(0.3)
    assert by_key.loc["LRT:2", "cov_agency"] == pytest.approx(0.3)
    row = _row(res, "LRT11")
    assert row["status"] == "split_merge"
    assert row["reason"] == "runs over 2 agency routes"
    assert row["agency_route_key"] == "LRT:2"  # a route it runs over, not LRT:1
    assert row["cov_ours"] == pytest.approx(0.3) and row["cov_agency"] == pytest.approx(0.3)


def test_lines_without_a_usable_node_are_dropped_not_merged():
    nodes = make_network_nodes({
        "LRT11": _lrt(pts(0, 1000, 200)),
        "BAD1": _lrt([(5000, 0), (5100, 0)]),
        "BAD2": _lrt([(9000, 0)]),
    })
    nodes["x_itm"] = nodes["x_itm"].astype(object)
    nodes.loc[nodes["LINE_ID"].isin(["BAD1", "BAD2"]), "x_itm"] = "n/a"
    ours = build_our_routes(nodes, load_mode_map())
    assert list(ours["route_key"]) == ["LRT11"]
    assert ours.attrs["dropped_lines"] == 2
    assert ours.attrs["dropped_nodes"] == 3
    report = RunReport()
    match_routes(ours, make_agency_network({}), CFG, report)
    assert any("2 line(s) with no usable node" in e.message for e in report.warnings)


def test_agency_route_that_is_never_best_gets_a_covered_row():
    # R1 and R2 both match LRT:1 fully; LRT:2 (twice as long) is a good second candidate of
    # both but the best of neither: it is not agency_only, and it must not vanish
    res = _run(
        {"R1": _lrt(pts(0, 1000, 100)), "R2": _lrt(pts(50, 1050, 100))},
        {
            "LRT:1": {"coords": pts(0, 1050, 1050), "stops": pts(0, 1000, 100)},
            "LRT:2": {"coords": pts(0, 2000, 2000), "stops": pts(0, 2000, 100)},
        },
    )
    assert _row(res, "R1")["status"] == "matched" and _row(res, "R2")["status"] == "matched"
    assert _row(res, "R1")["agency_route_key"] == "LRT:1"
    covered = res.routes[res.routes["status"] == "covered"]
    assert list(covered["agency_route_key"]) == ["LRT:2"]
    row = covered.iloc[0]
    pair = res.pairs.set_index(["our_route_key", "agency_route_key"]).loc[("R2", "LRT:2")]
    assert pair["score"] >= CFG.match_min_score
    assert row["our_route_key"] == "R2"  # its best same-mode pair
    assert row["cov_ours"] == pytest.approx(pair["cov_ours"])
    assert row["cov_agency"] == pytest.approx(pair["cov_agency"])
    assert row["score"] == pytest.approx(pair["score"])
    assert row["reason"] == "candidate of 2 of our routes, never their best"
    assert "R1 (" in row["candidates"] and "R2 (" in row["candidates"]
    assert row["agency_type"] == "LRT" and row["agency_n_stops"] == 21
    assert not (res.routes["status"] == "agency_only").any()
    # every agency route has exactly one row that is its own (agency_only, covered or chosen)
    assert set(res.routes["agency_route_key"].dropna()) == {"LRT:1", "LRT:2"}


def test_short_route_of_ours_on_a_long_agency_route_is_ours_within_agency():
    lines = {"LRT11": _lrt(pts(0, 300, 100))}
    agency = {"LRT:1": {"coords": pts(0, 10000, 10000), "stops": pts(0, 10000, 200)}}
    res = _run(lines, agency)
    row = _row(res, "LRT11")
    assert row["cov_ours"] == pytest.approx(1.0)
    assert row["cov_agency"] == pytest.approx(3 / 51)
    assert row["score"] < CFG.only_max_score
    assert row["status"] == "ours_within_agency"
    assert row["agency_route_key"] == "LRT:1"
    assert not (res.routes["status"].isin(["agency_only", "covered"])).any()

    off = _run_cfg(lines, agency, NO_CONTAINMENT)
    assert _row(off, "LRT11")["status"] == "ours_only"
    assert list(off.routes.loc[off.routes["status"] == "agency_only", "agency_route_key"]) == [
        "LRT:1"]


def test_agency_rail_route_inside_a_long_route_of_ours_is_agency_within_ours():
    lines = {"R1": {"mode": "Suburban Rail", "coords": pts(0, 20000, 500)}}
    agency = {"Rail:0:A": {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 500)}}
    res = _run(lines, agency)
    row = _row(res, "R1")
    assert row["cov_agency"] == pytest.approx(1.0)
    assert row["cov_ours"] == pytest.approx(3 / 41)
    assert row["status"] == "agency_within_ours"
    assert row["agency_route_key"] == "Rail:0:A"
    assert not (res.routes["status"] == "agency_only").any()

    off = _run_cfg(lines, agency, NO_CONTAINMENT)
    assert _row(off, "R1")["status"] == "ours_only"
    assert (off.routes["status"] == "agency_only").sum() == 1


def test_ours_within_agency_shows_the_pair_with_the_highest_agency_coverage():
    lines = {"LRT11": _lrt(pts(0, 300, 100))}
    agency = {
        "LRT:1": {"coords": pts(0, 10000, 10000), "stops": pts(0, 10000, 200)},
        "LRT:2": {"coords": pts(0, 5000, 5000), "stops": pts(0, 5000, 200)},
    }
    row = _row(_run(lines, agency), "LRT11")
    assert row["status"] == "ours_within_agency"
    assert row["agency_route_key"] == "LRT:2"  # 3/26 of its stops beats 3/51


def test_containment_off_reproduces_the_previous_statuses():
    lines = {
        "M1": _lrt(pts(0, 1000, 200)),  # matched on LRT:1
        "P1": _lrt(pts(0, 1000, 200, y=3000)),  # partial on LRT:3
        "W1": _lrt(pts(0, 2000, 1000, y=6000) + pts(3000, 9000, 1000, y=11000)),  # weak
        "B1": {"mode": "BRT", "coords": pts(0, 1000, 200, y=20000)},  # mode_differs
        "S1": _lrt(pts(0, 300, 100, y=30000)),  # contained in LRT:6
        "C1": {"mode": "Cable Line", "coords": pts(0, 500, 250, y=40000)},  # no agency mode
    }
    agency = {
        "LRT:1": {"coords": pts(0, 1000, 1000), "stops": pts(0, 1000, 200)},
        "LRT:3": {"coords": pts(0, 2000, 2000, y=3000), "stops": pts(0, 2000, 200, y=3000)},
        "LRT:4": {"coords": pts(0, 9000, 9000, y=6000), "stops": pts(0, 9000, 1000, y=6000)},
        "LRT:5": {"coords": pts(0, 1000, 1000, y=20000), "stops": pts(0, 1000, 200, y=20000)},
        "LRT:6": {"coords": pts(0, 10000, 10000, y=30000),
                  "stops": pts(0, 10000, 200, y=30000)},
        "LRT:9": {"coords": pts(0, 1000, 1000, y=50000), "stops": pts(0, 1000, 200, y=50000)},
    }

    def statuses(res):
        r = res.routes
        return {(k if pd.notna(k) else a): s
                for k, a, s in zip(r["our_route_key"], r["agency_route_key"], r["status"])}

    off = _run_cfg(lines, agency, NO_CONTAINMENT)
    assert statuses(off) == {
        "M1": "matched", "P1": "partial", "W1": "weak", "B1": "mode_differs",
        "S1": "ours_only", "C1": "ours_only", "LRT:4": "agency_only", "LRT:5": "agency_only",
        "LRT:6": "agency_only", "LRT:9": "agency_only",
    }
    on = _run(lines, agency)
    expected_on = dict(statuses(off), S1="ours_within_agency")
    del expected_on["LRT:6"]
    assert statuses(on) == expected_on
    # every other row is identical, value for value
    keep_on = ~on.routes["our_route_key"].eq("S1")
    keep_off = ~(off.routes["our_route_key"].eq("S1") | off.routes["agency_route_key"].eq("LRT:6"))
    pd.testing.assert_frame_equal(on.routes[keep_on].reset_index(drop=True),
                                  off.routes[keep_off].reset_index(drop=True))
    # the pairs differ only by the containment candidate
    extra = on.pairs.merge(off.pairs, how="left", indicator=True)
    assert list(extra.loc[extra["_merge"] == "left_only", "our_route_key"]) == ["S1"]
