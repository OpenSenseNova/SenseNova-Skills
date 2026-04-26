import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, basename, extname } from 'node:path';
import { get } from 'node:https';
import { get as httpGet } from 'node:http';

// Only match image URLs in IMAGE contexts:
//   <img ... src="https://...">
//   style="... background-image: url(https://...)"
//   style="... background: url(https://...)"
// Explicitly NOT <script src="..."> / <link href="..."> — those are code/asset
// loads. We used to match any `src=...http...` which caused the converter to
// "download" the echarts.min.js CDN script as an image (silently renamed
// `.js` → `.js.jpg` by sanitizeName), breaking the ECharts runtime and
// nuking native-chart rebuild.
const IMG_SRC_RE = /(<img\b[^>]*\bsrc\s*=\s*)(["'])(https?:\/\/[^"'\>\s]+)\2/gi;
const CSS_URL_RE = /(background(?:-image)?\s*:\s*[^;"'>]*url\(\s*)(["']?)(https?:\/\/[^"'\>\s\)]+)\2(\s*\))/gi;

function sanitizeName(url) {
  let name;
  try {
    name = basename(new URL(url).pathname) || 'image';
  } catch {
    name = 'image';
  }
  const safe = name.replace(/[^\w\-\.]/g, '_');
  const ext = extname(safe).toLowerCase();
  const allowed = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp'];
  // Only append `.jpg` when the original has no extension at all; never
  // override a real extension like `.js` / `.css` (those shouldn't reach here
  // anyway now that the regex is image-context-only, but belt + suspenders).
  if (allowed.includes(ext)) return safe;
  if (!ext) return safe + '.jpg';
  return safe;  // keep whatever extension the URL had
}

function fetchBuffer(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https:') ? get : httpGet;
    client(url, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode}`));
        return;
      }
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks)));
    }).on('error', reject);
  });
}

export async function downloadRemoteImages(deckDir) {
  const pagesDir = resolve(deckDir, 'pages');
  if (!existsSync(pagesDir)) return;

  const htmlFiles = readdirSync(pagesDir).filter(f => /^page_\d+\.html$/.test(f));
  if (htmlFiles.length === 0) return;

  const imagesDir = resolve(deckDir, 'images');
  mkdirSync(imagesDir, { recursive: true });

  for (const file of htmlFiles) {
    const htmlPath = resolve(pagesDir, file);
    let content = readFileSync(htmlPath, 'utf-8');

    // Collect image URLs from both <img src=...http...> and CSS url(http...).
    const urls = new Set();
    for (const m of content.matchAll(IMG_SRC_RE)) urls.add(m[3]);
    for (const m of content.matchAll(CSS_URL_RE)) urls.add(m[3]);
    if (urls.size === 0) continue;

    const seen = new Map(); // url -> relativePath
    for (const url of urls) {
      let filename = sanitizeName(url);
      let localPath = resolve(imagesDir, filename);
      let counter = 1;
      const stem = filename.replace(extname(filename), '');
      const ext = extname(filename);
      while (existsSync(localPath)) {
        localPath = resolve(imagesDir, `${stem}_${counter}${ext}`);
        counter++;
      }

      try {
        const buf = await fetchBuffer(url);
        writeFileSync(localPath, buf);
        const rel = `../images/${basename(localPath)}`;
        seen.set(url, rel);
      } catch (e) {
        process.stderr.write(`[WARN] 下载远程图片失败 ${url}: ${e.message}\n`);
      }
    }

    for (const [url, rel] of seen) {
      const escaped = url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      // Rewrite only inside the same image contexts we scanned — don't touch
      // <script src> / <link href>.
      const imgPattern = new RegExp(`(<img\\b[^>]*\\bsrc\\s*=\\s*)(["'])${escaped}\\2`, 'gi');
      content = content.replace(imgPattern, `$1$2${rel}$2`);
      const cssPattern = new RegExp(`(background(?:-image)?\\s*:\\s*[^;"'>]*url\\(\\s*)(["']?)${escaped}\\2(\\s*\\))`, 'gi');
      content = content.replace(cssPattern, `$1$2${rel}$2$3`);
    }

    writeFileSync(htmlPath, content, 'utf-8');
  }
}
