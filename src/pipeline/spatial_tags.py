"""
Part 2, step 2.3: tag hexagons with metropolitan area and position.

Ports cells 30 and 34 of ``COMPLETE_TRANSIT_PIPELINE.ipynb``:

- metro layer (``METRO_NAME`` -> ``area``, ``ZONE_NAME`` -> ``location``) by intersection
- districts layer (``MACHOZ`` -> ``area`` and ``location``) for hexagons outside a metro
- the notebook's exact-match name fixes (e.g. ``מחוז צפון`` -> ``צפון``) so that the
  ``area`` vocabulary matches the golden results
- :func:`get_regions_for_area`: area -> ordered candidate demand-model regions
"""

from __future__ import annotations

import re

import geopandas as gpd
import pandas as pd

from ..config import CRS_WGS84
from .report import RunReport

AREA_COL = "area"
LOCATION_COL = "location"
UNKNOWN = "Unknown"

METRO_NAME_CANDIDATES = ("METRO_NAME", "MetroName", "metro_name", "NAME", "name", "SHEM")
ZONE_NAME_CANDIDATES = ("ZONE_NAME", "ZoneName", "zone_name", "ZONE", "zone")
DISTRICT_NAME_CANDIDATES = ("MACHOZ", "SHEM_MACHOZ", "SHEM_NAFA", "District", "NAME", "SHEM")

# Exact-match repairs the notebook applied after tagging. Truncated forms are kept for
# robustness (inputs.read_shapefile already yields full names); the 'מחוז' entries change
# the area vocabulary and therefore matter for reproducing results.
HEBREW_NAME_FIXES = {
    "גלעי": "גלעין",
    "טבעת פנימי": "טבעת פנימית",
    "טבעת חיצוני": "טבעת חיצונית",
    "טבעת תיכונ": "טבעת תיכונה",
    "טבע": "טבעת",
    "תל אבי": "תל אביב",
    "מרכ": "מרכז",
    "צפו": "צפון",
    "דרו": "דרום",
    "חיפ": "חיפה",
    "ירושלי": "ירושלים",
    "באר שב": "באר שבע",
    "מחוז חיפה": "חיפה",
    "מחוז תל אביב": "תל אביב",
    "מחוז מרכז": "מרכז",
    "מחוז ירושלים": "ירושלים",
    "מחוז הדרום": "הדרום",
    "מחוז צפון": "צפון",
}

# Exact area -> demand-model region (fallback for get_regions_for_area)
AREA_TO_REGION = {
    "חיפה": "Haifa",
    "צפון": "Haifa",
    "תל אביב": "Tel Aviv",
    "תל-אביב": "Tel Aviv",
    "מרכז": "Tel Aviv",
    "באר שבע": "Beer Sheva",
    "דרום": "Beer Sheva",
    "ירושלים": "Jerusalem",
    "אשדוד": "Ashdod-Ashkelon",
    "אשקלון": "Ashdod-Ashkelon",
    "Haifa": "Haifa",
    "North": "Haifa",
    "Tel Aviv": "Tel Aviv",
    "Center": "Tel Aviv",
    "Beer Sheva": "Beer Sheva",
    "South": "Beer Sheva",
    "Jerusalem": "Jerusalem",
}


def fix_hebrew_name(text):
    """Apply :data:`HEBREW_NAME_FIXES` (exact match first, then whole-word replacement)."""
    if not isinstance(text, str) or not text:
        return text
    s = text.strip()
    if s in HEBREW_NAME_FIXES:
        return HEBREW_NAME_FIXES[s]
    for truncated, fixed in HEBREW_NAME_FIXES.items():
        pattern = r"\b" + re.escape(truncated) + r"\b"
        if re.search(pattern, s):
            s = re.sub(pattern, fixed, s)
    return s


def get_regions_for_area(area) -> list[str]:
    """Ordered candidate demand-model regions for a hub area (keyword containment).

    The Southern District is served by both the Beer Sheva and the Ashdod-Ashkelon
    models, so it yields two candidates; matching tries them in order per node.
    """
    if area is None or (isinstance(area, float) and pd.isna(area)):
        return []
    s = str(area).strip()
    out: list[str] = []

    def add(region: str) -> None:
        if region not in out:
            out.append(region)

    if any(k in s for k in ("חיפ", "Haifa", "צפון", "North")):
        add("Haifa")
    if any(k in s for k in ("תל אבי", "תל-אבי", "Tel Aviv", "TelAviv", "מרכז", "Center")):
        add("Tel Aviv")
    if any(k in s for k in ("ירושלי", "Jerusalem")):
        add("Jerusalem")
    if any(k in s for k in ("דרום", "South")):
        add("Beer Sheva")
        add("Ashdod-Ashkelon")
    if any(k in s for k in ("באר שב", "Beer Sheva", "BeerSheva")):
        add("Beer Sheva")
    if any(k in s for k in ("אשדוד", "Ashdod", "אשקלון", "Ashkelon")):
        add("Ashdod-Ashkelon")
    if not out and s in AREA_TO_REGION:
        add(AREA_TO_REGION[s])
    return out


def _first_present(columns, candidates) -> str | None:
    for c in candidates:
        if c in columns:
            return c
    return None


def tag_area_and_location(
    hexes: gpd.GeoDataFrame,
    metro: gpd.GeoDataFrame | None,
    districts: gpd.GeoDataFrame | None,
    report: RunReport | None = None,
) -> gpd.GeoDataFrame:
    """Add ``area`` (str) and ``location`` (list of str) to every hexagon.

    Metro polygons are joined by intersection (first match wins); hexagons still
    untagged fall back to the district they lie within, whose name is used for both
    columns. Remaining rows get ``'Unknown'`` / ``['Unknown']``.
    """
    out = hexes.copy().reset_index(drop=True)
    out[AREA_COL] = None
    out[LOCATION_COL] = None
    hubs_wgs = out[["geometry"]].to_crs(CRS_WGS84)

    if metro is not None and len(metro):
        metro_col = _first_present(metro.columns, METRO_NAME_CANDIDATES)
        zone_col = _first_present(metro.columns, ZONE_NAME_CANDIDATES)
        if metro_col is None:
            if report is not None:
                report.warn("spatial_tags", "metro layer has no recognised name column; skipped", columns=list(metro.columns))
        else:
            cols = [c for c in (metro_col, zone_col) if c]
            joined = gpd.sjoin(hubs_wgs, metro.to_crs(CRS_WGS84)[cols + ["geometry"]], how="left", predicate="intersects")
            joined = joined[~joined.index.duplicated(keep="first")]
            out[AREA_COL] = joined[metro_col].to_numpy()
            if zone_col:
                out[LOCATION_COL] = [[z] if pd.notna(z) else None for z in joined[zone_col].to_numpy()]
            if report is not None:
                report.info("spatial_tags", f"metro layer tagged {int(out[AREA_COL].notna().sum())} of {len(out)} hexagons")

    if districts is not None and len(districts):
        district_col = _first_present(districts.columns, DISTRICT_NAME_CANDIDATES)
        untagged = out[AREA_COL].isna()
        if district_col is None:
            if report is not None:
                report.warn("spatial_tags", "districts layer has no recognised name column; skipped", columns=list(districts.columns))
        elif untagged.any():
            joined = gpd.sjoin(
                hubs_wgs[untagged], districts.to_crs(CRS_WGS84)[[district_col, "geometry"]], how="left", predicate="within"
            )
            joined = joined[~joined.index.duplicated(keep="first")]
            for idx, val in zip(joined.index, joined[district_col]):
                if pd.notna(val):
                    out.at[idx, AREA_COL] = val
                    if out.at[idx, LOCATION_COL] is None:
                        out.at[idx, LOCATION_COL] = [val]
            if report is not None:
                report.info("spatial_tags", f"districts layer tagged {int(untagged.sum() - out.loc[untagged, AREA_COL].isna().sum())} of {int(untagged.sum())} remaining hexagons")

    out[AREA_COL] = out[AREA_COL].map(lambda v: fix_hebrew_name(v) if isinstance(v, str) else UNKNOWN)
    out[LOCATION_COL] = out[LOCATION_COL].map(
        lambda v: [fix_hebrew_name(x) if isinstance(x, str) else x for x in v] if isinstance(v, list) else [UNKNOWN]
    )

    n_unknown = int((out[AREA_COL] == UNKNOWN).sum())
    if report is not None:
        report.set_metric("hexes_without_area", n_unknown)
        if n_unknown:
            report.warn("spatial_tags", f"{n_unknown} hexagons fall outside every metro and district polygon")
    return out
