// Capture a deterministic web page to MP4, frame by frame.
// The page must set window.READY = true when loaded and expose window.seek(t) (may return a Promise).
// usage: node capture.mjs PROJECT_DIR [--page index.html] [--fps 30] [--dur 12] [--size 1920x1080]
//                         [--out out/video.mp4] [--start 0] [--frames N] [--selector canvas] [--jpeg]
// Uses Playwright if installed, otherwise Puppeteer. Needs ffmpeg on PATH.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

const argv = process.argv.slice(2);
const dir = path.resolve(argv[0] || '.');
const opt = (k, d) => { const i = argv.indexOf('--' + k); return i < 0 ? d : (argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : true); };
const page_ = opt('page', 'index.html'), fps = +opt('fps', 30), [W, H] = String(opt('size', '1920x1080')).split('x').map(Number);
const out = path.resolve(dir, opt('out', 'out/video.mp4')), sel = opt('selector', null), jpeg = !!opt('jpeg', false);

const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml',
  '.ttf': 'font/ttf', '.otf': 'font/otf', '.woff': 'font/woff', '.woff2': 'font/woff2', '.wasm': 'application/wasm' };
const server = http.createServer((req, res) => {
  const p = path.join(dir, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(dir) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': types[path.extname(p).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const url = `http://127.0.0.1:${server.address().port}/${page_}`;

// Import from the project folder first, so a local node_modules is found.
const { createRequire } = await import('node:module');
const req = createRequire(path.join(dir, 'package.json'));
const load = async name => { try { return req(name); } catch { return import(name); } };
const glArgs = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'];
let browser, page, lib;
try { lib = await load('playwright'); } catch { lib = null; }
if (lib) {
  browser = await lib.chromium.launch({ args: glArgs });   // launch errors (missing system libs) surface here
  page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
} else {
  const puppeteer = (await load('puppeteer')).default;      // throws if neither is installed
  browser = await puppeteer.launch({ args: glArgs });
  page = await browser.newPage(); await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
}
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
await page.goto(url);
await page.waitForFunction(() => window.READY === true && typeof window.seek === 'function', null, { timeout: 120000 });
const dur = +opt('dur', 0) || await page.evaluate(() => window.DUR || 0);
if (!dur) throw new Error('give --dur or set window.DUR');
const start = +opt('start', 0), total = +opt('frames', 0) || Math.round(dur * fps) - start;

fs.mkdirSync(path.dirname(out), { recursive: true });
const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
  '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium', '-movflags', '+faststart', '-an', out],
  { stdio: ['pipe', 'inherit', 'inherit'] });
const target = sel ? await page.$(sel) : page;
const t0 = Date.now();
for (let i = start; i < start + total; i++) {
  await page.evaluate(async t => { await window.seek(t); }, i / fps);
  const buf = await target.screenshot(jpeg ? { type: 'jpeg', quality: 95 } : { type: 'png' });
  if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  if (errors.length) { console.error('page error at frame', i, errors); break; }
  if ((i - start) % fps === 0) process.stdout.write(`\rframe ${i - start + 1}/${total}  ${((Date.now() - t0) / (i - start + 1)).toFixed(0)} ms/frame`);
}
ff.stdin.end();
await new Promise(r => ff.on('close', r));
await browser.close(); server.close();
console.log(`\nwrote ${out}`);
if (errors.length) process.exit(1);
