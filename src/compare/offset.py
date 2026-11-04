"""Estimate the systematic shift between pipeline node positions and agency station positions."""

from __future__ import annotations

import numpy as np

_CHUNK = 500  # rows of the pairwise distance matrix held in memory at once
MIN_PAIRS = 5  # fewest node-stop pairs that make a median shift worth trusting


def _nearest(points: np.ndarray, targets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Distance to, and index of, the nearest target for every point (chunked brute force)."""
    dist = np.empty(len(points))
    idx = np.empty(len(points), dtype=np.intp)
    for start in range(0, len(points), _CHUNK):
        block = points[start:start + _CHUNK]
        d2 = ((block[:, None, :] - targets[None, :, :]) ** 2).sum(axis=2)
        j = d2.argmin(axis=1)
        idx[start:start + _CHUNK] = j
        dist[start:start + _CHUNK] = np.sqrt(d2[np.arange(len(block)), j])
    return dist, idx


def estimate_shift(
    nodes_xy: np.ndarray,
    stops_xy: np.ndarray,
    tol_m: float,
    radius_m: float,
    passes: int,
    min_pairs: int = MIN_PAIRS,
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate the local offset between our nodes and the agency's stops.

    Each pass matches every node (moved by the current shift) to its nearest stop; pairs closer
    than ``tol_m`` are kept and their offset ``stop - node`` is taken against the raw node
    position. The shift of a node is the median offset of the matched pairs whose raw node lies
    within ``radius_m`` of it, or the global median when there are fewer than ``min_pairs`` of
    them. Iteration stops (keeping the last result) once fewer than ``min_pairs`` pairs match.

    Args:
        nodes_xy: Node coordinates in metres (ITM), shape ``(n, 2)``.
        stops_xy: Agency stop coordinates in metres, shape ``(m, 2)``.
        tol_m: Largest node-to-stop distance accepted as a pair.
        radius_m: Radius around a node within which pair offsets are pooled.
        passes: Number of refinement passes; ``0`` returns a zero shift.
        min_pairs: Fewest pairs needed to trust a median.

    Returns:
        ``(shift, global_shift)`` with shapes ``(n, 2)`` and ``(2,)``. The shift is *added* to
        the node coordinates (see :func:`apply_shift`); both are zero when nothing matches.
    """
    nodes = np.asarray(nodes_xy, dtype=float).reshape(-1, 2)
    stops = np.asarray(stops_xy, dtype=float).reshape(-1, 2)
    shift = np.zeros_like(nodes)
    glob = np.zeros(2)
    if len(nodes) == 0 or len(stops) == 0:
        return shift, glob

    for _ in range(passes):
        dist, idx = _nearest(nodes + shift, stops)
        matched = dist <= tol_m
        if matched.sum() < min_pairs:
            break
        raw = nodes[matched]
        off = stops[idx[matched]] - raw
        glob = np.median(off, axis=0)
        new = np.tile(glob, (len(nodes), 1))
        for start in range(0, len(nodes), _CHUNK):
            block = nodes[start:start + _CHUNK]
            d2 = ((block[:, None, :] - raw[None, :, :]) ** 2).sum(axis=2)
            near = d2 <= radius_m ** 2
            for k in np.flatnonzero(near.sum(axis=1) >= min_pairs):
                new[start + k] = np.median(off[near[k]], axis=0)
        shift = new
    return shift, glob


def count_pairs(nodes_xy: np.ndarray, stops_xy: np.ndarray, tol_m: float) -> int:
    """Number of nodes whose nearest stop is within ``tol_m`` (the first pass of
    :func:`estimate_shift`; fewer than its ``min_pairs`` means no shift is estimated)."""
    nodes = np.asarray(nodes_xy, dtype=float).reshape(-1, 2)
    stops = np.asarray(stops_xy, dtype=float).reshape(-1, 2)
    if len(nodes) == 0 or len(stops) == 0:
        return 0
    dist, _ = _nearest(nodes, stops)
    return int((dist <= tol_m).sum())


def apply_shift(nodes_xy: np.ndarray, shift: np.ndarray) -> np.ndarray:
    """Return the node coordinates moved by the estimated shift (``nodes_xy + shift``)."""
    return np.asarray(nodes_xy, dtype=float) + np.asarray(shift, dtype=float)
