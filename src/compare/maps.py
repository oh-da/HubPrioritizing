"""Leaflet pages of ``hubs compare-network``: one for the routes, one for the hubs.

Each page is one self-contained HTML file in the design of the HubsScraping reference pages
(``compare_lines.html`` for the routes, ``compare.html`` for the hubs; the shared look is in
:mod:`src.compare.map_assets`). The layers of :func:`export.build_layers` are reprojected to
WGS84, reduced to GeoJSON features (coordinates rounded to six decimals, null attributes left
out) and embedded as a JSON block together with the display labels and the settings; Leaflet
1.9.4 comes from cdnjs. Every ``<`` of the JSON block is escaped, so a name cannot end the
block, and every data text reaches the markup through ``esc()``. The pages show plain words
only: the codes of the data are turned into labels through :data:`map_assets.LABELS`. The
output is a pure function of the layers and the settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import mapping

from .map_assets import (
    AGENCY_HE, BASE_CSS, BASEMAP_HTML, FONT_CSS, LABELS, LEAFLET_CSS, LEAFLET_JS, OURS_HE,
    basemap_js, plain_reason, safe_json, tokens_css,
)
from .settings import CompareConfig

__all__ = ["LEAFLET_CSS", "LEAFLET_JS", "write_hubs_map", "write_routes_map"]

COORD_DECIMALS = 6  # about 0.1 m
VALUE_DECIMALS = 4
ISRAEL_BOUNDS = [[29.4, 34.2], [33.4, 35.9]]  # [[south, west], [north, east]]
ROUTE_LAYERS = ("route_pairs", "our_routes")
HUB_LAYERS = ("agency_hubs", "our_groups", "hub_ties")
MIN_MODES = 2  # the reference page compares agency hubs with at least two modes
AG = f"<bdi>{AGENCY_HE}</bdi>"
OU = f"<bdi>{OURS_HE}</bdi>"


# ----------------------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------------------


def _value(value: Any) -> Any:
    """JSON-safe attribute: lists joined with ``"; "``, NaN / NA as ``None``, numpy as Python."""
    if isinstance(value, (list, tuple, set, frozenset, np.ndarray)):
        items = sorted(value, key=str) if isinstance(value, (set, frozenset)) else value
        return "; ".join(str(v) for v in items)
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return round(float(value), VALUE_DECIMALS) if np.isfinite(value) else None
    return str(value)


def _true(value: Any) -> bool:
    value = _value(value)
    return value is True or value == 1 or str(value).strip().lower() in ("true", "1", "1.0")


def _round(coords: Any) -> Any:
    if len(coords) and isinstance(coords[0], (int, float)):
        return [round(float(c), COORD_DECIMALS) for c in coords[:2]]
    return [_round(c) for c in coords]


def _feature(geom: Any, props: Mapping[str, Any], **members: Any) -> dict[str, Any]:
    """A GeoJSON feature; ``members`` are foreign members the page script reads."""
    geometry = None
    if geom is not None and not geom.is_empty:
        geometry = mapping(geom)
        geometry = {"type": geometry["type"], "coordinates": _round(geometry["coordinates"])}
    clean = {str(k): v for k, v in ((k, _value(v)) for k, v in props.items())
             if v is not None and v != ""}
    return {"type": "Feature", "geometry": geometry, "properties": clean, **members}


def _itm(layers: Mapping[str, gpd.GeoDataFrame], name: str) -> gpd.GeoDataFrame:
    """The layer ``name`` in EPSG:2039 (an empty frame when it is missing)."""
    layer = layers.get(name)
    if layer is None or len(layer) == 0:
        return gpd.GeoDataFrame({"_": []}, geometry=gpd.GeoSeries([], crs=2039), crs=2039)
    return layer.set_crs(2039) if layer.crs is None else layer.to_crs(2039)


def _rows(layer: gpd.GeoDataFrame) -> list[dict[str, Any]]:
    columns = [c for c in layer.columns if c != layer.geometry.name and c != "_"]
    return layer[columns].to_dict("records")


def _wgs(geoms: list) -> list:
    """ITM geometries -> WGS84 (``None`` stays ``None``)."""
    series = gpd.GeoSeries(geoms, crs=2039)
    return list(series.to_crs(4326)) if len(series) else []


def _collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def _settings(settings: Mapping[str, Any] | None) -> dict[str, Any]:
    out = CompareConfig().to_dict()
    out.update(settings or {})
    return {k: _value(v) for k, v in out.items()}


def _routes_data(layers: Mapping[str, gpd.GeoDataFrame]) -> dict[str, Any]:
    """``route_pairs`` and ``our_routes`` with the set(s) each feature is drawn in.

    Sets: ``routed`` (a ``matched`` row of ours, drawn on the agency geometry), ``diff`` and
    ``off`` (our routes, drawn through their nodes), ``used`` (one row per agency route that a
    route of ours uses, every status but ``agency_only``) and ``gap`` (``agency_only``).
    """
    pairs, ours = _itm(layers, "route_pairs"), _itm(layers, "our_routes")
    pair_rows, our_rows = _rows(pairs), _rows(ours)
    gaps = {r.get("agency_route_key") for r in pair_rows if r.get("status") == "agency_only"}
    used: set[Any] = set()
    features = []
    for geom, geom_wgs, row in zip(pairs.geometry, _wgs(list(pairs.geometry)), pair_rows):
        key, status = row.get("agency_route_key"), row.get("status")
        sets = []
        if status == "matched" and _value(row.get("our_route_key")) is not None:
            sets.append("routed")
        if status == "agency_only":
            sets.append("gap")
        elif key not in gaps and key not in used:
            sets.append("used")
            used.add(key)
        extra = {"length_m": None if geom is None else round(float(geom.length)),
                 "why": plain_reason(row.get("reason"))}
        features.append(_feature(geom_wgs, {**row, **extra}, sets=sets))
    our_features = []
    for geom_wgs, row in zip(_wgs(list(ours.geometry)), our_rows):
        status = _value(row.get("status")) or "ours_only"
        sets = ["off" if status == "ours_only" else "routed" if status == "matched" else "diff"]
        extra = {"status": status, "why": plain_reason(row.get("reason"))}
        our_features.append(_feature(geom_wgs, {**row, **extra}, sets=sets))
    return {"route_pairs": _collection(features), "our_routes": _collection(our_features)}


def _centroids(layer: gpd.GeoDataFrame) -> list:
    return [None if g is None or g.is_empty else g.centroid for g in layer.geometry]


def _nearest(src: list, dst: list, dst_ids: list) -> list[tuple[Any, float | None]]:
    """For each geometry of ``src``: the id of the closest of ``dst`` and the distance (m)."""
    out: list[tuple[Any, float | None]] = []
    ok = [i for i, g in enumerate(dst) if g is not None and not g.is_empty]
    arr = np.array([dst[i] for i in ok], dtype=object)
    for g in src:
        if g is None or g.is_empty or not len(ok):
            out.append((None, None))
            continue
        dist = shapely.distance(g, arr)
        j = int(np.argmin(dist))
        out.append((dst_ids[ok[j]], round(float(dist[j]))))
    return out


def _hubs_data(layers: Mapping[str, gpd.GeoDataFrame]) -> dict[str, Any]:
    """Hubs as centroid points with their set, the nearest hub of the other side and ties.

    Agency hubs with ``n_modes >= 2`` and our scored groups (``eligible``) are compared:
    ``both`` (a tie between the two), ``onlym`` / ``onlyx`` (no such tie). The others are the
    extra sets ``single`` (one-mode agency hubs) and ``filt`` (groups that are not scored).
    """
    a, g, t = _itm(layers, "agency_hubs"), _itm(layers, "our_groups"), _itm(layers, "hub_ties")
    a_rows, g_rows, t_rows = _rows(a), _rows(g), _rows(t)
    a_ids = [_value(r.get("agency_hub_id")) for r in a_rows]
    g_ids = [_value(r.get("group")) for r in g_rows]
    a_pt, g_pt = _centroids(a), _centroids(g)
    multi = {i for i, r, p in zip(a_ids, a_rows, a_pt)
             if p is not None and (_value(r.get("n_modes")) or 0) >= MIN_MODES}
    scored = {i for i, r, p in zip(g_ids, g_rows, g_pt)
              if p is not None and _true(r.get("eligible"))}
    both = [_value(r.get("agency_hub_id")) in multi and _value(r.get("group")) in scored
            for r in t_rows]
    a_both = {_value(r.get("agency_hub_id")) for r, b in zip(t_rows, both) if b}
    g_both = {_value(r.get("group")) for r, b in zip(t_rows, both) if b}

    a_multi_geom = [geo if i in multi else None for i, geo in zip(a_ids, a.geometry)]
    g_scored_geom = [geo if i in scored else None for i, geo in zip(g_ids, g.geometry)]
    a_near = _nearest([geo if i in multi and i not in a_both else None
                       for i, geo in zip(a_ids, a.geometry)], g_scored_geom, g_ids)
    g_near = _nearest([geo if i in scored and i not in g_both else None
                       for i, geo in zip(g_ids, g.geometry)], a_multi_geom, a_ids)

    def hub_set(i: Any, point: Any, compared: set, paired: set, single: str, alone: str):
        if point is None:
            return None
        if i not in compared:
            return single
        return "both" if i in paired else alone

    a_feats = [
        _feature(p, {**r, "near_group": n[0], "near_m": n[1]},
                 set=hub_set(i, p, multi, a_both, "single", "onlym"))
        for i, r, p, n in zip(a_ids, a_rows, _wgs(a_pt), a_near)
    ]
    g_feats = [
        _feature(p, {**r, "near_hub": n[0], "near_m": n[1]},
                 set=hub_set(i, p, scored, g_both, "filt", "onlyx"))
        for i, r, p, n in zip(g_ids, g_rows, _wgs(g_pt), g_near)
    ]
    t_feats = [_feature(None, r, both=b) for r, b in zip(t_rows, both)]
    return {"agency_hubs": _collection(a_feats), "our_groups": _collection(g_feats),
            "hub_ties": _collection(t_feats)}


# ----------------------------------------------------------------------------------------
# Page
# ----------------------------------------------------------------------------------------


def _render(title: str, aria: str, panel: str, data: Mapping[str, Any], page_js: str) -> str:
    html = _PAGE
    for key, value in {
        "__TITLE__": title, "__ARIA__": aria, "__FONT__": FONT_CSS,
        "__LEAFLET_CSS__": LEAFLET_CSS, "__LEAFLET_JS__": LEAFLET_JS,
        "__CSS__": tokens_css() + BASE_CSS, "__PANEL__": panel,
        "__SCRIPT__": basemap_js() + _COMMON_JS + page_js + "})();",
    }.items():
        html = html.replace(key, value)
    html = html.replace("__BOUNDS__", safe_json(ISRAEL_BOUNDS))
    return html.replace("__DATA__", safe_json(data))  # last: data text is never substituted


def _write(path: Path, html: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(html.encode("utf-8", "replace"))
    return path


def _m(value: Any) -> str:
    return f"{float(value):g} m"


def _set_row(set_id: str, svg: str, label: str, small: str, checked: bool = True) -> str:
    state = " checked" if checked else ""
    return (f'    <li><label><input type="checkbox" id="set-{set_id}"{state}>\n'
            f'      <svg class="sym" viewBox="0 0 22 16" aria-hidden="true">{svg}</svg>\n'
            f'      <span class="lbl">{label}<small>{small}</small></span>'
            f'<span class="cnt" id="cnt-{set_id}"></span></label></li>\n')


def _actions() -> str:
    return ('  <div class="actions">\n'
            '    <button type="button" id="btn-fit">Zoom to all</button>\n'
            '    <button type="button" id="btn-tlv">Tel Aviv</button>\n'
            '    <button type="button" id="btn-hfa">Haifa</button>\n'
            '    <button type="button" id="btn-jlm">Jerusalem</button>\n'
            '    <button type="button" id="btn-bsh">Be\'er Sheva</button>\n'
            '  </div>\n')


def _offset_text(s: Mapping[str, Any]) -> str:
    if not s.get("apply_offset", True):
        return "our stops are not shifted"
    dx, dy = s.get("offset_dx_m"), s.get("offset_dy_m")
    if dx is None or dy is None:
        return "our stops shifted by a local offset"
    return f"our stops shifted by a local offset (overall {dx:.0f} m, {dy:.0f} m)"


def _routes_panel(data: Mapping[str, Any], s: Mapping[str, Any]) -> str:
    pairs = data["route_pairs"]["features"]
    n_ours = len(data["our_routes"]["features"])
    n_agency = len({f["properties"].get("agency_route_key") for f in pairs})
    sub = (f"{n_ours} Hubs project lines ({OU}) compared with {n_agency} lines of {AG} · "
           f"a stop is on a line within {_m(s['route_tol_m'])} (rail {_m(s['rail_tol_m'])}) · "
           f"{_offset_text(s)}")
    wave = '<path d="M1 12 C 6 2, 12 14, 21 4" fill="none" stroke="var(--routed)" stroke-width="3"/>'
    dash = '<line x1="1" y1="8" x2="21" y2="8" stroke="var({})" stroke-width="3" stroke-dasharray="4 3"/>'
    solid = '<line x1="1" y1="8" x2="21" y2="8" stroke="var({})" stroke-width="{}"/>'
    return (
        f'  <h1>Hubs project vs {AG}: transit lines</h1>\n'
        f'  <p class="sub">{sub}</p>\n'
        '  <p class="eyebrow">Hubs project lines</p>\n  <ul class="sets">\n'
        + _set_row("routed", wave, "Same line", f"follows a line of {AG}; drawn on their line")
        + _set_row("diff", dash.format("--diff"), "Lines that differ",
                   "partly the same, split or joined, part of a longer line, other mode or "
                   "barely overlaps")
        + _set_row("off", dash.format("--off"), "Only in Hubs project",
                   f"no line of {AG} here")
        + f'  </ul>\n  <p class="eyebrow">{AG} lines</p>\n  <ul class="sets">\n'
        + _set_row("used", solid.format("--used", 2), f"{AG} lines in use",
                   "a line of ours follows it")
        + _set_row("gap", solid.format("--gap", 3.5), f"{AG} lines without a line of ours",
                   "no line of ours follows it")
        + '  </ul>\n  <p class="eyebrow">Find a Hubs project line</p>\n'
        '  <div class="pick">\n'
        '    <select id="pick-line" aria-label="Hubs project line"><option value="">all lines</option></select>\n'
        '    <select id="pick-status" aria-label="Line status"><option value="">any status</option></select>\n'
        '  </div>\n'
        + _actions() + "  " + BASEMAP_HTML + "\n"
        '  <p class="note">Our lines are drawn through their stops in order; the project has '
        'no drawn routes, so their shape is approximate.</p>\n'
        '  <p class="note">Lines are compared by location only, not by name.</p>\n'
    )


def _hubs_panel(data: Mapping[str, Any], s: Mapping[str, Any]) -> str:
    n_a = sum(1 for f in data["agency_hubs"]["features"] if f["set"] in ("both", "onlym"))
    n_g = sum(1 for f in data["our_groups"]["features"] if f["set"] in ("both", "onlyx"))
    tol = _m(s["hub_match_tol_m"])
    ring = '<circle cx="11" cy="8" r="{r}" fill="{fill}" stroke="var({c})" stroke-width="{w}"{d}/>'
    both = ('<line x1="6" y1="8" x2="16" y2="8" stroke="var(--tie)" stroke-width="1.5"/>'
            '<circle cx="6" cy="8" r="6" fill="var(--both)" stroke="var(--ring)" stroke-width="1.5"/>'
            '<circle cx="16" cy="8" r="6" fill="none" stroke="var(--both)" stroke-width="2.2"/>')
    return (
        '  <h1>Hub list comparison</h1>\n'
        f'  <p class="sub">{n_a} {AG} hubs (2 or more modes) vs {n_g} {OU} hubs · '
        f'matched within {tol}</p>\n'
        '  <p class="eyebrow">Sets</p>\n  <ul class="sets">\n'
        + _set_row("both", both, "In both", f"filled = {AG} · ring = {OU} · line = offset")
        + _set_row("onlyx", ring.format(r=6.5, fill="none", c="--onlyx", w=2.4, d=""),
                   "Only in Hubs project", f"no {AG} hub within {tol}")
        + _set_row("onlym", ring.format(r=6.5, fill="var(--onlym)", c="--ring", w=1.5, d=""),
                   f"Only in {AG}", f"no Hubs project hub within {tol}")
        + '  </ul>\n  <p class="eyebrow">More (off at start)</p>\n  <ul class="sets">\n'
        + _set_row("single", ring.format(r=4.5, fill="var(--onlym)", c="--ring", w=1,
                                         d=' fill-opacity=".4"'),
                   f"{AG} hubs with one mode", "changes within one mode; not compared",
                   checked=False)
        + _set_row("filt", ring.format(r=5, fill="none", c="--onlyx", w=1.6,
                                       d=' stroke-dasharray="3 2"'),
                   "Hubs project groups not scored", "left out by the hub rules; not compared",
                   checked=False)
        + '  </ul>\n'
        + _actions() + "  " + BASEMAP_HTML + "\n"
        f'  <p class="note">Hubs are matched by location only: a stop of {AG} within {tol} of '
        'a stop of ours, after shifting our stops by the local offset.</p>\n'
        f'  <p class="note">Passenger numbers of {AG} are not available; the type shown for '
        'their hubs is worked out from their modes.</p>\n'
        '  <p class="note">Hubs project hubs marked “not a hub” (fewer than 3 lines) are '
        'included.</p>\n'
    )


def write_routes_map(path: Path, layers: Mapping[str, gpd.GeoDataFrame],
                     settings: Mapping[str, Any] | None = None) -> Path:
    """Write the route comparison page (the design of ``compare_lines.html``).

    Args:
        path: Output ``.html``.
        layers: :func:`export.build_layers` output (``route_pairs`` and ``our_routes`` are
            used; a missing layer is treated as empty).
        settings: The comparison settings (``CompareConfig.to_dict()``, optionally with
            ``offset_dx_m`` / ``offset_dy_m``); the defaults when omitted.

    Returns:
        ``path``. Sets: our routes with the same line (drawn on the agency line), routes that
        differ and routes only on our side (drawn through their nodes, dashed), agency routes
        in use (grey) and agency routes no route of ours uses (purple); a line picker, a status
        picker, city buttons and a basemap select with an automatic fallback.
    """
    s = _settings(settings)
    data = {"labels": LABELS, "settings": s, **_routes_data(layers)}
    return _write(path, _render(
        "Hubs project lines compared", f"Map comparing the transit lines of the Hubs project "
        f"with the lines of {AGENCY_HE}", _routes_panel(data, s), data, _ROUTES_JS,
    ))


def write_hubs_map(path: Path, layers: Mapping[str, gpd.GeoDataFrame],
                   settings: Mapping[str, Any] | None = None) -> Path:
    """Write the hub comparison page (the design of ``compare.html``).

    Args:
        path: Output ``.html``.
        layers: :func:`export.build_layers` output (``agency_hubs``, ``our_groups`` and
            ``hub_ties`` are used; a missing layer is treated as empty).
        settings: As for :func:`write_routes_map` (``hub_match_tol_m`` is quoted).

    Returns:
        ``path``. Sets: in both (agency hubs with two or more modes tied to our scored hubs),
        only ours, only the agency's, and, off at start, the one-mode agency hubs and our groups
        that are not scored.
    """
    s = _settings(settings)
    data = {"labels": LABELS, "settings": s, **_hubs_data(layers)}
    return _write(path, _render(
        "Hub List Comparison", f"Map comparing the hubs of {AGENCY_HE} with {OURS_HE}",
        _hubs_panel(data, s), data, _HUBS_JS,
    ))


# ----------------------------------------------------------------------------------------
# Templates
# ----------------------------------------------------------------------------------------

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__TITLE__</title>
<link rel="stylesheet" href="__FONT__">
<link rel="stylesheet" href="__LEAFLET_CSS__">
<style>
__CSS__</style>
</head>
<body>
<div id="map" role="application" aria-label="__ARIA__"></div>

<section class="panel" id="panel" aria-label="Sets and legend">
__PANEL__</section>

<script type="application/json" id="page-data">__DATA__</script>
<script src="__LEAFLET_JS__"></script>
<script>
__SCRIPT__</script>

</body>
</html>
"""

# Shared by both pages: the script opens an IIFE here and the page JS closes it.
_COMMON_JS = r"""
(function () {
  'use strict';
  const DATA = JSON.parse(document.getElementById('page-data').textContent);
  const LAB = DATA.labels, S = DATA.settings;
  const $ = id => document.getElementById(id);
  const NAMES = /מנהל התכנון|פרויקט תעדוף מתחמים/g;
  const esc = t => String(t ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const escB = t => esc(t).replace(NAMES, m => '<bdi>' + m + '</bdi>');
  const bdi = t => '<bdi>' + esc(t) + '</bdi>';
  const has = v => v != null && v !== '';
  const fmt = v => has(v) ? Number(v).toLocaleString('en', {maximumFractionDigits: 0}) : '–';
  const pct = v => has(v) ? Math.round(Number(v) * 100) + ' %' : '';
  const lab = (kind, code) => { const e = (LAB[kind] || {})[code]; return e ? e[0] : String(code ?? ''); };
  const expl = (kind, code) => { const e = (LAB[kind] || {})[code]; return e ? e[1] : ''; };
  const kv = rows => '<dl class="kv">' + rows.filter(r => has(r[1])).map(r => '<dt>' + escB(r[0]) + '</dt><dd>' + r[1] + '</dd>').join('') + '</dl>';
  const list = t => String(t ?? '').split(';').map(x => x.trim()).filter(Boolean);
  const panel = $('panel');
  if (typeof L === 'undefined') {
    $('basemap-note').textContent = 'The map could not be drawn: Leaflet did not load from cdnjs (offline?).';
    return;
  }
  const css = getComputedStyle(document.documentElement), tok = n => css.getPropertyValue(n).trim();
  const map = L.map('map', {zoomControl: false, preferCanvas: true});
  L.control.zoom({position: 'topright'}).addTo(map);
  map.attributionControl.setPrefix('');
  const ISRAEL = __BOUNDS__;
  map.fitBounds(ISRAEL);
  const basemap = hubsBasemap(map, $('basemap'), $('basemap-note'));
  const wire = (id, layer) => $(id).addEventListener('change', e => e.target.checked ? layer.addTo(map) : map.removeLayer(layer));
  const sw = c => [c[1], c[0]];
  function path(g) {  // a GeoJSON line -> Leaflet latlngs (null for anything else)
    if (!g) return null;
    if (g.type === 'LineString') return g.coordinates.map(sw);
    if (g.type === 'MultiLineString') return g.coordinates.map(l => l.map(sw));
    return null;
  }
  const pointOf = g => g && g.type === 'Point' ? sw(g.coordinates) : null;
  const bounds = L.latLngBounds([]);
  const extend = l => bounds.extend(l.getLatLng ? l.getLatLng() : l.getBounds());
  const fitAll = () => bounds.isValid() ? map.fitBounds(bounds, {padding: [30, 30]}) : map.fitBounds(ISRAEL);
  function cities() {
    $('btn-fit').addEventListener('click', fitAll);
    [['btn-tlv', [32.08, 34.82]], ['btn-hfa', [32.80, 35.02]], ['btn-jlm', [31.78, 35.21]],
     ['btn-bsh', [31.25, 34.79]]].forEach(c => $(c[0]).addEventListener('click', () => map.setView(c[1], 12)));
    L.DomEvent.disableClickPropagation(panel);
    L.DomEvent.disableScrollPropagation(panel);
  }
"""

_ROUTES_JS = r"""
  const OUR_ST = ['matched', 'partial', 'split_merge', 'ours_within_agency', 'agency_within_ours', 'mode_differs', 'weak', 'ours_only'];
  const ST_CLS = {matched: 'st-match', partial: 'st-partial', split_merge: 'st-partial', ours_within_agency: 'st-partial',
    agency_within_ours: 'st-partial', covered: 'st-partial', mode_differs: 'st-missing', weak: 'st-missing', ours_only: 'st-missing', agency_only: 'st-missing'};
  const covCls = v => v >= S.full_cov ? 'st-match' : v >= S.multi_cov ? 'st-partial' : 'st-missing';
  const groups = {}, counts = {};
  ['used', 'gap', 'routed', 'diff', 'off'].forEach(k => { groups[k] = L.layerGroup().addTo(map); counts[k] = 0; });
  const PAIRS = DATA.route_pairs.features, OURS = DATA.our_routes.features;
  const pairOf = {}, onLine = {}, REC = {};
  PAIRS.forEach(f => {
    const q = f.properties;
    if (q.our_route_key == null || q.status === 'agency_only') return;
    if (q.status !== 'covered') pairOf[q.our_route_key] = q;
    (onLine[q.agency_route_key] = onLine[q.agency_route_key] || []).push(q);
  });
  OURS.forEach(f => {
    const p = f.properties;
    REC[p.route_key] = {p: p, q: pairOf[p.route_key] || {}, status: p.status, f: f, layers: []};
  });
  const lineName = r => list(r.p.line_ids || r.q.our_line_ids || r.p.route_key || r.q.our_route_key).join(' / ');
  const years = q => has(q.year_operation) ? (has(q.year_cancel) ? q.year_operation + ' to ' + q.year_cancel : 'from ' + q.year_operation) : '';
  const theirs = q => [
    ['line of מנהל התכנון', has(q.agency_route_key) ? bdi(q.agency_route_key) + (has(q.agency_name) ? ' · ' + bdi(q.agency_name) : '') + (has(q.agency_line_name) ? ' · ' + bdi(q.agency_line_name) : '') : ''],
    ['its mode', esc(q.agency_type)], ['its stops', has(q.agency_n_stops) ? fmt(q.agency_n_stops) : ''],
    ['years', esc(years(q))], ['plan', has(q.source_plan) ? bdi(q.source_plan) : '']];
  const pick = (r, k) => has(r.q[k]) ? r.q[k] : r.p[k];
  function linePopup(key) {
    const r = REC[key], p = r.p, q = r.q, st = r.status;
    const cov = pick(r, 'cov_ours'), share = pick(r, 'cov_agency'), score = pick(r, 'score'), dist = pick(r, 'median_dist_corr_m');
    const names = list(p.line_names || q.our_line_names).join(' / ');
    const mode = p.mode || q.our_mode || '', other = p.agency_type || q.agency_type;
    const far = has(dist) ? fmt(dist) + ' m' + (has(q.median_dist_raw_m) ? ' (' + fmt(q.median_dist_raw_m) + ' m before the shift)' : '')
      + (has(q.max_dist_corr_m) ? ' · at most ' + fmt(q.max_dist_corr_m) + ' m' : '') : '';
    return `<div class="pp" dir="auto"><span class="st ${ST_CLS[st] || 'st-missing'}">${escB(lab('route_status', st))}</span>${has(cov) ? ` <span class="st ${covCls(cov)}">overlap ${pct(cov)}</span>` : ''}
      <h2 style="margin-top:6px">${bdi(lineName(r))}</h2><p class="expl">${escB(expl('route_status', st))}</p>`
      + kv([['names', names ? bdi(names) : ''], ['mode', esc(mode) + (other && other !== mode ? ' ' + escB('(' + other + ' at מנהל התכנון)') : '')],
        ['stops', fmt(p.n_nodes ?? q.our_n_nodes)], ['share of our line on theirs', pct(cov)], ['share of their line on ours', pct(share)],
        ['overlap score', has(score) ? Number(score).toFixed(2) : ''], ...(has(q.agency_route_key) ? theirs(q) : []),
        ['typical distance', far], ['other close lines', esc(pick(r, 'candidates'))], ['why', escB(pick(r, 'why'))]])
      + `<button type="button" data-zoom="${esc(key)}">Zoom to line</button></div>`;
  }
  function addLine(l, set, key) {
    const r = REC[key];
    l.bindPopup(() => linePopup(key), {maxWidth: 360});
    l.bindTooltip(bdi(lineName(r)) + ' · ' + esc(r.p.mode || r.q.our_mode) + ' · ' + escB(lab('route_status', r.status)), {sticky: true});
    l._kind = set; l._op = set === 'routed' ? .8 : .9;
    groups[set].addLayer(l); r.layers.push(l); counts[set]++; extend(l);
  }
  function theirPopup(q, gap) {
    const ours = (onLine[q.agency_route_key] || []).map(o => bdi(o.our_route_key) + ' (' + escB(lab('route_status', o.status)) + ')');
    const tag = gap ? `<span class="tag" style="background:var(--gap)">${escB(lab('route_status', 'agency_only'))}</span>`
      : `<span class="tag" style="background:var(--used)">${escB('מנהל התכנון line in use')}</span>`;
    return `<div class="pp" dir="auto">${tag}<h2>${bdi(q.agency_name || q.agency_route_key)}</h2>${gap ? `<p class="expl">${escB(expl('route_status', 'agency_only'))}</p>` : ''}`
      + kv([...theirs(q), ['length', has(q.length_m) ? fmt(q.length_m) + ' m' : ''], ['lines of ours on it', ours.join(', ')],
        ['close lines of ours', gap ? esc(q.candidates) : ''], ['why', gap ? escB(q.why) : '']]) + '</div>';
  }
  PAIRS.forEach(f => {
    const q = f.properties, pts = path(f.geometry), sets = f.sets || [];
    if (!pts) return;
    if (sets.includes('used')) {
      const l = L.polyline(pts, {color: tok('--used'), weight: 2, opacity: .7});
      l.bindPopup(() => theirPopup(q, false), {maxWidth: 340});
      l.bindTooltip(bdi(q.agency_name || q.agency_route_key) + ' · ' + esc(q.agency_type) + ' · ' + escB('מנהל התכנון line in use'), {sticky: true});
      groups.used.addLayer(l); counts.used++; extend(l);
    }
    if (sets.includes('gap')) {
      const l = L.polyline(pts, {color: tok('--gap'), weight: 4, opacity: .85});
      l.bindPopup(() => theirPopup(q, true), {maxWidth: 340});
      l.bindTooltip(bdi(q.agency_name || q.agency_route_key) + ' · ' + esc(q.agency_type) + ' · ' + fmt(q.length_m) + ' m, no line of ours follows it', {sticky: true});
      groups.gap.addLayer(l); counts.gap++; extend(l);
    }
  });
  PAIRS.forEach(f => {
    const q = f.properties, pts = path(f.geometry);
    if (!pts || !(f.sets || []).includes('routed')) return;
    const key = q.our_route_key;
    if (!REC[key]) REC[key] = {p: {}, q: q, status: 'matched', layers: []};
    REC[key].q = q;
    addLine(L.polyline(pts, {color: tok('--routed'), weight: 3.5, opacity: .8}), 'routed', key);
  });
  OURS.forEach(f => {
    const set = (f.sets || [])[0], key = f.properties.route_key;
    if (set !== 'diff' && set !== 'off') return;
    const style = {color: tok(set === 'off' ? '--off' : '--diff'), weight: 3, opacity: .9, dashArray: '6 5'};
    const pts = path(f.geometry), pt = pointOf(f.geometry);
    if (pts) addLine(L.polyline(pts, style), set, key);
    else if (pt) addLine(L.circleMarker(pt, Object.assign({}, style, {radius: 5, fillOpacity: 0, dashArray: '3 3'})), set, key);
  });
  Object.keys(groups).forEach(k => { $('cnt-' + k).textContent = counts[k]; wire('set-' + k, groups[k]); });

  const sel = $('pick-line'), selSt = $('pick-status'), byStatus = {};
  Object.keys(REC).sort().forEach(key => {
    const r = REC[key];
    if (!r.layers.length) return;
    const o = document.createElement('option');
    o.value = key; o.textContent = lineName(r) + ' · ' + (r.p.mode || r.q.our_mode || '') + ' · ' + lab('route_status', r.status);
    sel.appendChild(o);
    (byStatus[r.status] = byStatus[r.status] || []).push(key);
  });
  OUR_ST.filter(s => byStatus[s]).forEach(s => {
    const o = document.createElement('option'); o.value = s; o.textContent = lab('route_status', s); selSt.appendChild(o);
  });
  function showRoutes(keys) {
    const all = keys == null, set = new Set(keys || []);
    Object.keys(REC).forEach(key => REC[key].layers.forEach(l => {
      const on = all || set.has(key);
      l.setStyle({opacity: on ? l._op : .08});
      if (on) l.bringToFront();
    }));
  }
  function zoomTo(key) {
    const b = L.latLngBounds([]);
    (REC[key] ? REC[key].layers : []).forEach(l => b.extend(l.getLatLng ? l.getLatLng() : l.getBounds()));
    if (b.isValid()) map.fitBounds(b, {padding: [40, 40], maxZoom: 15});
  }
  sel.addEventListener('change', () => { selSt.value = ''; if (sel.value) { showRoutes([sel.value]); zoomTo(sel.value); } else showRoutes(null); });
  selSt.addEventListener('change', () => { sel.value = ''; showRoutes(selSt.value ? (byStatus[selSt.value] || []) : null); });
  map.on('popupopen', e => {
    const b = e.popup.getElement() && e.popup.getElement().querySelector('button[data-zoom]');
    if (b) b.addEventListener('click', () => { sel.value = b.dataset.zoom; selSt.value = ''; showRoutes([b.dataset.zoom]); zoomTo(b.dataset.zoom); });
  });
  cities();
  fitAll();
  window.hubsPage = {map: map, groups: groups, counts: counts, basemap: basemap};
"""

_HUBS_JS = r"""
  const R = 12;
  const groups = {}, counts = {};
  ['both', 'onlyx', 'onlym', 'single', 'filt'].forEach(k => { groups[k] = L.layerGroup(); counts[k] = 0; });
  const A = {}, G = {}, pairsA = {}, pairsG = {}, tiesA = {}, tiesG = {};
  DATA.agency_hubs.features.forEach(f => { const ll = pointOf(f.geometry); if (ll && f.set) A[f.properties.agency_hub_id] = {p: f.properties, ll: ll, set: f.set}; });
  DATA.our_groups.features.forEach(f => { const ll = pointOf(f.geometry); if (ll && f.set) G[f.properties.group] = {p: f.properties, ll: ll, set: f.set}; });
  const push = (o, k, v) => { (o[k] = o[k] || []).push(v); };
  DATA.hub_ties.features.forEach(f => {
    const t = f.properties;
    if (!A[t.agency_hub_id] || !G[t.group]) return;
    push(tiesA, t.agency_hub_id, t); push(tiesG, t.group, t);
    if (f.both) { push(pairsA, t.agency_hub_id, t); push(pairsG, t.group, t); }
  });
  const aName = p => p.name || 'hub ' + p.agency_hub_id;
  const gName = p => p.HubNameHE || p.hub_id || 'group ' + p.group;
  const modes = t => list(t).join(' | ');
  const tier = p => has(p.HubType) ? escB(lab('hub_type', p.HubType)) : '';
  const why = p => list(p.exclusion_reason).map(x => escB(lab('exclusion', x))).join(', ');
  const ourLine = p => [has(p.n_modes) ? fmt(p.n_modes) + ' modes' : '', has(p.Rank_TS_MC) ? 'rank ' + fmt(p.Rank_TS_MC) : '', tier(p)].filter(Boolean).join(' · ');
  const near = (name, m) => has(name) ? bdi(name) + ' · ' + fmt(m) + ' m' : '';
  function pairBlock(t) {
    const a = A[t.agency_hub_id].p, g = G[t.group].p;
    const agree = !has(t.modes_only_agency) && !has(t.modes_only_ours);
    return `<div class="two"><div class="col"><h3><bdi>מנהל התכנון</bdi> · hub ${esc(a.agency_hub_id)}</h3><div class="nm">${bdi(aName(a))}</div><div>${esc(modes(a.modes))}</div><div>${fmt(a.n_modes)} modes</div></div>
      <div class="col"><h3><bdi>פרויקט תעדוף מתחמים</bdi> · group ${esc(g.group)}</h3><div class="nm">${bdi(gName(g))}</div><div>${esc(modes(g.Mode_Planned))}</div><div>${ourLine(g)}</div>${has(g.TotalDemand) ? `<div>${fmt(g.TotalDemand)} passengers a day</div>` : ''}</div></div>
      <div style="margin-top:6px">${agree ? '<span class="same">modes agree</span>' : '<span class="diff">modes differ</span>'} · ${fmt(t.distance_m)} m apart · ${escB(lab('hub_relation', t.relation))}</div>`
      + kv([['lines at both', esc(list(t.routes_shared).map(x => x.replace('=', ' = ')).join(', '))], ['lines only at מנהל התכנון', esc(list(t.routes_only_agency).join(', '))],
        ['lines only in ours', esc(list(t.routes_only_ours).join(', '))]]);
  }
  function bothPopup(ties) {
    const head = ties.length === 1 ? 'In both · ' + fmt(ties[0].distance_m) + ' m apart' : 'In both · ' + ties.length + ' pairs';
    return `<div class="pp" dir="auto"><span class="tag" style="background:var(--both)">${head}</span>${ties.map(pairBlock).join('')}</div>`;
  }
  const others = (ts, side) => ts.map(t => side === 'a' ? bdi(gName(G[t.group].p)) + ' (' + (G[t.group].set === 'filt' ? 'not scored' : 'scored') + ')'
    : bdi(aName(A[t.agency_hub_id].p)) + ' (' + fmt(A[t.agency_hub_id].p.n_modes) + ' mode' + (A[t.agency_hub_id].p.n_modes > 1 ? 's' : '') + ')').join(', ');
  function ourPopup(r, tag, color) {
    const p = r.p, nh = A[p.near_hub];
    return `<div class="pp" dir="auto"><span class="tag" style="background:var(${color})">${escB(tag)}</span><h2>${bdi(gName(p))}</h2>`
      + kv([['hub', esc(p.hub_id) + ' · group ' + esc(p.group)], ['modes', esc(modes(p.Mode_Planned))], ['number of modes', fmt(p.n_modes)],
        ['lines', has(p.n_lines) ? fmt(p.n_lines) : ''], ['hub type', tier(p)], ['rank', has(p.Rank_TS_MC) ? fmt(p.Rank_TS_MC) : ''],
        ['rank in its type and area', has(p.RankByHubTypeMetro) ? fmt(p.RankByHubTypeMetro) : ''],
        ['passengers a day', has(p.TotalDemand) ? fmt(p.TotalDemand) : ''], ['why not scored', r.set === 'filt' ? why(p) : ''],
        ['nearest hub of מנהל התכנון (2 or more modes)', nh ? near(aName(nh.p), p.near_m) : ''],
        [`hubs of מנהל התכנון within ${fmt(S.hub_match_tol_m)} m`, others(tiesG[p.group] || [], 'g')],
        ['match', has(p.relation) && r.set === 'filt' ? escB(lab('hub_relation', p.relation)) : '']]) + '</div>';
  }
  function theirPopup(r, tag, color) {
    const p = r.p, ng = G[p.near_group], ts = tiesA[p.agency_hub_id] || [];
    const status = r.set === 'onlym' ? (ts.length ? 'near Hubs project groups that are not scored' : `no Hubs project group within ${fmt(S.hub_match_tol_m)} m`) : '';
    return `<div class="pp" dir="auto"><span class="tag" style="background:var(${color})">${escB(tag)}</span><h2>${bdi(aName(p))}</h2>`
      + kv([['hub', esc(p.agency_hub_id)], ['modes', esc(modes(p.modes))], ['number of modes', fmt(p.n_modes)], ['type', esc(p.agency_type)],
        ['lines', has(p.n_routes) ? fmt(p.n_routes) : ''], ['status', esc(status)],
        [`Hubs project groups within ${fmt(S.hub_match_tol_m)} m`, others(ts, 'a')],
        ['nearest Hubs project hub', ng ? near(gName(ng.p), p.near_m) : ''],
        ['match', r.set === 'single' && has(p.relation) ? escB(lab('hub_relation', p.relation)) : '']]) + '</div>';
  }
  const tip = r => ({direction: 'top', offset: [0, -r]});
  // in both: ties, then rings (Hubs project), then filled circles (מנהל התכנון)
  Object.keys(pairsA).sort((x, y) => x - y).forEach(id => pairsA[id].forEach(t => {
    groups.both.addLayer(L.polyline([A[id].ll, G[t.group].ll], {color: tok('--tie'), weight: 1.5, opacity: .9, interactive: false}));
    counts.both++;
  }));
  Object.keys(G).forEach(id => {
    const r = G[id];
    let m;
    if (r.set === 'both') {
      m = L.circleMarker(r.ll, {radius: R + 1, color: tok('--both'), weight: 2.2, fillColor: tok('--both'), fillOpacity: 0});
      m.bindPopup(() => bothPopup(pairsG[id]), {maxWidth: 380});
      m.bindTooltip(bdi(gName(r.p)) + ' ↔ ' + pairsG[id].map(t => bdi(aName(A[t.agency_hub_id].p))).join(', '), tip(R));
    } else if (r.set === 'onlyx') {
      m = L.circleMarker(r.ll, {radius: R + 1, color: tok('--onlyx'), weight: 2.4, fillColor: tok('--onlyx'), fillOpacity: .15});
      m.bindPopup(() => ourPopup(r, 'Only in Hubs project', '--onlyx'), {maxWidth: 340});
      m.bindTooltip(bdi(gName(r.p)) + ' (only in Hubs project)', tip(R));
      counts.onlyx++;
    } else {
      m = L.circleMarker(r.ll, {radius: R - 3, color: tok('--onlyx'), weight: 1.6, opacity: .8, dashArray: '3 3', fillColor: tok('--onlyx'), fillOpacity: .05});
      m.bindPopup(() => ourPopup(r, 'Hubs project group not scored', '--onlyx'), {maxWidth: 340});
      m.bindTooltip(bdi(gName(r.p)) + ' (not scored)', tip(R - 3));
      counts.filt++;
    }
    groups[r.set].addLayer(m);
    if (r.set !== 'filt') extend(m);
  });
  Object.keys(A).forEach(id => {
    const r = A[id];
    let m;
    if (r.set === 'both') {
      m = L.circleMarker(r.ll, {radius: R, color: tok('--ring'), weight: 1.5, fillColor: tok('--both'), fillOpacity: .95});
      m.bindPopup(() => bothPopup(pairsA[id]), {maxWidth: 380});
      m.bindTooltip(bdi(aName(r.p)) + ' ↔ ' + pairsA[id].map(t => bdi(gName(G[t.group].p))).join(', ') + ' (' + fmt(pairsA[id][0].distance_m) + ' m)', tip(R));
    } else if (r.set === 'onlym') {
      m = L.circleMarker(r.ll, {radius: R, color: tok('--ring'), weight: 1.5, fillColor: tok('--onlym'), fillOpacity: .95});
      m.bindPopup(() => theirPopup(r, 'Only in מנהל התכנון', '--onlym'), {maxWidth: 340});
      m.bindTooltip(bdi(aName(r.p)) + ' ' + escB('(only in מנהל התכנון)'), tip(R));
      counts.onlym++;
    } else {
      m = L.circleMarker(r.ll, {radius: R - 4, color: tok('--ring'), weight: 1, opacity: .8, fillColor: tok('--onlym'), fillOpacity: .4});
      m.bindPopup(() => theirPopup(r, 'מנהל התכנון hub with one mode', '--onlym'), {maxWidth: 340});
      m.bindTooltip(bdi(aName(r.p)) + ' (one mode)', tip(R - 4));
      counts.single++;
    }
    groups[r.set].addLayer(m);
    if (r.set !== 'single') extend(m);
  });
  ['both', 'onlyx', 'onlym', 'single', 'filt'].forEach(k => {
    if ($('set-' + k).checked) groups[k].addTo(map);
    wire('set-' + k, groups[k]);
    $('cnt-' + k).textContent = k === 'both' ? counts.both + ' pairs' : counts[k];
  });
  cities();
  fitAll();
  window.hubsPage = {map: map, groups: groups, counts: counts, basemap: basemap};
"""
