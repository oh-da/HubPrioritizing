"""Leaflet pages of ``hubs compare-network``: one for the routes, one for the hubs.

Each page is one self-contained HTML file. The layers of :func:`export.build_layers` are
reprojected to WGS84, reduced to GeoJSON features (coordinates rounded to six decimals, null
attributes left out) and embedded as a JSON block; Leaflet 1.9.4 comes from cdnjs. Text reaches
the page only through ``textContent`` and every ``<`` of the JSON block is escaped, so a
name cannot end the block or inject markup. The output is a pure function of the layers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import mapping

LEAFLET_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"
LEAFLET_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
COORD_DECIMALS = 6  # about 0.1 m
VALUE_DECIMALS = 4
ISRAEL_BOUNDS = [[29.4, 34.2], [33.4, 35.9]]  # [[south, west], [north, east]]
ROUTE_LAYERS = ("route_pairs", "our_routes", "our_routes_raw")
HUB_LAYERS = ("agency_hubs", "our_groups", "hub_ties")


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


def _round(coords: Any) -> Any:
    if len(coords) and isinstance(coords[0], (int, float)):
        return [round(float(c), COORD_DECIMALS) for c in coords[:2]]
    return [_round(c) for c in coords]


def _feature(geom: Any, props: Mapping[str, Any]) -> dict[str, Any]:
    geometry = None
    if geom is not None and not geom.is_empty:
        geometry = mapping(geom)
        geometry = {"type": geometry["type"], "coordinates": _round(geometry["coordinates"])}
    clean = {str(k): v for k, v in ((k, _value(v)) for k, v in props.items())
             if v is not None and v != ""}
    return {"type": "Feature", "geometry": geometry, "properties": clean}


def _collection(layers: Mapping[str, gpd.GeoDataFrame], name: str) -> dict[str, Any]:
    """The layer ``name`` as a WGS84 FeatureCollection (empty when the layer is missing)."""
    layer = layers.get(name)
    if layer is None or len(layer) == 0:
        return {"type": "FeatureCollection", "features": []}
    if layer.crs is None:
        layer = layer.set_crs(2039)
    layer = layer.to_crs(4326)
    columns = [c for c in layer.columns if c != layer.geometry.name]
    rows = layer[columns].to_dict("records")
    features = [_feature(g, r) for g, r in zip(layer.geometry, rows)]
    return {"type": "FeatureCollection", "features": features}


def _embed(data: Mapping[str, Any]) -> str:
    """JSON for a ``<script>`` block: UTF-8 kept, every ``<`` written as ``\\u003c``.

    That covers ``</script>`` and ``<!--`` inside a string and decodes to the same text.
    """
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def _render(title: str, subtitle: str, notes: list[str], data: Mapping[str, Any],
            page_js: str) -> str:
    html = _PAGE
    for key, value in {
        "__TITLE__": title, "__SUB__": subtitle, "__LEAFLET_CSS__": LEAFLET_CSS,
        "__LEAFLET_JS__": LEAFLET_JS, "__CSS__": _CSS,
        "__NOTES__": "".join(f"<p class=\"note\">{n}</p>" for n in notes),
        "__SCRIPT__": _COMMON_JS + page_js + "})();",
    }.items():
        html = html.replace(key, value)
    html = html.replace("__BOUNDS__", json.dumps(ISRAEL_BOUNDS))
    return html.replace("__DATA__", _embed(data))  # last: data text is never substituted


def _write(path: Path, html: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(html.encode("utf-8", "replace"))
    return path


def write_routes_map(path: Path, layers: Mapping[str, gpd.GeoDataFrame]) -> Path:
    """Write the route comparison page.

    Args:
        path: Output ``.html``.
        layers: :func:`export.build_layers` output (``route_pairs``, ``our_routes`` and
            ``our_routes_raw`` are used; a missing layer is treated as empty).

    Returns:
        ``path``. The page draws the agency routes coloured by match status and our routes as a
        dashed visual aid, with layer toggles, a raw / offset-corrected toggle, mode and status
        filters and a picker that isolates one route by our key or the agency key.
    """
    data = {name: _collection(layers, name) for name in ROUTE_LAYERS}
    notes = [
        "Our routes are a <b>visual aid</b>: our nodes joined in order of the shortest path "
        "(our lines have no stop order or geometry), drawn dashed. Agency routes are solid.",
        "An agency route can appear twice (an <code>agency_only</code> row and a weak or "
        "mode_differs row of ours on the same geometry); each row is its own feature.",
        "Basemap: OpenStreetMap; the page needs Leaflet 1.9.4 from cdnjs.",
    ]
    return _write(path, _render("Route comparison", "Agency routes vs our routes", notes, data,
                                _ROUTES_JS))


def write_hubs_map(path: Path, layers: Mapping[str, gpd.GeoDataFrame]) -> Path:
    """Write the hub comparison page.

    Args:
        path: Output ``.html``.
        layers: :func:`export.build_layers` output (``agency_hubs``, ``our_groups`` and
            ``hub_ties`` are used; a missing layer is treated as empty).

    Returns:
        ``path``. Hubs are circles sized by their number of modes; our groups are coloured by
        tier or eligibility; ties join paired hubs (zero-length ties are not drawn). Filters:
        relation, mode, eligible / filtered out; a picker isolates one hub with its partners.
    """
    data = {name: _collection(layers, name) for name in HUB_LAYERS}
    notes = [
        "Agency demand is not available in the agency files. The agency type is "
        "<b>derived</b> (the number of distinct modes, the rail-hub flag and the mode mix), "
        "not the agency's own classification.",
        "Circle size grows with the number of modes. Ties join the nearest points of a paired "
        "agency hub and group; a hub exactly on its group has no visible tie.",
        "Basemap: OpenStreetMap; the page needs Leaflet 1.9.4 from cdnjs.",
    ]
    return _write(path, _render("Hub comparison", "Agency hubs vs our hub groups", notes, data,
                                _HUBS_JS))


# ----------------------------------------------------------------------------------------
# Page templates
# ----------------------------------------------------------------------------------------

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="__LEAFLET_CSS__">
<style>__CSS__</style></head>
<body>
<div id="map" role="application" aria-label="__TITLE__"></div>
<section class="panel" id="panel">
<h1>__TITLE__</h1><p class="sub">__SUB__</p>
<div id="controls"></div><div id="legend"></div>
__NOTES__
</section>
<script type="application/json" id="page-data">__DATA__</script>
<script src="__LEAFLET_JS__"></script>
<script>__SCRIPT__</script>
</body></html>
"""

_CSS = """
:root{color-scheme:light dark;--bg:#f4f3ef;--panel:#fffefb;--line:#dcd9d0;--ink:#1c1b18;
--ink2:#5b5950;--ink3:#8a877c;--accent:#2a78d6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#17171a;--panel:#212125;
--line:#3a3a40;--ink:#f2f1ea;--ink2:#c3c2b7;--ink3:#8b8a82;--accent:#3987e5}}
:root[data-theme="dark"]{--bg:#17171a;--panel:#212125;--line:#3a3a40;--ink:#f2f1ea;
--ink2:#c3c2b7;--ink3:#8b8a82;--accent:#3987e5}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,"Segoe UI",sans-serif}
#map{position:absolute;inset:0;background:#e9e9e9}
.leaflet-popup-content-wrapper,.leaflet-popup-tip{background:var(--panel);color:var(--ink)}
.panel{position:absolute;z-index:1000;top:12px;left:12px;width:330px;max-width:calc(100% - 56px);
max-height:calc(100% - 24px);overflow:auto;box-sizing:border-box;padding:12px 14px;
background:var(--panel);border:1px solid var(--line);border-radius:10px;
box-shadow:0 4px 18px rgba(0,0,0,.25)}
h1{margin:0;font-size:17px}.sub{margin:2px 0 0;color:var(--ink2);font-size:12.5px}
.eyebrow{margin:12px 0 4px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;
color:var(--ink3)}
.row{display:flex;align-items:center;gap:7px;padding:3px 2px;cursor:pointer}
.row .lbl{flex:1}.cnt{color:var(--ink2);font-variant-numeric:tabular-nums;font-size:12.5px}
.sw{width:22px;height:0;border-top:4px solid;flex:none}.sw.dash{border-top-style:dashed}
.sw.dot{width:12px;height:12px;border:2px solid;border-radius:50%}
.field{display:block;margin-top:8px}.field select{display:block;width:100%;margin-top:2px;
font:inherit;padding:3px;background:var(--bg);color:var(--ink);border:1px solid var(--line)}
button{font:inherit;margin:8px 6px 0 0;padding:4px 9px;border:1px solid var(--line);
border-radius:6px;background:var(--bg);color:var(--ink);cursor:pointer}
.note{margin:8px 0 0;font-size:11.5px;color:var(--ink3)}.note code{font-size:11px}
.pp{max-height:260px;overflow:auto;min-width:200px}.pp h2{margin:0 0 4px;font-size:14px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:1px 8px;margin:0;font-size:12.5px}
.kv dt{color:var(--ink3)}.kv dd{margin:0;overflow-wrap:anywhere}
:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
@media (max-width:560px){.panel{top:auto;bottom:12px;left:12px;right:12px;width:auto;
max-width:none;max-height:45%}}
"""

# Shared by both pages: the script opens an IIFE here and the page JS closes it.
_COMMON_JS = """
(function () {
'use strict';
const DATA = JSON.parse(document.getElementById('page-data').textContent);
const ISRAEL = __BOUNDS__;
const controls = document.getElementById('controls');
const legend = document.getElementById('legend');
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
if (typeof L === 'undefined') {
  controls.appendChild(el('p', 'note', 'Leaflet could not be loaded from cdnjs (offline?).'));
  return;
}
const map = L.map('map', {preferCanvas: true});
map.fitBounds(ISRAEL);
const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'});
osm.addTo(map);
function swatch(color, kind) {
  const s = el('span', 'sw' + (kind ? ' ' + kind : ''));
  s.style.borderColor = color;
  return s;
}
function heading(text) { controls.appendChild(el('p', 'eyebrow', text)); }
function check(label, checked, onChange, color, kind, count) {
  const row = el('label', 'row');
  const box = el('input');
  box.type = 'checkbox';
  box.checked = checked;
  box.addEventListener('change', () => onChange(box.checked));
  row.appendChild(box);
  if (color) row.appendChild(swatch(color, kind));
  row.appendChild(el('span', 'lbl', label));
  if (count != null) row.appendChild(el('span', 'cnt', String(count)));
  controls.appendChild(row);
  return box;
}
function select(label, options, onChange) {
  const wrap = el('label', 'field');
  wrap.appendChild(el('span', null, label));
  const s = el('select');
  options.forEach(o => {
    const opt = el('option', null, o[1]);
    opt.value = o[0];
    s.appendChild(opt);
  });
  s.addEventListener('change', () => onChange(s.value));
  wrap.appendChild(s);
  controls.appendChild(wrap);
  return s;
}
function button(label, onClick) {
  const b = el('button', null, label);
  b.type = 'button';
  b.addEventListener('click', onClick);
  controls.appendChild(b);
}
function legendRow(color, text, kind) {
  const row = el('div', 'row');
  row.appendChild(swatch(color, kind));
  row.appendChild(el('span', 'lbl', text));
  legend.appendChild(row);
}
function popup(title, props) {
  const box = el('div', 'pp');
  box.setAttribute('dir', 'auto');
  box.appendChild(el('h2', null, title));
  const dl = el('dl', 'kv');
  Object.keys(props).forEach(k => {
    const v = props[k];
    dl.appendChild(el('dt', null, k));
    dl.appendChild(el('dd', null, typeof v === 'boolean' ? (v ? 'yes' : 'no') : String(v)));
  });
  box.appendChild(dl);
  return box;
}
function points(g) {  // every [lng, lat] of a GeoJSON geometry
  const out = [];
  (function walk(c) {
    if (typeof c[0] === 'number') out.push(c); else c.forEach(walk);
  })(g ? g.coordinates : []);
  return out;
}
function fitTo(pts) {
  if (!pts.length) { map.fitBounds(ISRAEL); return; }
  map.fitBounds(L.latLngBounds(pts.map(p => [p[1], p[0]])), {padding: [30, 30], maxZoom: 16});
}
const uniq = a => Array.from(new Set(a)).sort();
select('Basemap', [['osm', 'OpenStreetMap'], ['none', 'No basemap']], v => {
  if (v === 'osm') osm.addTo(map); else map.removeLayer(osm);
});
"""

_ROUTES_JS = """
const COLORS = {matched: '#1b9e77', partial: '#7570b3', split_merge: '#e6ab02', weak: '#d95f02',
  mode_differs: '#e7298a', agency_only: '#636363', ours_only: '#1f78b4'};
const MEANING = {matched: 'full match', partial: 'partial overlap', split_merge: 'split / merged',
  weak: 'weak overlap', mode_differs: 'overlaps a route of another mode',
  agency_only: 'agency route nothing of ours matches', ours_only: 'our route, no agency route'};
const groups = {agency: L.layerGroup().addTo(map), ours: L.layerGroup().addTo(map)};
const state = {agency: true, ours: true, mode: '', picked: '', status: {}};

function make(collection, kind) {  // one record per feature (row), never per route key
  return collection.features.map(f => {
    const p = f.properties || {};
    const status = p.status || (kind === 'agency' ? 'agency_only' : 'ours_only');
    const color = COLORS[status] || '#999999';
    const style = kind === 'agency' ? {color: color, weight: 5, opacity: 0.8}
      : {color: color, weight: 2.5, opacity: 1, dashArray: '7 5'};
    const layer = L.geoJSON(f, {style: () => style,
      pointToLayer: (ft, ll) => L.circleMarker(ll,
        Object.assign({radius: 5, fillOpacity: 0.7}, style))});
    const title = (kind === 'agency' ? p.agency_route_key : p.route_key) + ' - ' + status;
    layer.bindPopup(() => popup(title, p));
    const modes = kind === 'agency' ? [p.agency_type, p.our_mode] : [p.mode];
    return {kind: kind, p: p, status: status, modes: modes, layer: layer, g: f.geometry};
  });
}
const agencyRecs = make(DATA.route_pairs, 'agency');
const oursCorr = make(DATA.our_routes, 'ours');
const oursRaw = make(DATA.our_routes_raw, 'ours');
let useRaw = false;

function matchesKey(r, sel) {  // 'o:KEY' = our route key, 'a:KEY' = agency route key
  const k = sel.slice(2);
  if (sel[0] === 'o') return (r.kind === 'agency' ? r.p.our_route_key : r.p.route_key) === k;
  return r.p.agency_route_key === k;
}
function selected() {
  const recs = agencyRecs.concat(useRaw ? oursRaw : oursCorr);
  return state.picked ? recs.filter(r => matchesKey(r, state.picked)) : recs;
}
const info = document.createElement('p');
info.className = 'note';
function refresh() {
  groups.agency.clearLayers();
  groups.ours.clearLayers();
  let shown = 0;
  [agencyRecs, useRaw ? oursRaw : oursCorr].forEach(recs => recs.forEach(r => {
    if (!state[r.kind]) return;
    const ok = state.picked ? matchesKey(r, state.picked)
      : (state.status[r.status] !== false && (!state.mode || r.modes.includes(state.mode)));
    if (ok) { groups[r.kind].addLayer(r.layer); shown++; }
  }));
  info.textContent = shown + ' features shown' + (useRaw ? ' (our nodes at raw positions)' : '');
}

heading('Layers');
check('Agency routes (solid)', true, v => { state.agency = v; refresh(); });
check('Our routes (dashed, visual aid)', true, v => { state.ours = v; refresh(); });
check('Our nodes at raw positions, not offset-corrected', false, v => { useRaw = v; refresh(); });
heading('Match status (agency / ours routes)');
Object.keys(COLORS).forEach(s => {
  const a = agencyRecs.filter(r => r.status === s).length;
  const o = oursCorr.filter(r => r.status === s).length;
  check(s, true, v => { state.status[s] = v; refresh(); }, COLORS[s], null, a + ' / ' + o);
  legendRow(COLORS[s], s + ': ' + MEANING[s], s === 'ours_only' ? 'dash' : '');
});
const allRecs = agencyRecs.concat(oursCorr);
select('Mode', [['', 'All modes']].concat(uniq(allRecs.flatMap(r => r.modes).filter(Boolean))
  .map(m => [m, m])), v => { state.mode = v; refresh(); });
const names = {};
oursCorr.forEach(r => {
  names['o:' + r.p.route_key] = 'ours ' + r.p.route_key + ' ' + (r.p.line_names || '');
});
agencyRecs.forEach(r => {
  names['a:' + r.p.agency_route_key] = 'agency ' + r.p.agency_route_key + ' '
    + (r.p.agency_name || '');
});
select('Isolate one route (ignores the filters)', [['', 'All routes']].concat(
  Object.keys(names).sort().map(k => [k, names[k]])), v => {
  state.picked = v;
  refresh();
  if (v) fitTo(selected().flatMap(r => points(r.g)));
});
button('Zoom to all', () => fitTo(allRecs.flatMap(r => points(r.g))));
controls.appendChild(info);
legendRow('#444444', 'solid thick: agency route; dashed thin: ours (visual aid)', '');
refresh();
fitTo(allRecs.flatMap(r => points(r.g)));
"""

_HUBS_JS = """
const REL = ['1:1', 'agency_splits', 'ours_merges', 'many_to_many', 'agency_only', 'ours_only'];
const PREFERRED = {'ארצי': '#d62728', 'מטרופוליני': '#ff7f0e', 'עירוני': '#2ca02c',
  National: '#d62728', Metropolitan: '#ff7f0e', Local: '#2ca02c'};
const SPARE = ['#7b3294', '#2c7bb6', '#a6761d', '#e7298a', '#66a61e'];
const AGENCY = '#0b6e4f', GREY = '#9a9a9a', BLUE = '#2a78d6';
const state = {agency: true, ours: true, ties: true, mode: '', elig: 'all', picked: '', rel: {}};
let colorBy = 'tier';

const lg = {agency: L.layerGroup().addTo(map), ours: L.layerGroup().addTo(map),
  ties: L.layerGroup().addTo(map)};
const radius = p => Math.min(16, 5 + 2.5 * (p.n_modes || 1));
function centre(g) {
  const pts = points(g);
  if (!pts.length) return null;
  const s = pts.reduce((a, c) => [a[0] + c[0], a[1] + c[1]], [0, 0]);
  return [s[0] / pts.length, s[1] / pts.length];
}
function hubRecs(collection, kind) {
  const out = [];
  collection.features.forEach((f, i) => {
    const p = f.properties || {};
    const c = centre(f.geometry);
    if (!c) return;  // a group without a position cannot be drawn
    const id = kind === 'agency' ? 'a' + p.agency_hub_id
      : 'g' + (p.group != null ? p.group : '?' + i);
    const m = L.circleMarker([c[1], c[0]], kind === 'agency'
      ? {radius: radius(p), color: AGENCY, weight: 2.5, fillColor: AGENCY, fillOpacity: 0.12}
      : {radius: radius(p), color: '#ffffff', weight: 1.5, fillOpacity: 0.9});
    const title = kind === 'agency' ? (p.name || id) : (p.HubNameHE || p.hub_id || id);
    m.bindPopup(() => popup(title, p));
    const parts = [m];
    const stops = points(f.geometry);
    if (kind === 'agency' && stops.length > 1) stops.forEach(s => parts.push(
      L.circleMarker([s[1], s[0]], {radius: 2.5, color: AGENCY, weight: 1, interactive: false})));
    const modes = String(kind === 'agency' ? p.modes || '' : p.Mode_Planned || '').split('; ');
    out.push({kind: kind, id: id, p: p, modes: modes, marker: m, layer: L.layerGroup(parts), c: c});
  });
  return out;
}
const agencyRecs = hubRecs(DATA.agency_hubs, 'agency');
const groupRecs = hubRecs(DATA.our_groups, 'ours');
const byId = {};
agencyRecs.concat(groupRecs).forEach(r => { byId[r.id] = r; });

const adj = {};
const ties = DATA.hub_ties.features.map(f => {
  const p = f.properties || {};
  const a = 'a' + p.agency_hub_id, g = 'g' + p.group;
  (adj[a] = adj[a] || new Set()).add(g);
  (adj[g] = adj[g] || new Set()).add(a);
  const cs = f.geometry ? f.geometry.coordinates : [];
  const first = cs[0], last = cs[cs.length - 1];
  const degenerate = cs.length < 2 || (first[0] === last[0] && first[1] === last[1]);
  const style = {color: '#555555', weight: 1, opacity: 0.7};
  const line = degenerate ? null : L.geoJSON(f, {style: () => style});
  if (line) line.bindPopup(() => popup('tie ' + a + ' - ' + g, p));
  return {a: a, g: g, line: line};
});

const tiers = uniq(groupRecs.map(r => r.p.HubType).filter(Boolean));
const tierColor = {};
let spare = 0;
tiers.forEach(t => { tierColor[t] = PREFERRED[t] || SPARE[spare++ % SPARE.length]; });
function groupColor(p) {
  if (colorBy === 'eligible') return p.eligible ? BLUE : GREY;
  return p.eligible && p.HubType ? tierColor[p.HubType] : GREY;
}
function drawLegend() {
  legend.textContent = '';
  legendRow(AGENCY, 'agency hub (hollow ring; small dots = its stops)', 'dot');
  if (colorBy === 'eligible') {
    legendRow(BLUE, 'our group: eligible (scored)', 'dot');
  } else {
    tiers.forEach(t => legendRow(tierColor[t], 'our group: ' + t, 'dot'));
  }
  legendRow(GREY, 'our group: not eligible (filtered out)', 'dot');
}
function visible(r) {
  if (state.picked) return r.id === state.picked || (adj[state.picked] || new Set()).has(r.id);
  if (state.rel[r.p.relation] === false) return false;
  if (state.mode && !r.modes.includes(state.mode)) return false;
  return r.kind === 'agency' || state.elig === 'all' || (state.elig === 'yes') === !!r.p.eligible;
}
const info = document.createElement('p');
info.className = 'note';
function refresh() {
  Object.keys(lg).forEach(k => lg[k].clearLayers());
  const vis = {};
  let shown = 0;
  agencyRecs.concat(groupRecs).forEach(r => {
    if (r.kind === 'ours') r.marker.setStyle({fillColor: groupColor(r.p)});
    vis[r.id] = state[r.kind] && visible(r);
    if (vis[r.id]) { lg[r.kind].addLayer(r.layer); shown++; }
  });
  ties.forEach(t => {
    if (t.line && state.ties && vis[t.a] && vis[t.g]) lg.ties.addLayer(t.line);
  });
  info.textContent = shown + ' hubs shown';
}

heading('Layers');
check('Agency hubs', true, v => { state.agency = v; refresh(); }, AGENCY, 'dot');
check('Our groups', true, v => { state.ours = v; refresh(); }, BLUE, 'dot');
check('Ties between paired hubs', true, v => { state.ties = v; refresh(); }, '#555555');
heading('Relation (agency hubs / our groups)');
REL.forEach(rel => {
  const a = agencyRecs.filter(r => r.p.relation === rel).length;
  const g = groupRecs.filter(r => r.p.relation === rel).length;
  check(rel, true, v => { state.rel[rel] = v; refresh(); }, null, null, a + ' / ' + g);
});
select('Mode', [['', 'All modes']].concat(uniq(agencyRecs.concat(groupRecs)
  .flatMap(r => r.modes).filter(Boolean)).map(m => [m, m])), v => { state.mode = v; refresh(); });
select('Our groups shown', [['all', 'All groups'], ['yes', 'Eligible only'],
  ['no', 'Filtered out only']], v => { state.elig = v; refresh(); });
select('Colour our groups by', [['tier', 'Tier (HubType)'], ['eligible', 'Eligible / not']],
  v => { colorBy = v; drawLegend(); refresh(); });
const names = {};
agencyRecs.forEach(r => { names[r.id] = 'agency ' + r.p.agency_hub_id + ' ' + (r.p.name || ''); });
groupRecs.forEach(r => {
  names[r.id] = 'group ' + (r.p.group != null ? r.p.group : '?') + ' ' + (r.p.HubNameHE || '');
});
select('Isolate one hub with its partners (ignores the filters)', [['', 'All hubs']].concat(
  Object.keys(names).sort().map(k => [k, names[k]])), v => {
  state.picked = v;
  refresh();
  if (v) {
    const ids = [v].concat(Array.from(adj[v] || []));
    fitTo(ids.filter(i => byId[i]).map(i => byId[i].c));
  }
});
button('Zoom to all', () => fitTo(agencyRecs.concat(groupRecs).map(r => r.c)));
controls.appendChild(info);
drawLegend();
refresh();
fitTo(agencyRecs.concat(groupRecs).map(r => r.c));
"""
