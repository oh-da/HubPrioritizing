"""Mapping from the pipeline's mode names to the agency network's ``type`` values."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping

from ..config import REFERENCE_DATA_DIR

MODE_MAP_PATH = REFERENCE_DATA_DIR / "agency_mode_map.csv"


def load_mode_map(path: Path | None = None) -> dict[str, str | None]:
    """Read the mode map CSV (columns ``our_mode, agency_type, note``).

    Args:
        path: CSV to read; defaults to the shipped ``data/reference/agency_mode_map.csv``.

    Returns:
        Our mode -> agency type; ``None`` where the agency network has no counterpart
        (empty ``agency_type``).
    """
    path = MODE_MAP_PATH if path is None else Path(path)
    out: dict[str, str | None] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            our = (row.get("our_mode") or "").strip()
            if not our:
                continue
            agency = (row.get("agency_type") or "").strip()
            out[our] = agency or None
    return out


def map_mode(our_mode: str, mode_map: Mapping[str, str | None]) -> str | None:
    """Return the agency type of one of our modes, or ``None`` (no counterpart or unknown)."""
    return mode_map.get(our_mode)
