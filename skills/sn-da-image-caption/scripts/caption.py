#!/usr/bin/env python3
"""
Image Caption Script — Generate text descriptions of images via vision LLM.

Standalone script for the sn-da-image-caption skill. Can be used directly
from the command line or imported as a module.

Features:
- Auto-detects image type (chart/table/UI/diagram/general) from filename + content heuristics
- Selects appropriate prompt per type
- Compresses large images (>5MB or >2048px longest side) via Pillow
- Caches results by image MD5 to avoid duplicate API calls
- Batch mode for processing entire directories
- Outputs plain text or structured JSON
- API key and model are pre-configured, no setup needed

Usage:
    python caption.py <image_path>
    python caption.py <image_path> --prompt "custom prompt"
    python caption.py <dir_path> --batch --output captions.json
    python caption.py <image_path> --json
"""

import argparse
import base64
import glob
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─── Constants ──────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024   # 5MB before compression
MAX_IMAGE_DIMENSION = 2048               # longest side after compression
JPEG_QUALITY = 75
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".caption_cache")

# ─── API settings (configure via environment variables) ─────────────
# Set VISION_API_KEY and VISION_API_BASE before use.
# VISION_API_BASE should point to an OpenAI-compatible endpoint.

DEFAULT_API_KEY = os.environ.get("VISION_API_KEY", "")
DEFAULT_API_BASE = os.environ.get("VISION_API_BASE", "https://api.openai.com/v1")
DEFAULT_MODEL = os.environ.get("VISION_MODEL", "gpt-4o")

# ─── Prompt templates ───────────────────────────────────────────────

PROMPTS = {
    "chart": (
        "这是一张数据图表。请精确提取以下信息：\n"
        "1. 图表标题\n"
        "2. X轴标签（所有类别/时间点）及单位\n"
        "3. Y轴标签及单位\n"
        "4. 每个数据点/柱/扇区的具体数值（保留原始精度）\n"
        "5. 图例名称（如有多系列）\n"
        "6. 整体趋势或关键发现\n"
        "请以 Markdown 表格格式输出数值数据。"
    ),
    "table": (
        "请精确提取图片中表格的所有内容。要求：\n"
        "1. 输出为 Markdown 表格格式\n"
        "2. 保持原始行列结构不变\n"
        "3. 数值保持原样，不四舍五入、不省略\n"
        "4. 如有合并单元格，展开并在每行重复填充\n"
        "5. 表头如有多级，用 / 分隔"
    ),
    "ui": (
        "请以前端开发者视角详细描述这个界面截图：\n"
        "1. 页面整体布局（header/sidebar/content/footer）\n"
        "2. 每个UI组件（按钮/表单/表格/导航/卡片）的位置和内容\n"
        "3. 文字内容（完整提取）\n"
        "4. 颜色主题和字体样式\n"
        "5. 间距和对齐关系"
    ),
    "diagram": (
        "请描述这张图的完整结构：\n"
        "1. 图的类型（流程图/架构图/思维导图/ER图/其他）\n"
        "2. 所有节点的名称和内容\n"
        "3. 节点之间的连接关系（A → B）和方向\n"
        "4. 分支条件（如有）\n"
        "5. 层级或分组关系\n"
        "6. 整体含义描述"
    ),
    "general": "请详细描述这张图片的内容，包括：主体对象、背景、文字信息、颜色和布局。如果包含文字请完整提取。",
}

# ─── Type detection keywords ────────────────────────────────────────

TYPE_KEYWORDS = {
    "chart": ["chart", "图表", "趋势", "柱状", "折线", "饼图", "散点", "bar", "line", "pie",
              "histogram", "可视化", "visualization", "plot", "graph"],
    "table": ["table", "表格", "excel", "整理", "提取", "data", "列表", "sheet"],
    "ui": ["ui", "截图", "screenshot", "界面", "页面", "网页", "app", "vue", "react",
           "html", "css", "前端", "layout", "设计稿"],
    "diagram": ["流程", "架构", "diagram", "flow", "架构图", "思维导图", "mindmap",
                "topology", "拓扑", "关系图", "er图"],
}


def detect_image_type(filename: str, context: str = "") -> str:
    """Detect image type from filename and optional context text."""
    combined = f"{filename} {context}".lower()
    scores = {t: 0 for t in TYPE_KEYWORDS}
    for img_type, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                scores[img_type] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def get_prompt(image_type: str, custom_prompt: Optional[str] = None) -> str:
    """Get the prompt for a given image type, or use custom."""
    if custom_prompt:
        return custom_prompt
    return PROMPTS.get(image_type, PROMPTS["general"])


# ─── Image processing ───────────────────────────────────────────────

def compute_md5(file_path: str) -> str:
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_and_compress(file_path: str) -> Tuple[str, str]:
    """Load image, compress if needed, return (base64_str, mime_type)."""
    from PIL import Image

    ext = Path(file_path).suffix.lower()
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    }
    mime = mime_map.get(ext, "image/png")

    file_size = os.path.getsize(file_path)
    img = Image.open(file_path)
    w, h = img.size
    needs_compress = file_size > MAX_IMAGE_SIZE_BYTES or max(w, h) > MAX_IMAGE_DIMENSION

    if needs_compress:
        # Resize
        if max(w, h) > MAX_IMAGE_DIMENSION:
            ratio = MAX_IMAGE_DIMENSION / max(w, h)
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        # Convert to RGB for JPEG
        if img.mode in ("RGBA", "P", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
            img = bg

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        mime = "image/jpeg"
    else:
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

    return b64, mime


# ─── Cache ───────────────────────────────────────────────────────────

def cache_get(md5: str, prompt_hash: str) -> Optional[str]:
    cache_file = os.path.join(CACHE_DIR, f"{md5}_{prompt_hash}.txt")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return f.read()
    return None


def cache_set(md5: str, prompt_hash: str, result: str):
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{md5}_{prompt_hash}.txt")
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(result)


# ─── API call ────────────────────────────────────────────────────────

def call_vision_api(
    b64_image: str,
    mime_type: str,
    prompt: str,
    model: str,
    api_key: str,
    api_base: str,
    max_tokens: int = 4096,
    max_retries: int = 3,
) -> dict:
    """Call the vision API and return {description, usage}."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=api_base)
    data_url = f"data:{mime_type};base64,{b64_image}"

    last_exc = None
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }],
                max_tokens=max_tokens,
            )
            text = resp.choices[0].message.content or ""
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
            }
            return {"description": text, "usage": usage}
        except Exception as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return {"description": f"Error: {last_exc}", "usage": {}}


# ─── Main functions ──────────────────────────────────────────────────

def caption_image(
    image_path: str,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    context: str = "",
    use_cache: bool = True,
) -> dict:
    """
    Caption a single image.

    Returns:
        {
            "file": str,
            "type": str,
            "description": str,
            "usage": {"prompt_tokens": int, "completion_tokens": int},
            "cached": bool,
        }
    """
    image_path = os.path.abspath(image_path)
    if not os.path.exists(image_path):
        return {"file": image_path, "error": f"File not found: {image_path}"}

    ext = Path(image_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return {"file": image_path, "error": f"Unsupported format: {ext}"}

    # Resolve config (pre-configured defaults, no setup needed)
    model = model or os.environ.get("VISION_MODEL", DEFAULT_MODEL)
    api_key = api_key or os.environ.get("VISION_API_KEY", DEFAULT_API_KEY)
    api_base = api_base or os.environ.get("VISION_API_BASE", DEFAULT_API_BASE)

    # Detect type & prompt
    img_type = detect_image_type(os.path.basename(image_path), context)
    final_prompt = get_prompt(img_type, prompt)

    # Cache check
    md5 = compute_md5(image_path)
    prompt_hash = hashlib.md5(final_prompt.encode()).hexdigest()[:8]

    if use_cache:
        cached = cache_get(md5, prompt_hash)
        if cached:
            return {
                "file": image_path,
                "type": img_type,
                "description": cached,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                "cached": True,
            }

    # Process image
    b64, mime = load_and_compress(image_path)

    # Call API
    result = call_vision_api(b64, mime, final_prompt, model, api_key, api_base)

    # Cache result
    if use_cache and "Error" not in result["description"]:
        cache_set(md5, prompt_hash, result["description"])

    return {
        "file": image_path,
        "type": img_type,
        "description": result["description"],
        "usage": result.get("usage", {}),
        "cached": False,
    }


def caption_batch(
    dir_path: str,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
) -> List[dict]:
    """Caption all images in a directory."""
    results = []
    image_files = []
    for ext in SUPPORTED_EXTENSIONS:
        image_files.extend(glob.glob(os.path.join(dir_path, f"*{ext}")))
        image_files.extend(glob.glob(os.path.join(dir_path, f"*{ext.upper()}")))

    image_files = sorted(set(image_files))
    total = len(image_files)
    print(f"Found {total} images in {dir_path}", file=sys.stderr)

    for i, img_path in enumerate(image_files, 1):
        print(f"  [{i}/{total}] {os.path.basename(img_path)}...", end="", file=sys.stderr)
        result = caption_image(img_path, prompt=prompt, model=model,
                               api_key=api_key, api_base=api_base)
        cached_tag = " (cached)" if result.get("cached") else ""
        if "error" in result:
            print(f" ERROR: {result['error']}", file=sys.stderr)
        else:
            desc_preview = result["description"][:60].replace("\n", " ")
            print(f" OK{cached_tag}: {desc_preview}...", file=sys.stderr)
        results.append(result)

    return results


# ─── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate text descriptions of images via vision LLM"
    )
    parser.add_argument("path", help="Image file path or directory (with --batch)")
    parser.add_argument("--prompt", "-p", default=None, help="Custom prompt")
    parser.add_argument("--model", "-m", default=None, help="Vision model name")
    parser.add_argument("--api-key", default=None, help="API key (or set VISION_API_KEY)")
    parser.add_argument("--api-base", default=None, help="API base URL")
    parser.add_argument("--batch", action="store_true", help="Process all images in directory")
    parser.add_argument("--output", "-o", default=None, help="Output file for batch results (JSON)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-cache", action="store_true", help="Disable result caching")
    args = parser.parse_args()

    if args.batch:
        if not os.path.isdir(args.path):
            print(f"Error: {args.path} is not a directory", file=sys.stderr)
            sys.exit(1)
        results = caption_batch(
            args.path, prompt=args.prompt, model=args.model,
            api_key=args.api_key, api_base=args.api_base,
        )
        output = json.dumps(results, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Saved {len(results)} results to {args.output}", file=sys.stderr)
        else:
            print(output)
    else:
        if not os.path.isfile(args.path):
            print(f"Error: {args.path} is not a file", file=sys.stderr)
            sys.exit(1)
        result = caption_image(
            args.path, prompt=args.prompt, model=args.model,
            api_key=args.api_key, api_base=args.api_base,
            use_cache=not args.no_cache,
        )
        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result["description"])


if __name__ == "__main__":
    main()
