#!/usr/bin/env python3
"""Generate normalized scene and connector clips from a motion-story manifest."""

from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import mimetypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class NonRetryableArkError(RuntimeError):
    """An account or request error another identical attempt cannot fix."""


def load_dotenv(root: Path) -> None:
    path = root / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


class ArkClient:
    def __init__(self, key: str, base_url: str) -> None:
        self.key = key
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "User-Agent": "sn-motion-html/1.0",
            },
        )
        try:
            with urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            fatal = ('"ModelNotOpen"', '"AccessDenied"', '"InvalidAuthentication"', '"InvalidParameter"')
            error_type = NonRetryableArkError if any(code in detail for code in fatal) else RuntimeError
            raise error_type(f"Ark HTTP {exc.code}: {detail[:800]}") from exc
        except URLError as exc:
            raise RuntimeError(f"Ark network error: {exc.reason}") from exc

    def create(self, payload: dict[str, Any]) -> str:
        result = self.request("POST", "/contents/generations/tasks", payload)
        if not result.get("id"):
            raise RuntimeError(f"Ark response missing task id: {result}")
        return str(result["id"])

    def wait(self, task_id: str, poll_seconds: int, timeout_seconds: int) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            result = self.request("GET", f"/contents/generations/tasks/{task_id}")
            status = str(result.get("status", ""))
            print(f"  {task_id}: {status or 'unknown'}", flush=True)
            if status == "succeeded":
                return result
            if status in {"failed", "cancelled", "expired"}:
                raise RuntimeError(f"Ark task {task_id} ended as {status}: {result}")
            time.sleep(poll_seconds)
        raise TimeoutError(f"Ark task {task_id} timed out after {timeout_seconds}s")


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "sn-motion-html/1.0"})
    with urlopen(request, timeout=180) as response, path.open("wb") as target:
        shutil.copyfileobj(response, target)


def run_ffmpeg(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def normalize_video(source: Path, target: Path, manifest: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    width = int(manifest.get("target_width", 1280))
    height = int(manifest.get("target_height", 720))
    fps = int(manifest.get("fps", 24))
    duration = float(manifest.get("duration", 4))
    filters = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},"
        f"tpad=stop_mode=clone:stop_duration={duration},trim=duration={duration},"
        "setpts=PTS-STARTPTS"
    )
    if manifest.get("generate_audio", False):
        audio_args = ["-af", f"apad,atrim=duration={duration}", "-c:a", "aac", "-b:a", "192k"]
    else:
        audio_args = ["-an"]
    run_ffmpeg([
        "-i", str(source), *audio_args, "-vf", filters,
        "-c:v", "libx264", "-preset", "slow", "-crf", str(manifest.get("crf", 20)),
        "-pix_fmt", "yuv420p", "-g", str(manifest.get("gop", 8)),
        "-keyint_min", str(manifest.get("gop", 8)), "-sc_threshold", "0",
        "-movflags", "+faststart", str(target),
    ])


def extract_frames(video: Path, first: Path, last: Path) -> None:
    first.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-i", str(video), "-vf", "select=eq(n\\,0)", "-frames:v", "1", str(first)])
    run_ffmpeg(["-sseof", "-0.05", "-i", str(video), "-frames:v", "1", str(last)])


def build_payload(
    manifest: dict[str, Any], prompt: str, first: Path, last: Path | None
) -> dict[str, Any]:
    mode = manifest.get("conditioning_mode", "reference_images")
    first_role = "reference_image" if mode == "reference_images" else "first_frame"
    content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": data_uri(first)}, "role": first_role},
    ]
    if last is not None:
        last_role = "reference_image" if mode == "reference_images" else "last_frame"
        content.append({"type": "image_url", "image_url": {"url": data_uri(last)}, "role": last_role})
    payload: dict[str, Any] = {
        "model": os.getenv("SEEDANCE_MODEL") or manifest["model"],
        "content": content,
        "duration": int(manifest["duration"]),
        "resolution": manifest["resolution"],
        "ratio": manifest["ratio"],
        "generate_audio": bool(manifest.get("generate_audio", False)),
        "watermark": bool(manifest.get("watermark", False)),
    }
    if manifest.get("output_format"):
        payload["output_format"] = manifest["output_format"]
    return payload


def generate_clip(
    root: Path,
    client: ArkClient,
    manifest: dict[str, Any],
    kind: str,
    item: dict[str, Any],
    first: Path,
    last: Path | None,
    args: argparse.Namespace,
) -> None:
    clip_id = item["id"]
    output = root / item["output"]
    if output.exists() and output.stat().st_size > 0 and not args.force:
        print(f"skip {kind} {clip_id} (already exists)")
        return
    if not first.exists() or (last is not None and not last.exists()):
        raise FileNotFoundError(f"Missing conditioning frame for {clip_id}")

    prompt_path = root / item["prompt"]
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    style_motion_path = root / "prompts" / "style-motion.txt"
    if style_motion_path.exists():
        style_motion = style_motion_path.read_text(encoding="utf-8").strip()
        if style_motion:
            prompt = f"{style_motion}\n\n{prompt}"
    raw = root / "tmp" / "seedance" / "raw" / kind / f"{clip_id}.mp4"
    tasks = root / "tmp" / "seedance" / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    safe = {
        "model": os.getenv("SEEDANCE_MODEL") or manifest["model"],
        "kind": kind,
        "clip_id": clip_id,
        "prompt_file": item["prompt"],
        "first_frame": str(first.relative_to(root)),
        "last_frame": str(last.relative_to(root)) if last else None,
    }

    last_error: Exception | None = None
    for attempt in range(1, args.attempts + 1):
        print(f"{kind} {clip_id} attempt {attempt}/{args.attempts}", flush=True)
        try:
            task_id = client.create(build_payload(manifest, prompt, first, last))
            safe.update({"attempt": attempt, "task_id": task_id})
            (tasks / f"{kind}-{clip_id}-request.json").write_text(
                json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            result = client.wait(task_id, args.poll_seconds, args.timeout_seconds)
            (tasks / f"{kind}-{clip_id}-result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            video_url = result.get("content", {}).get("video_url")
            if not video_url:
                raise RuntimeError(f"Succeeded task has no content.video_url: {task_id}")
            download(str(video_url), raw)
            normalize_video(raw, output, manifest)
            print(f"saved {output.relative_to(root)}", flush=True)
            return
        except Exception as exc:
            last_error = exc
            print(f"  failed: {exc}", file=sys.stderr, flush=True)
            if isinstance(exc, NonRetryableArkError):
                raise
    raise RuntimeError(f"{kind} {clip_id} failed after {args.attempts} attempts") from last_error


def run_dives(root: Path, client: ArkClient, manifest: dict[str, Any], args: argparse.Namespace) -> None:
    items = manifest.get("dives", [])[: args.limit or None]
    frames = root / "assets" / "video" / "frames"

    def run_one(item: dict[str, Any]) -> None:
        generate_clip(root, client, manifest, "dives", item, root / item["still"], None, args)
        output = root / item["output"]
        extract_frames(output, frames / f"{item['id']}-first.png", frames / f"{item['id']}-last.png")

    if items:
        with ThreadPoolExecutor(max_workers=min(args.workers, len(items))) as executor:
            list(executor.map(run_one, items))


def run_connectors(root: Path, client: ArkClient, manifest: dict[str, Any], args: argparse.Namespace) -> None:
    items = manifest.get("connectors", [])[: args.limit or None]
    frames = root / "assets" / "video" / "frames"

    def run_one(item: dict[str, Any]) -> None:
        generate_clip(
            root, client, manifest, "connectors", item,
            frames / f"{item['from']}-last.png", frames / f"{item['to']}-first.png", args,
        )

    if items:
        with ThreadPoolExecutor(max_workers=min(args.workers, len(items))) as executor:
            list(executor.map(run_one, items))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("phase", choices=["plan", "dives", "connectors", "all"], nargs="?", default="plan")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=8)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args()
    if args.workers < 1 or args.attempts < 1:
        parser.error("--workers and --attempts must be at least 1")

    root = args.project_root.expanduser().resolve()
    load_dotenv(root)
    manifest = json.loads((root / "prompts" / "video-manifest.json").read_text(encoding="utf-8"))
    plan = {
        "model": os.getenv("SEEDANCE_MODEL") or manifest["model"],
        "duration": manifest["duration"],
        "resolution": manifest["resolution"],
        "ratio": manifest["ratio"],
        "dives": len(manifest.get("dives", [])),
        "connectors": len(manifest.get("connectors", [])),
        "workers": args.workers,
        "conditioning_mode": manifest.get("conditioning_mode", "reference_images"),
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if args.phase == "plan":
        return 0
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required")
    key = os.getenv("ARK_API_KEY") or os.getenv("VOLCENGINE_API_KEY")
    if not key:
        raise SystemExit("ARK_API_KEY is not set in the project-local .env file")
    client = ArkClient(key, os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"))
    if args.phase in {"dives", "all"}:
        run_dives(root, client, manifest, args)
    if args.phase in {"connectors", "all"}:
        run_connectors(root, client, manifest, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
