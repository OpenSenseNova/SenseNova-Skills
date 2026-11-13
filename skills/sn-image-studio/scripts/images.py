#!/usr/bin/env python3
"""Standalone SenseNova U1.5 generation/editing client for Image Studio."""
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import math
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from configuration import Configuration
from execution_limits import (CONNECT_TIMEOUT, UPLOAD_TIMEOUT, IMAGE_RESPONSE_TIMEOUT,
                              IMAGE_DOWNLOAD_TIMEOUT, error_text)

RESOLUTION_EDGES = {"2k": 2048, "4k": 4096}
MAX_IMAGE_BYTES = 80 * 1024 * 1024


def pixel_size(aspect_ratio, image_size, model):
    if not isinstance(aspect_ratio, str) or not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", aspect_ratio):
        raise ValueError("图片比例须为正整数比，例如 3:4。")
    width, height = map(int, aspect_ratio.split(":"))
    if width > 3 * height or height > 3 * width:
        raise ValueError("图片比例须介于 1:3 与 3:1 之间。")
    if image_size not in RESOLUTION_EDGES or (image_size == "4k" and model.lower() != "sensenova-u1.5-lite"):
        raise ValueError("支持 2k；sensenova-u1.5-lite 还支持 4k。")
    # API size rules: each edge is 512..4096 in multiples of 32; ratio 1:3..3:1.
    # Preserve the sample's ratio instead of snapping it to a small preset list.
    # Start from the resolution's square pixel budget, then cap the longest edge.
    ratio = width / height
    edge = RESOLUTION_EDGES[image_size]
    w, h = edge * math.sqrt(ratio), edge / math.sqrt(ratio)
    scale = min(1, 4096 / max(w, h))
    w, h = (max(512, min(4096, round(value * scale / 32) * 32)) for value in (w, h))
    # Independent rounding at 3:1 can overshoot the boundary by one grid step.
    w, h = min(w, 3 * h), min(h, 3 * w)
    if not (512 <= w <= 4096 and 512 <= h <= 4096 and
            w % 32 == h % 32 == 0 and h <= 3 * w and w <= 3 * h):
        raise ValueError("图片尺寸须为 512～4096 像素、32 的倍数，且比例介于 1:3 与 3:1 之间。")
    return f"{w}x{h}"


def input_image(value):
    """Keep URLs/data URLs intact and encode local inputs in their supplied order."""
    from PIL import Image
    if value.startswith("data:image/") and ";base64," in value:
        return value
    parsed = urlsplit(value)
    if parsed.scheme in {"https", "http"} and parsed.netloc:
        return value
    path = Path(value)
    data = path.read_bytes()
    if len(data) > 20 * 1024 * 1024:
        raise ValueError("每张输入图片最多 20 MB。")
    with Image.open(io.BytesIO(data)) as image:
        media_type = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(image.format)
        image.verify()
    if media_type is None:
        raise ValueError("输入图片须为 PNG、JPG 或 WebP。")
    return f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"


def save_png(data, save_path):
    """Decode before publishing; failures leave any previous output untouched."""
    from PIL import Image, ImageOps
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("模型返回的图片为空或超过 80 MB。")
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    output = Path(save_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".u15-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                ImageOps.exif_transpose(image).save(stream, format="PNG")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return str(output)


async def result_bytes(client, response):
    try:
        value = response.json()
    except ValueError as exc:
        raise ValueError("图像接口未返回有效 JSON。") from exc
    entries = value.get("data") if isinstance(value, dict) else None
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        raise ValueError("图像接口未返回生成图片。")
    entry = entries[0]
    if isinstance(entry.get("b64_json"), str):
        if len(entry["b64_json"]) > (MAX_IMAGE_BYTES + 2) // 3 * 4:
            raise ValueError("模型返回的图片超过 80 MB。")
        return base64.b64decode(entry["b64_json"], validate=True)
    url = entry.get("url")
    if not isinstance(url, str) or urlsplit(url).scheme not in {"https", "http"} or not urlsplit(url).netloc:
        raise ValueError("图像接口未返回有效图片地址。")
    # This client has no API authorization headers; CDN downloads never receive the Key.
    import httpx
    try:
        timeout = httpx.Timeout(IMAGE_DOWNLOAD_TIMEOUT, connect=CONNECT_TIMEOUT)
        async with client.stream("GET", url, follow_redirects=True, timeout=timeout) as download:
            if download.is_error:
                raise RuntimeError(f"图片下载失败：HTTP {download.status_code}")
            chunks, length = [], 0
            async for chunk in download.aiter_bytes():
                length += len(chunk)
                if length > MAX_IMAGE_BYTES:
                    raise ValueError("模型返回的图片超过 80 MB。")
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.TimeoutException as exc:
        seconds = CONNECT_TIMEOUT if isinstance(exc, httpx.ConnectTimeout) else IMAGE_DOWNLOAD_TIMEOUT
        raise RuntimeError(f"接口已返回图片地址，但下载图片超时（{seconds} 秒，{type(exc).__name__}）；请检查原任务结果，不要重复生图。") from exc


async def create_image(config, prompt, images, save_path, aspect_ratio="1:1", image_size="2k"):
    status = config.public()
    if not status["image_ready"]:
        raise ValueError("；".join(status["missing"] + status["missing_dependencies"]))
    resolved = config.resolve()
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 64000:
        raise ValueError("Prompt 不能为空且最多为 64000 字符。")
    if len(images) > 10:
        raise ValueError("最多支持 10 张输入图片。")
    payload = {"model": resolved["model"], "prompt": prompt, "n": 1,
               "watermark": False, "prompt_extend": False, "response_format": "url"}
    if images:
        endpoint = "/images/edits"
        payload.update(size="auto", images=[{"image_url": input_image(str(image))} for image in images])
    else:
        endpoint = "/images/generations"
        payload.update(size=pixel_size(aspect_ratio, image_size, resolved["model"]), output_format="png")
    import httpx
    # No retries: a timed-out POST may already have been accepted and billed.
    timeout = httpx.Timeout(IMAGE_RESPONSE_TIMEOUT, connect=CONNECT_TIMEOUT,
                            write=UPLOAD_TIMEOUT, pool=CONNECT_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(resolved["base_url"] + endpoint, json=payload,
                                         headers={"Authorization": f"Bearer {resolved['api_key']}"})
        except httpx.TimeoutException as exc:
            stage, seconds = "等待图片接口响应", IMAGE_RESPONSE_TIMEOUT
            if isinstance(exc, (httpx.ConnectTimeout, httpx.PoolTimeout)):
                stage, seconds = "连接图片接口", CONNECT_TIMEOUT
            elif isinstance(exc, httpx.WriteTimeout):
                stage, seconds = "上传图片请求", UPLOAD_TIMEOUT
            raise RuntimeError(f"{stage}超时（{seconds} 秒，{type(exc).__name__}）；结果尚未确认，请检查原任务，不要直接重复提交。") from exc
        if not response.is_success:
            details = response.text[:2000].replace(resolved["api_key"], "[REDACTED]")
            raise RuntimeError(f"HTTP {response.status_code}: {details}")
        output = save_png(await result_bytes(client, response), save_path)
    return {"output": output, "model": resolved["model"],
            "operation": "edit" if images else "generate", "submitted_prompt": prompt}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path.cwd() / ".env")
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--images", nargs="*", default=[])
    parser.add_argument("--aspect-ratio", default="1:1")
    parser.add_argument("--image-size", choices=["2k", "4k"], default="2k")
    parser.add_argument("--save-path", required=True, type=Path)
    args = parser.parse_args()
    config = Configuration(args.env_file)
    try:
        result = asyncio.run(create_image(config, args.prompt_file.read_text(encoding="utf-8"), args.images,
                                          args.save_path, args.aspect_ratio, args.image_size))
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False))
    except Exception as exc:
        message = error_text(exc, "图像任务失败")
        key = config.resolve()["api_key"]
        if key:
            message = message.replace(key, "[REDACTED]")
        print(json.dumps({"status": "failed", "error": message}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
