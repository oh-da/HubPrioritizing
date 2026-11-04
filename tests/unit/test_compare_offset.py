"""Tests for the node-to-agency offset estimation."""

from __future__ import annotations

import numpy as np

from src.compare.offset import apply_shift, estimate_shift


def _grid(nx: int, ny: int, step: float, origin=(0.0, 0.0)) -> np.ndarray:
    xs, ys = np.meshgrid(np.arange(nx) * step, np.arange(ny) * step)
    return np.column_stack([xs.ravel() + origin[0], ys.ravel() + origin[1]])


def test_recovers_constant_offset():
    rng = np.random.default_rng(7)
    nodes = _grid(15, 15, 600.0, (180000.0, 650000.0))
    offset = np.array([60.0, -37.0])
    noise = rng.uniform(-3.0, 3.0, size=nodes.shape)
    stops = nodes + offset + noise
    decoys = rng.uniform(-5000.0, 15000.0, size=(300, 2)) + np.array([180000.0, 650000.0])
    stops = np.vstack([stops, decoys])

    shift, glob = estimate_shift(nodes, stops, tol_m=120.0, radius_m=3000.0, passes=2)

    assert shift.shape == nodes.shape
    assert np.abs(shift - offset).max() < 3.0
    assert np.abs(glob - offset).max() < 3.0


def test_local_offsets_vary_by_region():
    a = _grid(8, 8, 500.0, (180000.0, 650000.0))
    b = _grid(8, 8, 500.0, (210000.0, 650000.0))
    off_a, off_b = np.array([50.0, 0.0]), np.array([-40.0, 30.0])
    nodes = np.vstack([a, b])
    stops = np.vstack([a + off_a, b + off_b])

    shift, glob = estimate_shift(nodes, stops, tol_m=100.0, radius_m=5000.0, passes=2)

    assert np.abs(shift[: len(a)] - off_a).max() < 1.0
    assert np.abs(shift[len(a):] - off_b).max() < 1.0
    assert not np.allclose(shift[0], shift[-1])


def test_fewer_pairs_than_min_returns_zero_shift():
    nodes = _grid(2, 2, 500.0)
    stops = nodes + np.array([20.0, 10.0])

    shift, glob = estimate_shift(nodes, stops, tol_m=100.0, radius_m=5000.0, passes=2, min_pairs=5)

    assert shift.shape == (4, 2)
    assert not shift.any()
    assert not glob.any()


def test_node_far_from_any_pair_gets_global_median():
    cluster = _grid(5, 5, 500.0, (180000.0, 650000.0))
    far = np.array([[200000.0, 650000.0]])
    nodes = np.vstack([cluster, far])
    offset = np.array([45.0, -20.0])
    # the far node has a stop 1 km away: not a pair within tol_m, so it is never matched
    stops = np.vstack([cluster + offset, far + np.array([1000.0, 0.0])])

    shift, glob = estimate_shift(nodes, stops, tol_m=100.0, radius_m=2000.0, passes=2)

    assert np.allclose(glob, offset)
    assert np.allclose(shift[-1], glob)
    assert np.allclose(shift[:-1], offset)


def test_empty_inputs():
    empty = np.zeros((0, 2))
    pts = _grid(3, 3, 100.0)

    shift, glob = estimate_shift(empty, pts, 100.0, 1000.0, 2)
    assert shift.shape == (0, 2) and glob.shape == (2,) and not glob.any()

    shift, glob = estimate_shift(pts, empty, 100.0, 1000.0, 2)
    assert shift.shape == (9, 2) and not shift.any() and not glob.any()


def test_passes_zero_returns_zero():
    nodes = _grid(6, 6, 500.0)
    stops = nodes + np.array([30.0, 30.0])

    shift, glob = estimate_shift(nodes, stops, 100.0, 5000.0, passes=0)

    assert shift.shape == nodes.shape
    assert not shift.any()
    assert not glob.any()


def test_apply_shift_adds_the_shift():
    nodes = np.array([[1.0, 2.0], [3.0, 4.0]])
    shift = np.array([[10.0, -1.0], [0.0, 5.0]])
    assert np.array_equal(apply_shift(nodes, shift), np.array([[11.0, 1.0], [3.0, 9.0]]))
