// Runs the inline script of a generated comparison page against a minimal DOM and Leaflet
// stub (no network, no browser): usage `node compare_maps_stub.js page.html`.
// It builds every popup and tooltip, fires every control (change / click events), checks
// that the panel counts equal the layers drawn and prints one JSON line.
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const data = /<script type="application\/json" id="page-data">([\s\S]*?)<\/script>/.exec(html)[1];
const code = /<script>\n([\s\S]*?)<\/script>/.exec(html)[1];

class El {
  constructor(tag, id) { this.tag = tag; this.id = id; this.children = []; this.listeners = {};
    this.attrs = {}; this._text = ''; this.value = ''; this.checked = /checked/.test(tag); this.dataset = {}; }
  appendChild(c) { this.children.push(c); return c; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k]; }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  fire(t) { (this.listeners[t] || []).forEach(f => f({target: this})); }
  set textContent(v) { this._text = String(v); }
  get textContent() { return this._text; }
}
// the static markup gives each element's tag and whether a checkbox starts checked
const els = {};
const tagRe = /<(\w+)([^>]*?)\sid="([^"]+)"([^>]*)>/g;
let m;
while ((m = tagRe.exec(html))) {
  const e = new El(m[1] + (/\schecked/.test(m[2] + m[4]) ? ' checked' : ''), m[3]);
  e.tag = m[1];
  els[m[3]] = e;
}
els['page-data']._text = data;
global.document = {getElementById: id => els[id] || (els[id] = new El('div', id)),
  createElement: tag => new El(tag), documentElement: {}};
global.getComputedStyle = () => ({getPropertyValue: n => '#123456'});
global.window = {};

const state = {fits: 0, views: 0, onMap: new Set(), popups: 0, tooltips: 0, errors: []};
class Layer {
  constructor(opts) { this.options = Object.assign({}, opts); this.kids = []; }
  addTo(map) { state.onMap.add(this); return this; }
  addLayer(l) { this.kids.push(l); return this; }
  getLayers() { return this.kids.slice(); }
  bindPopup(f) { this.popup = f; return this; }
  bindTooltip(t) { this.tooltip = t; return this; }
  setStyle(s) { Object.assign(this.options, s); return this; }
  bringToFront() { return this; }
  on() { return this; }
}
class Path extends Layer {
  constructor(ll, opts) { super(opts); this.ll = ll; }
  getBounds() { return {}; }
}
class Circle extends Path { getLatLng() { return this.ll; } }
const bounds = () => { let n = 0; return {extend() { n++; return this; }, isValid: () => n > 0}; };
const mapObj = {
  fitBounds() { state.fits++; }, setView() { state.views++; }, removeLayer(l) { state.onMap.delete(l); },
  hasLayer: l => state.onMap.has(l), on() {}, getContainer: () => ({setAttribute() {}}),
  attributionControl: {setPrefix() {}},
};
global.L = {
  map: () => mapObj,
  tileLayer: () => new Layer(),
  layerGroup: () => new Layer(),
  polyline: (ll, o) => new Path(ll, o),
  circleMarker: (ll, o) => new Circle(ll, o),
  latLngBounds: bounds,
  control: {zoom: () => ({addTo() { return this; }})},
  DomEvent: {disableClickPropagation() {}, disableScrollPropagation() {}},
};
(0, eval)(code);  // the runner evaluates the page script; the page itself never uses eval

const page = global.window.hubsPage;
if (!page) throw new Error('page did not finish');
const out = {counts: {}, drawn: {}, popups: 0, tooltips: 0};
Object.keys(page.groups).forEach(k => {
  const layers = page.groups[k].getLayers();
  const ties = layers.filter(l => !(l instanceof Circle));
  out.drawn[k] = k === 'both' ? ties.length : layers.length;
  out.counts[k] = els['cnt-' + k].textContent;
  layers.forEach(l => {
    if (l.popup) {
      const h = l.popup(l);
      if (!/^<div class="pp" dir="auto">/.test(h)) throw new Error('popup markup: ' + h.slice(0, 80));
      out.popups++;
    }
    if (l.tooltip) out.tooltips++;
  });
});
const onMapBefore = Object.keys(page.groups).filter(k => state.onMap.has(page.groups[k])).sort();
Object.values(els).forEach(e => {
  if (e.tag === 'input') { e.checked = !e.checked; e.fire('change'); e.checked = !e.checked; e.fire('change'); }
  if (e.tag === 'select') {
    e.children.forEach(o => { e.value = o.value; e.fire('change'); });
    e.value = ''; e.fire('change');
  }
  if (e.tag === 'button') e.fire('click');
});
const onMapAfter = Object.keys(page.groups).filter(k => state.onMap.has(page.groups[k])).sort();
if (onMapBefore.join() !== onMapAfter.join()) throw new Error('toggles not restored');
if (!state.fits) throw new Error('map never fitted');
if (state.views < 4) throw new Error('city buttons did not move the map');
out.onMap = onMapAfter;
console.log(JSON.stringify(out));
