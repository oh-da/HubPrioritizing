// Runs the inline script of a generated comparison page against a minimal DOM and Leaflet
// stub (no network, no browser): usage `node compare_maps_stub.js page.html`.
// It exercises every control (change / click events), then checks the layer bookkeeping.
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const data = /<script type="application\/json" id="page-data">([\s\S]*?)<\/script>/.exec(html)[1];
const code = /<script>([\s\S]*?)<\/script>/.exec(html)[1];

class El {
  constructor(tag) { this.tag = tag; this.children = []; this.listeners = {}; this.style = {};
    this.attrs = {}; this._text = ''; this.value = ''; this.checked = false; }
  appendChild(c) { this.children.push(c); return c; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  fire(t) { (this.listeners[t] || []).forEach(f => f({target: this})); }
  set textContent(v) { this._text = String(v); if (v === '') this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  all() { return [this].concat(...this.children.map(c => c.all())); }
}
const byId = {map: new El('div'), controls: new El('div'), legend: new El('div'),
  panel: new El('section'), 'page-data': new El('script')};
byId['page-data']._text = data;
global.document = {getElementById: id => byId[id], createElement: tag => new El(tag)};

const state = {added: 0, removed: 0, fits: [], popups: 0, groups: []};
class Layer {
  constructor(kids) { this.kids = kids || []; this.set = new Set(); }
  addTo() { return this; }
  addLayer(l) { this.set.add(l); return this; }
  removeLayer(l) { this.set.delete(l); return this; }
  clearLayers() { this.set.clear(); return this; }
  bindPopup(f) { state.popups++; if (typeof f === 'function') this.popup = f; return this; }
  setStyle() { return this; }
}
const mk = () => new Layer();
global.L = {
  map: () => ({fitBounds: (b) => state.fits.push(b), removeLayer() {}, setView() {}}),
  tileLayer: () => ({addTo() { return this; }}),
  layerGroup: (kids) => { const g = new Layer(kids); state.groups.push(g); return g; },
  geoJSON: mk, circleMarker: mk, polyline: mk,
  latLngBounds: (pts) => ({pts: pts}),
  control: {zoom: () => ({addTo() { return this; }})},
};
(0, eval)(code);  // the runner evaluates the page script; the page itself never uses eval

const nodes = byId.controls.all();
const selects = nodes.filter(n => n.tag === 'select');
const checks = nodes.filter(n => n.tag === 'input');
const shown = () => state.groups.reduce((n, g) => n + g.set.size, 0);
const base = shown();
checks.forEach(c => { c.checked = !c.checked; c.fire('change'); c.checked = !c.checked; c.fire('change'); });
selects.forEach(s => {
  const opts = s.children.filter(o => o.tag === 'option');
  opts.forEach(o => { s.value = o.value; s.fire('change'); });
  s.value = opts[0].value; s.fire('change');
});
byId.controls.all().filter(n => n.tag === 'button').forEach(b => b.fire('click'));
if (shown() !== base) throw new Error('state not restored: ' + base + ' -> ' + shown());
if (state.fits.length === 0) throw new Error('map never fitted');
const total = JSON.parse(data);
const n = Object.values(total).reduce((a, c) => a + c.features.length, 0);
console.log('OK', 'features=' + n, 'shown=' + base, 'controls=' + (checks.length + selects.length));
