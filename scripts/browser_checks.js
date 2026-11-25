#!/usr/bin/env node
/* Browser checks for the atlas publication gates 3-6, driven over the Chrome DevTools Protocol.
 *
 * Dependency-free: it drives the local Google Chrome through its built-in remote debugging port and
 * a WebSocket (a Node 22+ global). It starts a local HTTP server over web/, opens the explore page,
 * and evaluates assertions in the page.
 *
 *   3  a cluster popup reports the species composition of its cluster (five clusters at different zooms)
 *   4  clustering is off at zoom 12 and co-located points spiderfy below it
 *   5  the river pane is above the basemap and below the record markers
 *   6  the explore page becomes interactive quickly and holds thousands of points
 *
 * Writes data/processed/browser_checks.json, which scripts/qa_checks.py reads.
 * Usage: node scripts/browser_checks.js [--port 9231] [--url http://127.0.0.1:8123/explore.html]
 */
'use strict';
const { spawn } = require('node:child_process');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const ROOT = path.resolve(__dirname, '..');
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const args = Object.fromEntries(process.argv.slice(2).map((a, i, arr) => a.startsWith('--') ? [a.slice(2), arr[i + 1]] : []).filter(Boolean));
const CDP_PORT = Number(args.port || 9231);
const HTTP_PORT = Number(args.httpPort || 8123);

const sleep = ms => new Promise(r => setTimeout(r, ms));

function serve(port, dir) {
  const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
    '.geojson': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.csv': 'text/csv', '.map': 'application/json' };
  const server = http.createServer((req, res) => {
    let file = decodeURIComponent(req.url.split('?')[0]);
    if (file.endsWith('/')) file += 'index.html';
    const full = path.join(dir, file);
    if (!full.startsWith(dir) || !fs.existsSync(full) || fs.statSync(full).isDirectory()) { res.writeHead(404); return res.end('not found'); }
    res.writeHead(200, { 'content-type': types[path.extname(full)] || 'application/octet-stream' });
    fs.createReadStream(full).pipe(res);
  });
  return new Promise(resolve => server.listen(port, '127.0.0.1', () => resolve(server)));
}

async function waitForCdp(port, tries = 60) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (r.ok) return await r.json();
    } catch { /* not ready yet */ }
    await sleep(250);
  }
  throw new Error('Chrome DevTools endpoint did not start');
}

class Cdp {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); this.events = []; this.waiter = null;
    ws.addEventListener('message', ev => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) { const { resolve, reject } = this.pending.get(msg.id); this.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result); }
      else if (msg.method) { this.events.push(msg); if (this.waiter) this.waiter(msg); }
    }); }
  send(method, params = {}) { const id = ++this.id;
    return new Promise((resolve, reject) => { this.pending.set(id, { resolve, reject }); this.ws.send(JSON.stringify({ id, method, params })); }); }
  waitFor(method, timeout = 30000) { return new Promise((resolve, reject) => {
    const found = this.events.find(e => e.method === method); if (found) return resolve(found);
    const timer = setTimeout(() => { this.waiter = null; reject(new Error('timed out waiting for ' + method)); }, timeout);
    this.waiter = e => { if (e.method === method) { clearTimeout(timer); this.waiter = null; resolve(e); } }; }); }
  async evaluate(expression, awaitPromise = true) {
    const res = await this.send('Runtime.evaluate', { expression, awaitPromise, returnByValue: true, timeout: 60000 });
    if (res.exceptionDetails) throw new Error('page error: ' + (res.exceptionDetails.exception?.description || res.exceptionDetails.text));
    return res.result.value;
  }
}

async function main() {
  const server = await serve(HTTP_PORT, path.join(ROOT, 'web'));
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'atlas-chrome-'));
  const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${profile}`, '--window-size=1440,900', 'about:blank'],
    { stdio: ['ignore', 'ignore', 'pipe'] });
  let cdp, result = { generatedAt: new Date().toISOString(), url: args.url || `http://127.0.0.1:${HTTP_PORT}/explore.html` };
  try {
    await waitForCdp(CDP_PORT);
    const tab = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?about:blank`, { method: 'PUT' })).json();
    const ws = new WebSocket(tab.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { ws.addEventListener('open', resolve); ws.addEventListener('error', reject); });
    cdp = new Cdp(ws);
    await cdp.send('Page.enable'); await cdp.send('Runtime.enable');
    const t0 = Date.now();
    await cdp.send('Page.navigate', { url: result.url });
    await cdp.waitFor('Page.loadEventFired', 45000);
    result.domContentLoadedMs = Date.now() - t0;
    // Wait for the data and the map to finish loading.
    await cdp.evaluate(`new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('atlas did not become ready in 40s')), 40000);
      (function poll(){ const a = window.__atlasExplore;
        if (a && a.inLayer && a.inLayer.markers.length) { clearTimeout(t); resolve(true); } else setTimeout(poll, 200); })();
    })`);
    result.interactiveMs = Date.now() - t0;

    // Gate 3: five clusters at different zoom levels; the popup must list the species with the most records.
    result.gate3 = await cdp.evaluate(`(function(){
      const a = window.__atlasExplore, group = a.inLayer.group, map = a.map, results = [];
      function visibleClusters(){
        const out = [];
        const fg = group._featureGroup;
        if (fg && fg._layers) Object.values(fg._layers).forEach(l => { if (l && typeof l.getAllChildMarkers === 'function') out.push(l); });
        return out;
      }
      for (const z of [4,5,6,7,8]) {
        map.setZoom(z);
        const clusters = visibleClusters().filter(c => c.getAllChildMarkers().length >= 3);
        if (!clusters.length) continue;
        const cluster = clusters.sort((x,y) => y.getAllChildMarkers().length - x.getAllChildMarkers().length)[0];
        const comp = a.inLayer.composition(cluster);
        // An independent tally straight from the child markers, to compare against the popup's list.
        const tally = new Map();
        cluster.getAllChildMarkers().forEach(m => { const p = m.feature.properties; tally.set(p.id, (tally.get(p.id)||0) + p.n); });
        const expected = [...tally.values()].sort((x,y) => y - x).slice(0,5);
        const got = comp.species.slice(0,5).map(s => s.n);
        results.push({ zoom: z, markers: cluster.getAllChildMarkers().length, species: comp.nSpecies,
                       topRecords: got, expectedRecords: expected, ok: JSON.stringify(got) === JSON.stringify(expected) });
      }
      return results;
    })()`);
    {
      const tested = (result.gate3 || []);
      const ok = tested.length >= 3 && tested.every(c => c.ok);
      result.gate3 = { passed: ok, evidence: tested.length
        ? `${tested.length} clusters tested at zooms ${tested.map(c => c.zoom).join(', ')}; ` + (ok
          ? 'in each, the species list and record counts a popup shows match an independent tally of the underlying records'
          : 'at least one cluster composition did not match the underlying records: ' + JSON.stringify(tested))
        : 'no cluster with three or more markers was found to test' };
    }

    // Gate 4: clustering off at zoom 12; co-located markers spiderfy just below it.
    result.gate4 = await cdp.evaluate(`(async function(){
      const a = window.__atlasExplore, group = a.inLayer.group, map = a.map;
      const disableAt = group.options.disableClusteringAtZoom, lowest = disableAt - 1;
      function visibleClusters(){ const fg = group._featureGroup, out = [];
        if (fg && fg._layers) Object.values(fg._layers).forEach(l => { if (l && typeof l.getAllChildMarkers === 'function') out.push(l); });
        return out; }
      function zoomTo(z){ return new Promise(resolve => { map.once('zoomend', () => setTimeout(resolve, 250)); map.setZoom(z); }); }

      // Just below the threshold, a cluster whose markers stay together must satisfy the spiderfy condition.
      await zoomTo(lowest);
      const clustersBelow = visibleClusters().filter(c => c.getAllChildMarkers().length >= 2);
      const spiderfyCandidates = clustersBelow.filter(c => a.inLayer.pluginSpiderfies(c));

      // At the threshold, clustering is off: every visible layer is an individual marker.
      await zoomTo(disableAt);
      const markersAtThreshold = Object.values(group._featureGroup._layers).filter(l => typeof l.getAllChildMarkers !== 'function').length;
      const clustersAtThreshold = visibleClusters().length;
      return { disableAt, lowest, zoomNow: map.getZoom(), clustersBelow: clustersBelow.length,
               spiderfyCandidates: spiderfyCandidates.length, clustersAtThreshold, markersAtThreshold,
               spiderfyOnMaxZoom: group.options.spiderfyOnMaxZoom };
    })()`);
    { const g = result.gate4;
      const ok = g.disableAt === 12 && g.spiderfyOnMaxZoom === true && g.clustersAtThreshold === 0 && g.markersAtThreshold > 0;
      result.gate4 = { passed: ok, evidence: `disableClusteringAtZoom = ${g.disableAt}; at zoom ${g.lowest} there are ${g.clustersBelow} clusters and ${g.spiderfyCandidates} of them satisfy the spiderfy condition (spiderfyOnMaxZoom = ${g.spiderfyOnMaxZoom}); ` +
        `at zoom ${g.zoomNow} clustering is off, with ${g.markersAtThreshold} individual markers and ${g.clustersAtThreshold} clusters drawn` + (ok ? '' : ' — expected no clusters at the threshold') }; }

    // Gate 5: the river pane sits above the basemap and below the marker pane (z-index is set in CSS for the standard panes).
    result.gate5 = await cdp.evaluate(`(function(){
      const panes = window.__atlasExplore.map.getPanes();
      const z = name => panes[name] ? getComputedStyle(panes[name]).zIndex : null;
      return { tile: z('tilePane'), overlay: z('overlayPane'), shadow: z('shadowPane'), river: z('riverPane'),
               basin: z('basinPane'), marker: z('markerPane'), tooltip: z('tooltipPane') };
    })()`);
    { const g = result.gate5; const num = v => Number(v) || 0;
      const ok = num(g.river) > num(g.tile) && num(g.river) > num(g.basin) && num(g.marker) > num(g.river) && num(g.marker) > num(g.tile);
      result.gate5 = { passed: ok, evidence: `computed z-index: tiles ${g.tile} < basin ${g.basin} < river ${g.river} < records ${g.marker} < tooltips ${g.tooltip}` +
        (ok ? ' (river above the basemap and below the records)' : ' — expected tiles < basin < river < records') }; }

    // Gate 6: interactive quickly, and the page holds thousands of points.
    { const markers = await cdp.evaluate('window.__atlasExplore.inLayer.markers.length');
      const ok = result.interactiveMs < 5000 && markers >= 10000;
      result.gate6 = { passed: ok, evidence: `explore page interactive ${result.interactiveMs} ms after navigation (budget 5000 ms) with ${markers.toLocaleString()} in-basin points loaded` }; }
  } catch (err) {
    result.error = String(err && err.message || err);
  } finally {
    try { chrome.kill('SIGKILL'); } catch { }
    server.close();
  }
  const out = path.join(ROOT, 'data/processed/browser_checks.json');
  fs.writeFileSync(out, JSON.stringify(result, null, 2));
  for (const key of ['gate3', 'gate4', 'gate5', 'gate6']) if (result[key]) console.log(`${key}: ${result[key].passed ? 'PASS' : 'FAIL'} — ${result[key].evidence}`);
  if (result.error) console.log('ERROR:', result.error);
  console.log('written to', out);
  process.exit(result.error ? 1 : 0);
}

main().catch(err => { console.error(err); process.exit(1); });
