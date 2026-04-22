#!/usr/bin/env python3
"""
AI 图片生成（OpenAI 兼容格式）。支持豆包 Seedream 等兼容 /v1/images/generations 的服务。

生成图片并保存到指定目录，返回本地文件路径供 Markdown 引用。

环境变量：
  ARK_API_KEY   - API Key（OpenClaw 会从 skills.entries.generate-image.apiKey 注入）
  ARK_BASE_URL  - API 地址（可选，覆盖默认 endpoint）

示例：
  # 依赖 ARK_API_KEY 环境变量
  python3 generate_image.py "一幅展示AI芯片从云端向边缘迁移的科技风格示意图"
  python3 generate_image.py "市场增长趋势概念图，蓝色调" --size 1024x1024
  python3 generate_image.py "技术架构概览" --output-dir /path/to/report/images --filename arch.png
  # 显式传参会覆盖环境变量
  python3 generate_image.py "供应链示意图" --api-key sk-xxx --base-url https://ark.cn-beijing.volces.com/api/v3
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


# 默认配置
DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seedream-5-0-260128"


def generate_image(
    prompt: str,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    size: str = "2K",
    watermark: bool = False,
    output_dir: str = ".",
    filename: str | None = None,
) -> dict:
    """调用图片生成 API 并保存到本地。"""

    url = f"{base_url.rstrip('/')}/images/generations"

    body = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "response_format": "b64_json",
        "watermark": watermark,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        return {"success": False, "error": f"API 请求失败 ({e.code}): {error_body}"}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"网络错误: {e.reason}"}
    except TimeoutError:
        return {"success": False, "error": "请求超时（120s）"}

    # 解析响应
    data = result.get("data", [])
    if not data:
        return {"success": False, "error": "API 返回空结果"}

    image_b64 = data[0].get("b64_json", "")
    revised_prompt = data[0].get("revised_prompt", "")

    if not image_b64:
        # 回退：尝试 url 格式
        image_url = data[0].get("url", "")
        if image_url:
            try:
                with urllib.request.urlopen(image_url, timeout=60) as img_resp:
                    image_bytes = img_resp.read()
            except Exception as e:
                return {"success": False, "error": f"下载图片失败: {e}"}
        else:
            return {"success": False, "error": "API 未返回图片数据（b64_json 和 url 均为空）"}
    else:
        image_bytes = base64.b64decode(image_b64)

    # 保存图片
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not filename:
        timestamp = int(time.time() * 1000)
        filename = f"img_{timestamp}.png"

    file_path = output_path / filename
    with open(file_path, "wb") as f:
        f.write(image_bytes)

    return {
        "success": True,
        "file_path": str(file_path.resolve()),
        "filename": filename,
        "revised_prompt": revised_prompt,
        "model": model,
        "size": size,
    }


def main():
    parser = argparse.ArgumentParser(description="AI 图片生成（OpenAI 兼容格式）")
    parser.add_argument("prompt", help="图片描述（详细描述所需图片的内容、风格、色调）")
    parser.add_argument(
        "--api-key", default=os.environ.get("ARK_API_KEY"),
        help="API Key（默认从 ARK_API_KEY 环境变量读取）",
    )
    parser.add_argument(
        "--base-url", default=os.environ.get("ARK_BASE_URL", DEFAULT_BASE_URL),
        help=f"API 地址（默认从 ARK_BASE_URL 读取，未设置时为 {DEFAULT_BASE_URL}）",
    )
    parser.add_argument(
        "--model", "-m", default=DEFAULT_MODEL,
        help=f"模型名称（默认: {DEFAULT_MODEL}）",
    )
    parser.add_argument(
        "--size", "-s", default="2K",
        help="图片尺寸（默认: 2K；可选 1024x1024, 2K, 4K 等）",
    )
    parser.add_argument(
        "--output-dir", "-o", default=".",
        help="图片保存目录（默认: 当前目录）",
    )
    parser.add_argument(
        "--filename", "-f", default=None,
        help="输出文件名（默认: img_{timestamp}.png）",
    )
    parser.add_argument(
        "--watermark", action="store_true",
        help="添加水印（默认不加）",
    )

    args = parser.parse_args()

    if not args.api_key:
        print(json.dumps({
            "success": False,
            "error": "Missing API key. 请在 ~/.openclaw/openclaw.json 的 "
                     "skills.entries.generate-image.apiKey 中配置，或直接设置 ARK_API_KEY 环境变量。",
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    result = generate_image(
        prompt=args.prompt,
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        size=args.size,
        watermark=args.watermark,
        output_dir=args.output_dir,
        filename=args.filename,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
