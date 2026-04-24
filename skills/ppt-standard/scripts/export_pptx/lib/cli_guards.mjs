import { existsSync, readdirSync, readFileSync, renameSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

function readJsonIfExists(filePath) {
  if (!existsSync(filePath)) {
    return null;
  }
  try {
    return JSON.parse(readFileSync(filePath, 'utf-8'));
  } catch (e) {
    process.stderr.write(`[WARN] 无法解析 ${filePath}，跳过校验: ${e.message}\n`);
    return null;
  }
}

function parsePageNumberFromFile(htmlFile) {
  const fileName = htmlFile.split('/').pop() || '';
  return Number((/page_(\d+)\.html$/.exec(fileName) || [])[1]);
}

function listRealPhotoRequirements(page) {
  return (page?.asset_requirements || [])
    .filter(item => typeof item === 'string')
    .map(item => item.trim())
    .filter(item => /^real-photo\s*:/i.test(item))
    .map(item => item.replace(/^real-photo\s*:/i, '').trim())
    .filter(Boolean);
}

function listExplicitPlaceholders(html) {
  return [...html.matchAll(/\[\s*([^\]\n]{2,120})\s*\]/g)].map(match => match[1].trim());
}

function collectMotifMarkers(html) {
  const markers = {
    'bg-motif': new Set(),
    'fg-motif': new Set(),
  };
  const tags = html.match(/<[^>]+>/g) || [];
  for (const tag of tags) {
    const layerMatch = /data-layer\s*=\s*(?:"([^"]+)"|'([^']+)')/.exec(tag);
    const motifMatch = /data-motif-key\s*=\s*(?:"([^"]+)"|'([^']+)')/.exec(tag);
    const layer = layerMatch?.[1] || layerMatch?.[2];
    const motifKey = motifMatch?.[1] || motifMatch?.[2];
    if (!layer || !motifKey) {
      continue;
    }
    if (layer === 'bg-motif' || layer === 'fg-motif') {
      markers[layer].add(motifKey);
    }
  }
  return markers;
}

function ensureReviewArtifact(deckDir, opts = {}) {
  const reviewMd = resolve(deckDir, 'review.md');
  const reviewJson = resolve(deckDir, 'review.json');
  const hasReviewMd = existsSync(reviewMd);
  const hasReviewJson = existsSync(reviewJson);

  if (!hasReviewMd && !hasReviewJson) {
    if (opts.force) {
      process.stderr.write('[WARN] 缺少 review 工件，但 --force 已设置，继续导出\n');
      return;
    }
    throw new Error('缺少 review 工件：必须先生成 review.md 或 review.json，才能继续导出');
  }

  let isBlocked = false;

  if (hasReviewJson) {
    const review = readJsonIfExists(reviewJson);
    const markers = [
      review?.status,
      review?.result,
      review?.decision,
      review?.summary,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    if (/(block|blocked|fail|failed|reject|rejected|needs-fix|needs_fix)/.test(markers)) {
      isBlocked = true;
    }
  }

  if (hasReviewMd && !isBlocked) {
    const reviewText = readFileSync(reviewMd, 'utf-8');
    if (
      /status:\s*(block|blocked|fail|failed|reject|rejected)/i.test(reviewText) ||
      /阻塞|不可交付|不能直接交付/.test(reviewText)
    ) {
      isBlocked = true;
    }
  }

  if (isBlocked) {
    if (opts.force) {
      process.stderr.write('[WARN] review 标记为阻塞，但 --force 已设置，继续导出\n');
      return;
    }
    throw new Error('review 标记为阻塞，必须先修复 review 中的问题，不能继续导出');
  }
}

function parseTag(tag) {
  const closeMatch = /^<\s*\/\s*([a-zA-Z0-9:-]+)/.exec(tag);
  if (closeMatch) {
    return {
      type: 'close',
      name: closeMatch[1].toLowerCase(),
    };
  }

  const openMatch = /^<\s*([a-zA-Z0-9:-]+)/.exec(tag);
  if (!openMatch) {
    return null;
  }

  const idMatch = /\bid\s*=\s*(?:"([^"]+)"|'([^']+)')/.exec(tag);
  const classMatch = /\bclass\s*=\s*(?:"([^"]+)"|'([^']+)')/.exec(tag);
  return {
    type: 'open',
    name: openMatch[1].toLowerCase(),
    id: idMatch?.[1] || idMatch?.[2] || '',
    classList: (classMatch?.[1] || classMatch?.[2] || '')
      .split(/\s+/)
      .filter(Boolean),
    selfClosing: /\/\s*>$/.test(tag),
  };
}

function inspectTitlePlacement(html) {
  const tags = html.match(/<[^>]+>/g) || [];
  const stack = [];
  let titleInsideCt = false;
  let titleInsideHeader = false;
  let misplacedHeaderWithTitle = false;

  for (const tag of tags) {
    const parsed = parseTag(tag);
    if (!parsed) {
      continue;
    }

    if (parsed.type === 'close') {
      for (let i = stack.length - 1; i >= 0; i--) {
        const node = stack[i];
        stack.pop();
        if (node.name === parsed.name) {
          break;
        }
      }
      continue;
    }

    const insideCt = stack.some(node => node.id === 'ct');
    const insideHeader = stack.some(node => node.id === 'header');
    const insideLooseHeader = stack.some(
      node => node.id !== 'header' && node.classList.includes('header'),
    );
    const isHeading = /^h[1-6]$/.test(parsed.name);

    if (isHeading) {
      if (insideCt) {
        titleInsideCt = true;
      }
      if (insideHeader) {
        titleInsideHeader = true;
      }
      if (!insideCt && !insideHeader && insideLooseHeader) {
        misplacedHeaderWithTitle = true;
      }
    }

    if (!parsed.selfClosing) {
      stack.push(parsed);
    }
  }

  return {
    titleInsideCt,
    titleInsideHeader,
    misplacedHeaderWithTitle,
  };
}

function shouldRequireVisibleTitle(variant) {
  const strategy = String(variant?.header_strategy || '').toLowerCase();
  if (!strategy) {
    return false;
  }
  return !/(hidden|none|no-header|no_header|titleless)/.test(strategy);
}

function ensureVisibleTitles(deckDir, htmlFiles, opts = {}) {
  const styleSpec = readJsonIfExists(resolve(deckDir, 'style-spec.json'));
  const storyboard = readJsonIfExists(resolve(deckDir, 'storyboard.json'));
  if (!styleSpec || !storyboard) {
    return;
  }

  const variants = new Map(
    (styleSpec.page_type_variants || []).map(variant => [variant.variant_key, variant]),
  );
  const pages = new Map(
    (storyboard.pages || []).map(page => [Number(page.page_number), page]),
  );
  const errors = [];

  for (const htmlFile of htmlFiles) {
    const fileName = htmlFile.split('/').pop() || '';
    const pageNumber = Number((/page_(\d+)\.html$/.exec(fileName) || [])[1]);
    const page = pages.get(pageNumber);
    if (!page) {
      continue;
    }
    const variant = variants.get(page.style_variant);
    if (!shouldRequireVisibleTitle(variant)) {
      continue;
    }

    const html = readFileSync(htmlFile, 'utf-8');
    const titleCheck = inspectTitlePlacement(html);

    if (titleCheck.misplacedHeaderWithTitle) {
      errors.push(
        `${fileName} 的标题落在错误层级：不要把 .header 放在 #bg 和 #ct 之间；可见标题必须放在 #ct 内或单独的 #header 内`,
      );
      continue;
    }

    if (!titleCheck.titleInsideCt && !titleCheck.titleInsideHeader) {
      errors.push(
        `${fileName} 缺少可见标题：可见标题必须放在 #ct 内或单独的 #header 内，避免只在源码里存在却被内容层盖住`,
      );
    }
  }

  if (errors.length > 0) {
    if (opts.force) {
      process.stderr.write(`[WARN] 页面标题层级校验未通过，但 --force 已设置，继续导出:\n- ${errors.join('\n- ')}\n`);
      return;
    }
    throw new Error(`页面标题层级校验失败:\n- ${errors.join('\n- ')}`);
  }
}

function ensureRealPhotoCoverage(deckDir, htmlFiles, opts = {}) {
  const storyboard = readJsonIfExists(resolve(deckDir, 'storyboard.json'));
  if (!storyboard) {
    return;
  }

  const assetPlan = readJsonIfExists(resolve(deckDir, 'asset-plan.json'));
  const slots = Array.isArray(assetPlan?.slots) ? assetPlan.slots : [];
  const pages = new Map(
    (storyboard.pages || []).map(page => [Number(page.page_number), page]),
  );
  const errors = [];

  for (const htmlFile of htmlFiles) {
    const fileName = htmlFile.split('/').pop() || '';
    const pageNumber = parsePageNumberFromFile(htmlFile);
    const page = pages.get(pageNumber);
    if (!page) {
      continue;
    }

    const requiredRealPhotos = listRealPhotoRequirements(page);
    if (requiredRealPhotos.length === 0) {
      continue;
    }

    const pageSlots = slots.filter(slot => slot?.page_id === page.page_id && slot?.asset_kind === 'real-photo');
    const resolvedSlots = pageSlots.filter(
      slot => slot?.selected === true && slot?.status === 'success' && slot?.selected_image?.local_path,
    );
    const unresolvedSlots = pageSlots.filter(
      slot => slot?.status === 'unresolved' || slot?.selected === false || !slot?.selected_image?.local_path,
    );

    if (resolvedSlots.length < requiredRealPhotos.length) {
      errors.push(
        `${fileName} 的必需真实图片未补齐：storyboard 需要 ${requiredRealPhotos.length} 个 real-photo 槽位，但 asset-plan 仅落实 ${resolvedSlots.length} 个`,
      );
    }

    if (unresolvedSlots.length > 0) {
      errors.push(
        `${fileName} 仍存在未兑现的 real-photo 槽位：${unresolvedSlots.map(slot => slot.slot_id || 'unknown-slot').join(', ')}`,
      );
    }

    const html = readFileSync(htmlFile, 'utf-8');
    const placeholders = listExplicitPlaceholders(html);
    if (placeholders.length > 0) {
      errors.push(
        `${fileName} 仍包含明显媒体 placeholder：${placeholders.join('、')}；必需真实图片未补齐时不得继续导出`,
      );
    }
  }

  if (errors.length > 0) {
    if (opts.force) {
      process.stderr.write(`[WARN] 页面真实图片校验未通过，但 --force 已设置，继续导出:\n- ${errors.join('\n- ')}\n`);
      return;
    }
    throw new Error(`页面真实图片校验失败:\n- ${errors.join('\n- ')}`);
  }
}

function ensureDecorativeMarkers(deckDir, htmlFiles) {
  const styleSpec = readJsonIfExists(resolve(deckDir, 'style-spec.json'));
  const storyboard = readJsonIfExists(resolve(deckDir, 'storyboard.json'));
  if (!styleSpec || !storyboard) {
    return;
  }

  const variants = new Map(
    (styleSpec.page_type_variants || []).map(variant => [variant.variant_key, variant]),
  );
  const pages = new Map(
    (storyboard.pages || []).map(page => [Number(page.page_number), page]),
  );
  const warnings = [];

  for (const htmlFile of htmlFiles) {
    const fileName = htmlFile.split('/').pop() || '';
    const pageNumber = Number((/page_(\d+)\.html$/.exec(fileName) || [])[1]);
    const page = pages.get(pageNumber);
    if (!page) {
      continue;
    }
    const variant = variants.get(page.style_variant);
    if (!variant) {
      continue;
    }

    const html = readFileSync(htmlFile, 'utf-8');
    const markers = collectMotifMarkers(html);
    const checks = [
      ['bg-motif', variant.background_motif_recipe || []],
      ['fg-motif', variant.foreground_motif_recipe || []],
    ];

    for (const [layer, recipe] of checks) {
      if (!Array.isArray(recipe) || recipe.length === 0) {
        continue;
      }
      const oppositeLayer = layer === 'bg-motif' ? 'fg-motif' : 'bg-motif';
      if (markers[layer].size === 0) {
        const crossLayerMatches = recipe
          .map(item => item?.motif_key)
          .filter(Boolean)
          .filter(motifKey => markers[oppositeLayer].has(motifKey));
        if (crossLayerMatches.length > 0) {
          warnings.push(
            `${fileName} 的 ${crossLayerMatches.join('、')} 落在 ${oppositeLayer} 而非 ${layer}；按降级模式继续导出`,
          );
        } else {
          warnings.push(
            `${fileName} 缺少 ${layer} 标记；recipe 仅作装饰性校验，按降级模式继续导出`,
          );
        }
        continue;
      }
      for (const item of recipe) {
        const motifKey = item?.motif_key;
        if (!motifKey) {
          continue;
        }
        if (!markers[layer].has(motifKey)) {
          if (markers[oppositeLayer].has(motifKey)) {
            warnings.push(
              `${fileName} 的 ${motifKey} 落在 ${oppositeLayer} 而非 ${layer}；按降级模式继续导出`,
            );
          } else {
            warnings.push(
              `${fileName} 缺少 data-layer="${layer}" data-motif-key="${motifKey}"；recipe 仅作装饰性校验，按降级模式继续导出`,
            );
          }
        }
      }
    }
  }

  if (warnings.length > 0) {
    process.stderr.write(`警告: 页面装饰层校验未完全通过，继续导出:\n- ${warnings.join('\n- ')}\n`);
  }
}

/**
 * 规范化 deck 目录结构：确保 page_*.html 位于 pages/ 子目录下。
 * 如果 HTML 文件直接在 deckDir 下，则创建 pages/ 并移动文件，
 * 同时重写文件内的相对资源路径（src / url(...)）。
 */
function normalizeDeckPages(deckDir) {
  const pagesDir = resolve(deckDir, 'pages');
  if (existsSync(pagesDir)) {
    return;
  }

  const files = readdirSync(deckDir).filter(f => /^page_\d+\.html$/.test(f));
  if (files.length === 0) {
    return;
  }

  mkdirSync(pagesDir, { recursive: true });

  for (const file of files) {
    const srcPath = resolve(deckDir, file);
    const destPath = resolve(pagesDir, file);
    let content = readFileSync(srcPath, 'utf-8');

    // 将相对资源路径提升一级（因为文件从 deckDir 移到了 pages/）
    const attrPattern = /(src|href)\s*=\s*["']([^"']+)["']/g;
    const urlPattern = /url\((["']?)([^"')]+)\1\)/g;

    const rewrite = (match, p1, p2) => {
      const val = p2;
      if (
        val.startsWith('http://') ||
        val.startsWith('https://') ||
        val.startsWith('/') ||
        val.startsWith('data:') ||
        val.startsWith('#') ||
        val.startsWith('../')
      ) {
        return match;
      }
      return match.replace(val, `../${val}`);
    };

    content = content.replace(attrPattern, rewrite);
    content = content.replace(urlPattern, rewrite);

    writeFileSync(destPath, content, 'utf-8');
    // 不删除原文件，避免破坏其他引用
  }
}

export function ensureDeckPreconditions(deckDir, opts = {}) {
  if (!deckDir) {
    throw new Error('必须指定 --deck-dir 参数');
  }
  if (!existsSync(deckDir)) {
    throw new Error(`deck_dir 不存在: ${deckDir}`);
  }

  if (!opts.batch) {
    ensureReviewArtifact(deckDir, opts);
  }

  let pagesDir;
  if (opts.pagesDir) {
    pagesDir = opts.pagesDir;
  } else {
    normalizeDeckPages(deckDir);
    pagesDir = resolve(deckDir, 'pages');
  }

  if (!existsSync(pagesDir)) {
    throw new Error(`pages 目录不存在: ${pagesDir}`);
  }

  const htmlFiles = readdirSync(pagesDir)
    .filter(f => /^page_\d+\.html$/.test(f))
    .sort()
    .map(f => resolve(pagesDir, f));

  if (htmlFiles.length === 0) {
    throw new Error(`pages 目录中没有 page_*.html 文件: ${pagesDir}`);
  }

  if (!opts.batch) {
    ensureDecorativeMarkers(deckDir, htmlFiles);
    ensureVisibleTitles(deckDir, htmlFiles, opts);
    ensureRealPhotoCoverage(deckDir, htmlFiles, opts);
  }

  return {
    pagesDir,
    htmlFiles,
  };
}
