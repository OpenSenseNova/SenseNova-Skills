import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, basename, extname } from 'node:path';
import { get } from 'node:https';
import { get as httpGet } from 'node:http';

const URL_RE = /((?:src|url)\s*[=:]\s*)(["']?)(https?:\/\/[^"'\>\s\)]+)\2/g;

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
  return allowed.includes(ext) ? safe : safe + '.jpg';
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
    const matches = [...content.matchAll(URL_RE)];
    if (!matches.length) continue;

    const seen = new Map(); // url -> relativePath
    for (const m of matches) {
      const url = m[3];
      if (seen.has(url)) continue;

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
      const pattern = new RegExp(`((?:src|url)\\s*[=:]\\s*)(["']?)${escaped}\\2`, 'g');
      content = content.replace(pattern, `$1$2${rel}$2`);
    }

    writeFileSync(htmlPath, content, 'utf-8');
  }
}
