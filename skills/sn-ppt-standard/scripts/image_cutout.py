#!/usr/bin/env python3
"""Create conservative subject-only PNG assets without overwriting originals.

The command handles three common presentation-asset cases:

* a real alpha channel already exists: preserve it;
* a light checkerboard or nearly uniform edge background is baked into pixels:
  remove only the edge-connected background;
* a photographic background remains: use OpenCV GrabCut, optionally guided by
  a normalized subject box supplied by the Image agent.

Every operation writes a new PNG under ``assets/`` and emits a JSON report.
"""
from __future__ import annotations

import argparse
from collections import deque
import fcntl
import json
import os
from pathlib import Path
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageFilter


IMAGE_SUFFIXES = {".png", ".webp", ".jpg", ".jpeg"}


def _asset_path(root: Path, relative: str, *, must_exist: bool) -> Path:
    value = Path(relative)
    if value.is_absolute():
        raise ValueError("asset path must be workspace-relative")
    path = (root / value).resolve()
    assets = (root / "assets").resolve()
    if path.parent != assets or path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError("asset must be an image directly under assets/")
    if must_exist and not path.is_file():
        raise FileNotFoundError(f"asset does not exist: {relative}")
    return path


def _default_output(relative: str) -> str:
    source = Path(relative)
    return f"assets/{source.stem}-cutout.png"


def _atomic_png(image: Image.Image, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f"{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(descriptor)
    temporary = Path(name)
    try:
        image.save(temporary, format="PNG", optimize=True)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def _record_derived(root: Path, output_relative: str, source_relative: str) -> None:
    assets = root / "assets"
    catalog_path = assets / "catalog.json"
    lock_path = assets / ".catalog.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            try:
                catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                catalog = {"schema_version": 1, "assets": []}
            entries = catalog.get("assets")
            if not isinstance(entries, list):
                entries = []
            parent = next(
                (item for item in entries
                 if isinstance(item, dict) and item.get("path") == source_relative),
                {},
            )
            entry = {
                "path": output_relative,
                "origin": "derived",
                "parent_asset": source_relative,
                "source_origin": parent.get("origin"),
                "source_url": parent.get("source_url"),
                "source_path": parent.get("source_path"),
                "generator_model": parent.get("generator_model"),
            }
            entries = [item for item in entries
                       if not isinstance(item, dict) or item.get("path") != output_relative]
            entries.append(entry)
            payload = {"schema_version": 1, "assets": sorted(
                entries, key=lambda item: str(item.get("path") or "")
            )}
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".catalog.", suffix=".tmp", dir=assets
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                    json.dump(payload, output, ensure_ascii=False, indent=2)
                    output.write("\n")
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary_name, catalog_path)
            finally:
                Path(temporary_name).unlink(missing_ok=True)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _border_pixels(rgb: np.ndarray) -> np.ndarray:
    return np.concatenate((rgb[0], rgb[-1], rgb[1:-1, 0], rgb[1:-1, -1]))


def _checkerboard_likelihood(rgb: np.ndarray) -> float:
    border = _border_pixels(rgb).astype(np.int16)
    neutral = (border.max(axis=1) - border.min(axis=1) <= 34) & (
        border.min(axis=1) >= 165
    )
    if neutral.mean() < 0.72:
        return 0.0
    values = border[neutral].mean(axis=1)
    if values.size < 24:
        return 0.0
    low, high = np.percentile(values, (25, 75))
    separation = float(high - low)
    if separation < 7:
        return 0.0
    midpoint = (low + high) / 2
    classes = values >= midpoint
    transitions = float(np.count_nonzero(classes[1:] != classes[:-1]))
    return min(1.0, separation / 24.0) * min(1.0, transitions / 12.0)


def inspect(root: Path, relative: str) -> dict:
    path = _asset_path(root, relative, must_exist=True)
    with Image.open(path) as source:
        rgba = np.asarray(source.convert("RGBA"))
        alpha = rgba[:, :, 3]
        rgb = rgba[:, :, :3]
        meaningful = alpha < 250
        border = _border_pixels(rgb).astype(np.float32)
        median = np.median(border, axis=0)
        distance = np.linalg.norm(border - median, axis=1)
        border_p90 = float(np.percentile(distance, 90))
        return {
            "asset": relative,
            "format": source.format,
            "size": [int(source.width), int(source.height)],
            "meaningful_alpha": bool(meaningful.any()),
            "transparent_fraction": round(float((alpha < 16).mean()), 5),
            "soft_alpha_fraction": round(
                float(((alpha >= 16) & (alpha < 250)).mean()), 5
            ),
            "checkerboard_likelihood": round(_checkerboard_likelihood(rgb), 4),
            "border_color": [int(round(value)) for value in median],
            "border_color_p90_distance": round(border_p90, 3),
            "flat_edge_background": border_p90 <= 36,
        }


def _edge_connected(mask: np.ndarray) -> np.ndarray:
    """Return only true pixels connected to an image edge."""
    height, width = mask.shape
    visited = np.zeros((height, width), dtype=np.uint8)
    queue: deque[tuple[int, int]] = deque()

    def add(x: int, y: int) -> None:
        if mask[y, x] and not visited[y, x]:
            visited[y, x] = 1
            queue.append((x, y))

    for x in range(width):
        add(x, 0)
        add(x, height - 1)
    for y in range(height):
        add(0, y)
        add(width - 1, y)
    while queue:
        x, y = queue.popleft()
        if x:
            add(x - 1, y)
        if x + 1 < width:
            add(x + 1, y)
        if y:
            add(x, y - 1)
        if y + 1 < height:
            add(x, y + 1)
    return visited.astype(bool)


def _flat_or_checker_alpha(rgb: np.ndarray, checker: bool) -> np.ndarray:
    data = rgb.astype(np.int16)
    if checker:
        candidate = (data.max(axis=2) - data.min(axis=2) <= 46) & (
            data.min(axis=2) >= 155
        )
    else:
        border = _border_pixels(rgb).astype(np.float32)
        background = np.median(border, axis=0)
        border_distance = np.linalg.norm(border - background, axis=1)
        tolerance = max(24.0, min(58.0, float(np.percentile(border_distance, 90)) + 14.0))
        candidate = np.linalg.norm(rgb.astype(np.float32) - background, axis=2) <= tolerance
    connected = _edge_connected(candidate)
    removed = float(connected.mean())
    if not 0.03 <= removed <= 0.96:
        raise ValueError(
            f"edge-connected background mask is implausible ({removed:.3f})"
        )
    alpha = np.where(connected, 0, 255).astype(np.uint8)
    # A small feather removes white/checker halos without visibly eroding the subject.
    return np.asarray(Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(1.15)))


def _parse_box(value: str | None, width: int, height: int) -> tuple[int, int, int, int]:
    if not value:
        margin_x = max(1, int(width * 0.035))
        margin_y = max(1, int(height * 0.035))
        return margin_x, margin_y, width - 2 * margin_x, height - 2 * margin_y
    parts = [float(item.strip()) for item in value.split(",")]
    if len(parts) != 4 or any(item < 0 or item > 1 for item in parts):
        raise ValueError("subject-box must be normalized x,y,w,h values in 0..1")
    x, y, box_width, box_height = parts
    if box_width <= 0 or box_height <= 0 or x + box_width > 1 or y + box_height > 1:
        raise ValueError("subject-box must fit inside the image")
    return (
        int(round(x * width)),
        int(round(y * height)),
        max(1, int(round(box_width * width))),
        max(1, int(round(box_height * height))),
    )


def _grabcut_alpha(rgb: np.ndarray, subject_box: str | None) -> np.ndarray:
    height, width = rgb.shape[:2]
    scale = min(1.0, 1200.0 / max(width, height))
    if scale < 1:
        work = cv2.resize(rgb, (round(width * scale), round(height * scale)))
    else:
        work = rgb.copy()
    work_height, work_width = work.shape[:2]
    box = _parse_box(subject_box, work_width, work_height)
    mask = np.full((work_height, work_width), cv2.GC_PR_BGD, dtype=np.uint8)
    border = max(2, round(min(work_width, work_height) * 0.012))
    mask[:border, :] = cv2.GC_BGD
    mask[-border:, :] = cv2.GC_BGD
    mask[:, :border] = cv2.GC_BGD
    mask[:, -border:] = cv2.GC_BGD
    x, y, box_width, box_height = box
    mask[y:y + box_height, x:x + box_width] = cv2.GC_PR_FGD
    # A definite foreground seed stabilizes GrabCut while remaining conservative.
    seed_x1 = x + box_width * 3 // 8
    seed_x2 = x + box_width * 5 // 8
    seed_y1 = y + box_height * 3 // 8
    seed_y2 = y + box_height * 5 // 8
    mask[seed_y1:seed_y2, seed_x1:seed_x2] = cv2.GC_FGD
    background_model = np.zeros((1, 65), np.float64)
    foreground_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(
        cv2.cvtColor(work, cv2.COLOR_RGB2BGR),
        mask,
        None,
        background_model,
        foreground_model,
        5,
        cv2.GC_INIT_WITH_MASK,
    )
    alpha = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
    ).astype(np.uint8)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 1.1)
    if scale < 1:
        alpha = cv2.resize(alpha, (width, height), interpolation=cv2.INTER_LINEAR)
    return alpha


def _alpha_report(alpha: np.ndarray) -> dict:
    foreground = alpha >= 128
    fraction = float(foreground.mean())
    if not 0.01 <= fraction <= 0.97:
        raise ValueError(f"foreground mask is implausible ({fraction:.3f})")
    ys, xs = np.where(foreground)
    edge_fraction = float(
        np.concatenate((foreground[0], foreground[-1], foreground[:, 0], foreground[:, -1])).mean()
    )
    warnings = []
    if edge_fraction > 0.18:
        warnings.append("subject touches a large part of the canvas edge; inspect clipping")
    return {
        "foreground_fraction": round(fraction, 5),
        "edge_foreground_fraction": round(edge_fraction, 5),
        "subject_bbox": [
            int(xs.min()),
            int(ys.min()),
            int(xs.max() + 1),
            int(ys.max() + 1),
        ],
        "warnings": warnings,
    }


def cutout(
    root: Path,
    relative: str,
    output_relative: str,
    mode: str,
    subject_box: str | None,
) -> dict:
    source_path = _asset_path(root, relative, must_exist=True)
    output_path = _asset_path(root, output_relative, must_exist=False)
    if source_path == output_path:
        raise ValueError("output must differ from source; originals are never overwritten")
    with Image.open(source_path) as source:
        rgba_image = source.convert("RGBA")
    rgba = np.asarray(rgba_image).copy()
    rgb = rgba[:, :, :3]
    source_alpha = rgba[:, :, 3]
    info = inspect(root, relative)

    selected = mode
    if mode == "auto":
        if info["meaningful_alpha"]:
            selected = "preserve-alpha"
        elif info["checkerboard_likelihood"] >= 0.32:
            selected = "checkerboard"
        elif info["flat_edge_background"]:
            selected = "flat"
        else:
            selected = "grabcut"

    if selected == "preserve-alpha":
        if not info["meaningful_alpha"]:
            raise ValueError("source has no meaningful alpha channel")
        alpha = source_alpha
    elif selected == "checkerboard":
        alpha = _flat_or_checker_alpha(rgb, True)
    elif selected == "flat":
        alpha = _flat_or_checker_alpha(rgb, False)
    elif selected == "grabcut":
        alpha = _grabcut_alpha(rgb, subject_box)
    else:
        raise ValueError(f"unknown cutout mode: {selected}")

    report = _alpha_report(alpha)
    rgba[:, :, 3] = alpha
    _atomic_png(Image.fromarray(rgba, mode="RGBA"), output_path)
    _record_derived(root, output_relative, relative)
    return {
        "status": "PASS",
        "source": relative,
        "output": output_relative,
        "operation": selected,
        **report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("root")
    inspect_parser.add_argument("--asset", required=True)
    cutout_parser = subparsers.add_parser("cutout")
    cutout_parser.add_argument("root")
    cutout_parser.add_argument("--asset", required=True)
    cutout_parser.add_argument("--output")
    cutout_parser.add_argument(
        "--mode",
        choices=("auto", "preserve-alpha", "checkerboard", "flat", "grabcut"),
        default="auto",
    )
    cutout_parser.add_argument(
        "--subject-box",
        help="optional normalized x,y,w,h guidance for GrabCut",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        if args.command == "inspect":
            report = inspect(root, args.asset)
        else:
            output = args.output or _default_output(args.asset)
            report = cutout(root, args.asset, output, args.mode, args.subject_box)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {"status": "FAIL", "error": str(error)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
