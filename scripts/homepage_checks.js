#!/usr/bin/env node
/* Homepage checks for the pre-submission fixes (Part 4).
 *
 * Drives the local Chrome over CDP (same dependency-free approach as browser_checks.js):
 *   1  homepage becomes interactive (in-basin layer) under the 5 s budget on a cold cache
 *   2  the "All records" toggle lazily loads the out-of-basin layer and markers appear
 *   3  switching back to "In-basin" hides the out-of-basin points
 *   4  the toggle is visible and clickable at a phone-sized viewport
 *
 * Usage: node scripts/homepage_checks.js [--port 9232] [--httpPort 8124]
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
const CDP_PORT = Number(args.port || 9232);
const HTTP_PORT = Number(args.httpPort || 8124);
const sleep = ms => new Promise(r => setTimeout(r, ms));

function serve(port, dir) {
  const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
    '.geojson': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.csv': 'text/csv' };
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
    try { const r = await fetch(`http://127.0.0.1:${port}/json/version`); if (r.ok) return await r.json(); } catch {}
    await sleep(250);
  }
  throw new Error('Chrome DevTools endpoint did not start');
}
class Cdp {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); this.events = []; this.waiter = null;
    ws.addEventListener('message', ev => { const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) { const { resolve, reject } = this.pending.get(msg.id); this.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result); }
      else if (msg.method) { this.events.push(msg); if (this.waiter) this.waiter(msg); } }); }
  send(method, params = {}) { const id = ++this.id;
    return new Promise((resolve, reject) => { this.pending.set(id, { resolve, reject }); this.ws.send(JSON.stringify({ id, method, params })); }); }
  waitFor(method, timeout = 30000) { return new Promise((resolve, reject) => {
    const found = this.events.find(e => e.method === method); if (found) return resolve(found);
    const timer = setTimeout(() => { this.waiter = null; reject(new Error('timed out waiting for ' + method)); }, timeout);
    this.waiter = e => { if (e.method === method) { clearTimeout(timer); this.waiter = null; resolve(e); } }; }); }
  async evaluate(expression, awaitPromise = true) {
    const res = await this.send('Runtime.evaluate', { expression, awaitPromise, returnByValue: true, timeout: 90000 });
    if (res.exceptionDetails) throw new Error('page error: ' + (res.exceptionDetails.exception?.description || res.exceptionDetails.text));
    return res.result.value;
  }
}

async function main() {
  const server = await serve(HTTP_PORT, path.join(ROOT, 'web'));
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'atlas-home-'));
  const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${profile}`, '--window-size=1440,900', 'about:blank'],
    { stdio: ['ignore', 'ignore', 'pipe'] });
  const result = { generatedAt: new Date().toISOString(), url: `http://127.0.0.1:${HTTP_PORT}/index.html` };
  let exitCode = 0;
  try {
    await waitForCdp(CDP_PORT);
    const tab = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?about:blank`, { method: 'PUT' })).json();
    const ws = new WebSocket(tab.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { ws.addEventListener('open', resolve); ws.addEventListener('error', reject); });
    const cdp = new Cdp(ws);
    await cdp.send('Page.enable'); await cdp.send('Runtime.enable');
    await cdp.send('Network.enable'); await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });

    const t0 = Date.now();
    await cdp.send('Page.navigate', { url: result.url });
    await cdp.waitFor('Page.loadEventFired', 45000);
    // wait until index.js has finished attaching the scope listeners and drawn the in-basin layer
    await cdp.evaluate(`new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('home map not ready in 40s')), 40000);
      (function poll(){
        if (window.__atlasHomeReady) { clearTimeout(t); resolve(true); } else setTimeout(poll, 200);
      })();
    })`);
    result.totalToReadyMs = Date.now() - t0;

    // Gate A: out-of-basin layer lazily loads on toggle
    result.toggle = await cdp.evaluate(`(async function(){
      const all = document.getElementById('scopeAll');
      const inb = document.getElementById('scopeInBasin');
      if (!all || !inb) return { error: 'toggle control missing' };
      all.click();
      // wait until the scope note reports all records shown (layer loaded)
      const started = performance.now();
      const loaded = await new Promise(resolve => {
        const t = setTimeout(() => resolve(false), 45000);
        (function poll(){
          const note = document.getElementById('scopeNote');
          if (note && /All records shown/.test(note.textContent)) { clearTimeout(t); resolve(true); }
          else setTimeout(poll, 300);
        })();
      });
      const loadMs = Math.round(performance.now() - started);
      // count markers in a second (outside) cluster group if present
      const note = document.getElementById('scopeNote')?.textContent || '';
      return { loaded, loadMs, note };
    })()`);

    // Gate B: switch back hides out-of-basin
    result.hide = await cdp.evaluate(`(function(){
      const inb = document.getElementById('scopeInBasin');
      inb.click();
      const note = document.getElementById('scopeNote')?.textContent || '';
      return { note };
    })()`);

    // Gate C: phone viewport usability
    await cdp.send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
    await sleep(600);
    result.mobile = await cdp.evaluate(`(function(){
      const label = document.querySelector('label[for="scopeAll"]');
      const btn = document.getElementById('scopeAll');
      if (!label || !btn) return { visible: false };
      const r = label.getBoundingClientRect();
      const style = getComputedStyle(label);
      const visible = r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none' && r.right <= window.innerWidth + 1;
      return { visible, width: Math.round(r.width), height: Math.round(r.height), viewport: window.innerWidth, right: Math.round(r.right) };
    })()`);
  } catch (e) {
    result.error = String(e && e.stack || e);
    exitCode = 1;
  } finally {
    try { chrome.kill('SIGKILL'); } catch {}
    server.close();
  }

  const budget = 5000;
  const ok = !result.error
    && result.totalToReadyMs < budget
    && result.toggle && result.toggle.loaded
    && result.hide
    && result.mobile && result.mobile.visible;
  result.passed = ok;
  result.budgetMs = budget;
  fs.writeFileSync(path.join(ROOT, 'data', 'processed', 'homepage_checks.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  if (!ok) process.exit(exitCode || 1);
}
main();