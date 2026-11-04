"""Shared look of the comparison pages: design tokens, CSS, basemap block and display labels.

Used by :mod:`src.compare.maps` (the two ``hubs compare-network`` pages) and by
``scripts/build_missing_map.py``. The design follows the HubsScraping reference pages
(``compare_lines.html`` and ``compare.html``): the same ``:root`` tokens, panel, set rows,
popups and chips. Everything here is a constant or a pure function of constants, so a page
built from it is byte-identical for the same data.

* :data:`TOKENS` - the reference's CSS custom properties, light and dark.
* :data:`LABELS` - the ONE map from the codes of the data (route statuses, hub relations,
  verdicts, exclusion reasons, hub types) to the plain words the pages show.
* :data:`BASEMAPS` / :func:`basemap_js` - four basemaps with an automatic fallback when the
  tiles of one do not load (a page opened from disk sends no Referer, which OpenStreetMap's
  tile servers refuse).
"""

from __future__ import annotations

import json
import re
from typing import Any

LEAFLET_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"
LEAFLET_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
FONT_CSS = "https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&display=swap"

AGENCY_HE = "מנהל התכנון"  # the planning agency, as the pages name it
OURS_HE = "פרויקט תעדוף מתחמים"  # the Hubs project
TILE_FAIL_AFTER = 6  # tile errors before any tile loaded that make the page switch basemap

# ----------------------------------------------------------------------------------------
# Design tokens (values copied from the reference pages; tests check the parity)
# ----------------------------------------------------------------------------------------

TOKENS: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#f4f3ef", "panel": "#fffefb", "panel-border": "#dcd9d0", "ink": "#1c1b18",
        "ink-2": "#5b5950", "ink-3": "#8a877c", "map-bg": "#e9e9e9",
        "shadow": "0 4px 18px rgba(30,28,20,.16)", "accent": "#2a78d6", "focus": "#2a78d6",
        "ring": "#ffffff", "routed": "#2a78d6", "diff": "#eb6834", "off": "#c8102e",
        "used": "#9a978c", "gap": "#b038c9", "onlym": "#1baf7a", "tie": "#2a78d6",
        "both": "#2a78d6", "onlyx": "#eb6834",
    },
    "dark": {
        "bg": "#17171a", "panel": "#212125", "panel-border": "#3a3a40", "ink": "#f2f1ea",
        "ink-2": "#c3c2b7", "ink-3": "#8b8a82", "map-bg": "#e9e9e9",
        "shadow": "0 4px 18px rgba(0,0,0,.5)", "accent": "#3987e5", "focus": "#3987e5",
        "ring": "#ffffff", "routed": "#2a78d6", "diff": "#d95926", "off": "#c8102e",
        "used": "#8c8a80", "gap": "#a02fb8", "onlym": "#199e70", "tie": "#2a78d6",
        "both": "#2a78d6", "onlyx": "#d95926",
    },
}


def _token_lines(scheme: str) -> str:
    return " ".join(f"--{k}: {v};" for k, v in TOKENS[scheme].items())


def tokens_css() -> str:
    """The three ``:root`` blocks (light, dark by preference, dark forced) of the pages."""
    dark = f"color-scheme: dark; {_token_lines('dark')}"
    return (
        f":root {{ color-scheme: light; {_token_lines('light')} }}\n"
        f"@media (prefers-color-scheme: dark) {{ :root:not([data-theme=\"light\"]) {{ {dark} }} }}\n"
        f":root[data-theme=\"dark\"] {{ {dark} }}\n"
    )


# The reference CSS (compare_lines.html and compare.html), one copy for every page.
BASE_CSS = """
html, body { height: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.4 "Heebo", "Segoe UI", system-ui, sans-serif; }
#map { position: absolute; inset: 0; background: var(--map-bg); }
.leaflet-container { background: var(--map-bg); font: inherit; }
.osm-gray { filter: grayscale(1) brightness(1.06) contrast(0.88); }
.leaflet-bar { box-shadow: var(--shadow); border: 1px solid var(--panel-border); }
.leaflet-bar a { background: var(--panel); color: var(--ink); border-bottom-color: var(--panel-border); }
.leaflet-bar a:hover, .leaflet-bar a:focus-visible { background: var(--bg); }
.leaflet-control-attribution { background: color-mix(in srgb, var(--panel) 85%, transparent); color: var(--ink-3); font-size: 11px; }
.leaflet-control-attribution a { color: var(--ink-2); }
.leaflet-popup-content-wrapper, .leaflet-popup-tip { background: var(--panel); color: var(--ink); box-shadow: var(--shadow); }
.leaflet-popup-content-wrapper { border-radius: 8px; border: 1px solid var(--panel-border); }
.leaflet-popup-content { margin: 12px 14px; font-size: 13px; min-width: 220px; }
.leaflet-container a.leaflet-popup-close-button { color: var(--ink-3); }
.leaflet-container :focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.panel { position: absolute; z-index: 1000; top: calc(12px + env(safe-area-inset-top, 0px)); left: 12px; width: 336px; max-width: calc(100% - 24px); max-height: calc(100% - 24px); overflow: auto;
  background: var(--panel); border: 1px solid var(--panel-border); border-radius: 10px; box-shadow: var(--shadow); padding: 14px 16px 12px; box-sizing: border-box; }
.panel h1 { margin: 0; font-size: 17px; font-weight: 700; letter-spacing: -.01em; text-wrap: balance; }
.panel .sub { margin: 2px 0 0; color: var(--ink-2); font-size: 12.5px; }
.panel bdi { white-space: nowrap; }
.eyebrow { margin: 14px 0 6px; font-size: 11px; font-weight: 500; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-3); }
.sets { display: grid; gap: 2px; margin: 0; padding: 0; list-style: none; }
.sets label { display: grid; grid-template-columns: 18px 26px 1fr auto; align-items: center; gap: 8px; padding: 4px 6px; border-radius: 6px; cursor: pointer; }
.sets label:hover { background: var(--bg); }
.sets input { margin: 0; width: 15px; height: 15px; accent-color: var(--accent); }
.sets input:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
.sets .lbl { font-weight: 500; line-height: 1.2; }
.sets .lbl small { display: block; font-weight: 400; color: var(--ink-3); font-size: 11.5px; }
.sets .cnt { color: var(--ink-2); font-variant-numeric: tabular-nums; font-size: 13px; text-align: right; }
.sym { justify-self: center; width: 22px; height: 16px; }
.pick { display: grid; grid-template-columns: 1fr auto; gap: 6px; margin-top: 6px; }
.pick.one { grid-template-columns: 1fr; }
.pick select, .pick input { font: inherit; font-size: 12.5px; padding: 5px 6px; border-radius: 6px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--ink); min-width: 0; }
.pick select:focus-visible, .pick input:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
.actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.actions button { flex: 1 1 auto; white-space: nowrap; font: inherit; font-size: 12.5px; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--ink); cursor: pointer; }
.actions button:hover { border-color: var(--ink-3); }
.actions button:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
.note { margin: 10px 0 0; font-size: 11.5px; color: var(--ink-3); }
.bm-note { color: var(--ink-2); }
.bm-note:empty { display: none; }
.st { display: inline-block; font-size: 11px; font-weight: 500; letter-spacing: .04em; padding: 1px 7px; border-radius: 99px; color: #fff; }
.st-match { background: var(--onlym); } .st-partial { background: var(--diff); } .st-missing { background: var(--off); }
.pp h2 { margin: 0 0 6px; font-size: 14px; font-weight: 700; line-height: 1.25; }
.pp .tag { display: inline-block; font-size: 11px; font-weight: 500; letter-spacing: .04em; padding: 1px 7px; border-radius: 99px; color: #fff; margin-bottom: 6px; }
.pp .expl { margin: 0; font-size: 12px; color: var(--ink-2); }
.pp .two { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.pp .two + .two { margin-top: 8px; }
.pp .col { border: 1px solid var(--panel-border); border-radius: 6px; padding: 6px 8px; }
.pp .col h3 { margin: 0 0 3px; font-size: 11px; letter-spacing: .02em; color: var(--ink-3); font-weight: 500; }
.pp .col .nm { font-weight: 600; }
.pp .kv { display: grid; grid-template-columns: auto 1fr; gap: 2px 8px; font-size: 12.5px; margin-top: 6px; }
.pp .kv dt { color: var(--ink-3); } .pp .kv dd { margin: 0; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.pp .diff { color: var(--diff); } .pp .same { color: var(--onlym); } .pp .bad { color: var(--off); }
.pp button { font: inherit; font-size: 12px; margin-top: 8px; padding: 4px 8px; border-radius: 6px; border: 1px solid var(--panel-border); background: var(--bg); color: var(--ink); cursor: pointer; }
@media (max-width: 560px) {
  .panel { top: auto; bottom: calc(12px + env(safe-area-inset-bottom, 0px)); left: 12px; right: 12px; width: auto; max-height: 50%; }
  .leaflet-top.leaflet-right { top: env(safe-area-inset-top, 0px); }
}
@media (prefers-reduced-motion: reduce) { .leaflet-zoom-anim .leaflet-zoom-animated, .leaflet-fade-anim .leaflet-popup { transition: none; } }
"""

# ----------------------------------------------------------------------------------------
# Display labels: the one place where a code of the data becomes the words a page shows
# ----------------------------------------------------------------------------------------

LABELS: dict[str, dict[str, list[str]]] = {
    # code -> [label, short explanation]
    "route_status": {
        "matched": ["Same line", f"a line of ours that follows a line of {AGENCY_HE}"],
        "partial": ["Partly the same", "only part of the two lines runs together"],
        "split_merge": ["Split or joined", "one line on one side is several lines on the other"],
        "ours_within_agency": ["Part of a longer line",
                               f"our line lies on a longer line of {AGENCY_HE}"],
        "agency_within_ours": ["Part of our longer line",
                               "their line lies on a longer line of ours"],
        "weak": ["Barely overlaps", f"the closest line of {AGENCY_HE} shares only a little"],
        "mode_differs": ["Other mode", "same alignment, different mode"],
        "ours_only": ["Only in Hubs project", f"no line of {AGENCY_HE} here"],
        "agency_only": [f"Only in {AGENCY_HE}", "no line of ours follows it"],
        "covered": ["Covered by another line", "a line of ours already follows it"],
    },
    "hub_relation": {
        "1:1": ["one to one", "one hub on each side"],
        "agency_splits": [f"one hub of {AGENCY_HE} covers several of ours", ""],
        "ours_merges": [f"several hubs of {AGENCY_HE} are one of ours", ""],
        "many_to_many": ["overlapping hubs", "several hubs on each side touch each other"],
        "agency_only": [f"only in {AGENCY_HE}", ""],
        "ours_only": ["only in Hubs project", ""],
    },
    "verdict": {
        "real_gap": ["Missing", "nothing on the other side comes close"],
        "covered_elsewhere": ["Covered by another line", "other lines of the other side serve it"],
        "definition_difference": ["Defined differently", "the two sides define it differently"],
        "check": ["Needs a look", "the numbers do not decide it"],
        "present": ["In both", "both sides have it"],
    },
    "exclusion": {
        "demand < min": ["under 1,000 passengers a day", ""],
        "single mode": ["one mode only", ""],
        "rail only": ["only rail lines", ""],
    },
    "hub_type": {
        "Not Hub": ["not a hub (fewer than 3 lines)", ""],
        "Train Station": ["train station", ""],
    },
}

# reason texts of the route table (src/compare/routes.py) -> plain words; first match wins
_REASONS: tuple[tuple[str, str], ...] = (
    (r"^no candidate$", f"no line of {AGENCY_HE} nearby"),
    (r"^agency route shared by (\d+) of our routes$", r"their line is shared by \1 of our lines"),
    (r"^best score of ours ([\d.]+) below ([\d.]+)$",
     r"best overlap score of our lines \1, below \2"),
    (r"^best score below ([\d.]+)$", r"best overlap score below \1"),
    (r"^runs over (\d+) agency routes$", rf"runs over \1 lines of {AGENCY_HE}"),
    (r"^only cross-mode candidates.*$", "only lines of another mode nearby"),
    (r"^best match is an agency route of another type$", "the closest line is of another mode"),
    (r"^our route lies on a longer agency route$",
     f"our line lies on a longer line of {AGENCY_HE}"),
    (r"^candidate of (\d+) of our routes, never their best$",
     r"close to \1 of our lines, but the best match of none"),
    (r"^the agency route lies on a longer route of ours$",
     "their line lies on a longer line of ours"),
    (r"^no agency mode$", f"this mode has no counterpart at {AGENCY_HE}"),
)
_WORDS = ((r"\bagency\b", AGENCY_HE), (r"\bAgency\b", AGENCY_HE), (r"\broutes\b", "lines"),
          (r"\broute\b", "line"), (r"\bcandidates?\b", "close line"))


def plain_reason(text: Any) -> str:
    """The reason text of a route row in plain words (``""`` for an empty reason)."""
    if text is None or (isinstance(text, float) and text != text):
        return ""
    text = str(text).strip()
    for pattern, repl in _REASONS:
        if re.match(pattern, text):
            return re.sub(pattern, repl, text)
    for pattern, repl in _WORDS:
        text = re.sub(pattern, repl, text)
    return text


def label(kind: str, code: Any) -> str:
    """The display label of ``code`` in the section ``kind`` of :data:`LABELS` (else ``code``)."""
    entry = LABELS.get(kind, {}).get(str(code))
    return entry[0] if entry else str(code)


# ----------------------------------------------------------------------------------------
# Basemap block
# ----------------------------------------------------------------------------------------

_OSM = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
BASEMAPS: list[dict[str, Any]] = [
    {"id": "carto", "name": "CARTO light",
     "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
     "options": {"subdomains": "abcd", "maxZoom": 20,
                 "attribution": f'{_OSM} &copy; <a href="https://carto.com/attributions">CARTO</a>'}},
    {"id": "esri", "name": "Esri light gray",
     "url": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/"
            "MapServer/tile/{z}/{y}/{x}",
     "options": {"maxNativeZoom": 16, "maxZoom": 19, "attribution": "Tiles &copy; Esri"}},
    {"id": "osm", "name": "OpenStreetMap (light gray)",
     "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
     "options": {"maxZoom": 19, "className": "osm-gray", "attribution": _OSM}},
    {"id": "none", "name": "No basemap", "url": None, "options": {}},
]


def safe_json(data: Any) -> str:
    """JSON for a ``<script>`` block: UTF-8 kept, every ``<`` written as ``\\u003c``."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


BASEMAP_HTML = """<p class="eyebrow">Basemap</p>
  <div class="pick one"><select id="basemap" aria-label="Basemap"></select></div>
  <p class="note bm-note" id="basemap-note" role="status" aria-live="polite"></p>"""

_BASEMAP_JS = r"""
// Basemaps in order; when the first tiles of the active one all fail before any loads, the
// next one is tried, and a short notice in the panel says so (a page opened from disk sends
// no Referer, which OpenStreetMap refuses). A basemap the user picks is never replaced.
function hubsBasemap(map, select, note) {
  var list = HUBS_BASEMAPS, active = null, current = -1, auto = true;
  list.forEach(function (b, i) {
    var o = document.createElement('option'); o.value = String(i); o.textContent = b.name; select.appendChild(o);
  });
  var none = list.length - 1;
  function use(i) {
    if (active) { map.removeLayer(active); active = null; }
    current = i; select.value = String(i);
    map.getContainer().setAttribute('data-basemap', list[i].id);
    var b = list[i];
    if (!b.url) return;
    var layer = L.tileLayer(b.url, b.options), loaded = 0, failed = 0, done = false;
    function fail() {  // later, never inside Leaflet's own tile event handler
      if (done || layer !== active) return;
      done = true;
      setTimeout(switchAway, 0);
    }
    function switchAway() {
      if (layer !== active) return;
      if (!auto) { note.textContent = 'Basemap tiles from ' + b.name + ' did not load (blocked or offline).'; return; }
      var next = i + 1;
      if (next < none) {
        use(next);
        note.textContent = 'Basemap tiles from ' + b.name + ' did not load (blocked or offline); switched to ' + list[next].name + '.';
      } else {
        use(none);
        note.textContent = 'No basemap tiles could be loaded; the lines and hubs still draw on the gray background.';
      }
    }
    layer.on('tileload', function () { if (layer !== active) return; loaded++; auto = false; });
    layer.on('tileerror', function () { if (layer !== active) return; failed++; if (!loaded && failed >= __FAIL_AFTER__) fail(); });
    layer.on('load', function () { if (layer === active && !loaded && failed) fail(); });
    active = layer;
    layer.addTo(map);
  }
  select.addEventListener('change', function () { auto = false; note.textContent = ''; use(Number(select.value)); });
  use(0);
  return {current: function () { return list[current].id; }};
}
"""


def basemap_js() -> str:
    """The basemap function ``hubsBasemap(map, select, note)`` with the provider list."""
    return ("var HUBS_BASEMAPS = " + safe_json(BASEMAPS) + ";\n"
            + _BASEMAP_JS.replace("__FAIL_AFTER__", str(TILE_FAIL_AFTER)))
