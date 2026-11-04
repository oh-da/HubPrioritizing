// Loads a comparison page in Chromium (Playwright) with the real Leaflet 1.9.4 and no network:
// the cdnjs Leaflet files are served from a local folder, fonts are aborted and the tile
// servers answer as a scenario says. Prints one JSON object with what it saw.
//
//   node compare_maps_browser.js --leaflet DIR --page FILE [--scenario A|B|C|D|offline]
//        [--check] [--shot PNG] [--width 1400] [--height 900]
//
// Scenarios (basemap fallback): A CARTO answers; B CARTO aborted, Esri answers; C CARTO and
// Esri aborted, OpenStreetMap 403 (no Referer); D every server answers, then the user picks
// OpenStreetMap in the Basemap select; offline: every tile request aborted.
// --check exercises the page (counts vs drawn layers, toggles, pickers, popups, city buttons)
// and returns the visible texts so the caller can check the wording.
const fs = require('fs');
const path = require('path');
const {chromium} = require('playwright');

const args = {scenario: 'offline', width: 1400, height: 900};
for (let i = 2; i < process.argv.length; i++) {
  const k = process.argv[i].replace(/^--/, '');
  if (k === 'check') args.check = true; else args[k] = process.argv[++i];
}
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64');
const SERVERS = {carto: /basemaps\.cartocdn\.com/, esri: /server\.arcgisonline\.com/, osm: /tile\.openstreetmap\.org/};
const ANSWER = {  // scenario -> server -> 'ok' | 'abort' | 403
  A: {carto: 'ok', esri: 'abort', osm: 'abort'},
  B: {carto: 'abort', esri: 'ok', osm: 'abort'},
  C: {carto: 'abort', esri: 'abort', osm: 403},
  D: {carto: 'ok', esri: 'ok', osm: 'ok'},
  offline: {carto: 'abort', esri: 'abort', osm: 'abort'},
};

(async () => {
  const out = {errors: [], tiles: {carto: 0, esri: 0, osm: 0}};
  const browser = await chromium.launch();
  const page = await browser.newPage({viewport: {width: +args.width, height: +args.height}});
  page.on('pageerror', e => out.errors.push('pageerror: ' + e.message));
  page.on('console', m => {
    if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) out.errors.push('console: ' + m.text());
  });
  await page.route('**/*', route => {
    const url = route.request().url();
    if (url.startsWith('file:')) return route.continue();
    const lib = /cdnjs\.cloudflare\.com\/ajax\/libs\/leaflet\/1\.9\.4\/(leaflet)(\.min)?\.(js|css)$/.exec(url);
    if (lib) {
      const file = path.join(args.leaflet, 'leaflet.' + lib[3]);
      return route.fulfill({body: fs.readFileSync(file), contentType: lib[3] === 'js' ? 'application/javascript' : 'text/css'});
    }
    for (const [name, re] of Object.entries(SERVERS)) {
      if (!re.test(url)) continue;
      out.tiles[name]++;
      const how = ANSWER[args.scenario][name];
      if (how === 'ok') return route.fulfill({body: PNG, contentType: 'image/png'});
      if (how === 403) return route.fulfill({status: 403, body: 'Referer required'});
      return route.abort();
    }
    return route.abort();  // fonts and anything else: no network
  });
  await page.goto('file://' + path.resolve(args.page));
  await page.waitForTimeout(1500);
  const ours = await page.evaluate(() => !!(window.hubsPage || window.missingMap));
  if (ours) {
    const want = {A: 'carto', B: 'esri', C: 'none', D: 'carto', offline: 'none'}[args.scenario];
    await page.waitForFunction(w => document.getElementById('map').getAttribute('data-basemap') === w, want, {timeout: 8000})
      .catch(() => {});
    if (args.scenario === 'D') {
      await page.selectOption('#basemap', '2');
      await page.waitForTimeout(800);
    }
    out.basemap = await page.evaluate(() => document.getElementById('map').getAttribute('data-basemap'));
    out.note = await page.evaluate(() => document.getElementById('basemap-note').textContent);
    out.noteRole = await page.evaluate(() => document.getElementById('basemap-note').getAttribute('role'));
    out.osmLayer = await page.evaluate(() => !!document.querySelector('.leaflet-tile-pane .osm-gray'));
  }
  if (args.shot) await page.screenshot({path: args.shot});
  const missing = await page.evaluate(() => !!window.missingMap);
  if (ours && args.check) Object.assign(out, missing ? await checkMissing(page) : await check(page));
  await browser.close();
  console.log(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });

async function check(page) {
  const res = await page.evaluate(() => {
    const P = window.hubsPage, map = P.map, r = {counts: {}, drawn: {}, toggles: {}, popups: {}, tooltips: {}};
    const isTie = l => l instanceof L.Polyline;
    Object.keys(P.groups).forEach(k => {
      const g = P.groups[k], layers = g.getLayers();
      r.counts[k] = document.getElementById('cnt-' + k).textContent;
      r.drawn[k] = k === 'both' && layers.some(l => l instanceof L.CircleMarker) ? layers.filter(isTie).length : layers.length;
      const box = document.getElementById('set-' + k), before = map.hasLayer(g);
      box.click(); const mid = map.hasLayer(g); box.click(); const after = map.hasLayer(g);
      r.toggles[k] = before === box.checked && mid === !before && after === before;
      const withPopup = layers.find(l => l.getPopup && l.getPopup());
      if (withPopup) {
        if (!map.hasLayer(g)) g.addTo(map);
        withPopup.openPopup(withPopup.getLatLng ? withPopup.getLatLng() : withPopup.getBounds().getCenter());
        const all = document.querySelectorAll('.leaflet-popup-content .pp');
        const el = all[all.length - 1];
        r.popups[k] = el ? el.innerText : null;
        map.closePopup();
        if (!box.checked) map.removeLayer(g);
        const t = withPopup.getTooltip && withPopup.getTooltip();
        if (t) { const d = document.createElement('div'); d.innerHTML = t.getContent(); r.tooltips[k] = d.innerText; }
      }
    });
    r.panel = document.getElementById('panel').innerText;
    r.title = document.title;
    const sel = document.getElementById('pick-line');
    if (sel && sel.options.length > 1) {
      sel.value = sel.options[1].value; sel.dispatchEvent(new Event('change'));
      const all = Object.values(P.groups).flatMap(g => g.getLayers()).filter(l => l._op);
      r.pickDimmed = all.filter(l => l.options.opacity === 0.08).length;
      r.pickOn = all.filter(l => l.options.opacity !== 0.08).length;
      sel.value = ''; sel.dispatchEvent(new Event('change'));
      r.pickRestored = all.every(l => l.options.opacity === l._op);
      const st = document.getElementById('pick-status');
      r.statusOptions = Array.from(st.options).map(o => o.textContent);
      r.lineOptions = Array.from(sel.options).slice(0, 4).map(o => o.textContent);
      st.value = st.options[1] ? st.options[1].value : ''; st.dispatchEvent(new Event('change'));
      r.statusDimmed = all.filter(l => l.options.opacity === 0.08).length;
      st.value = ''; st.dispatchEvent(new Event('change'));
    }
    r.basemapOptions = Array.from(document.getElementById('basemap').options).map(o => o.textContent);
    return r;
  });
  res.cities = {};
  await page.waitForTimeout(1200);  // a zoom animation still running would swallow a setView
  for (const id of ['btn-tlv', 'btn-hfa', 'btn-jlm', 'btn-bsh', 'btn-fit']) {
    await page.click('#' + id);
    await page.waitForTimeout(1200);
    res.cities[id] = await page.evaluate(() => {
      const m = window.hubsPage.map, c = m.getCenter();
      return [+c.lat.toFixed(2), +c.lng.toFixed(2), m.getZoom()];
    });
  }
  return res;
}

// The missing-lines-and-hubs page (scripts/build_missing_map.py): one popup and tooltip per set.
async function checkMissing(page) {
  return page.evaluate(() => {
    const M = window.missingMap, map = M.map, r = {popups: {}, tooltips: {}, counts: {}, drawn: {}};
    Object.keys(M.groups).forEach(set => {
      r.counts[set] = document.getElementById('cnt-' + set).dataset.n;
      r.drawn[set] = M.drawnCount(set);
      const f = M.features.find(x => x.s === set);
      if (!f) return;
      const layer = M.layerById[f.id], wasOn = map.hasLayer(M.groups[set]);
      M.groups[set].addTo(map);
      layer.openPopup(layer.getBounds().getCenter());
      const all = document.querySelectorAll('.leaflet-popup-content .pp');
      r.popups[set] = all.length ? all[all.length - 1].innerText : null;
      map.closePopup();
      const t = layer.getTooltip();
      if (t) { const c = t.getContent(); r.tooltips[set] = typeof c === 'function' ? c(layer).textContent : String(c); }
      if (!wasOn) map.removeLayer(M.groups[set]);
    });
    r.panel = document.getElementById('panel').innerText;
    r.title = document.title;
    return r;
  });
}
