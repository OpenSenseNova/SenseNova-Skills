#!/usr/bin/env python3
"""Publish generalized generation progress for the SenseNova WebUI.

The script is intentionally small and dependency-free so any PPT-related skill
can emit progress without coupling itself to one generation implementation.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "agent_generation_progress_v1"
LEGACY_SCHEMA_VERSION = "workbench_generation_progress_v1"
STATUS_VALUES = {"idle", "running", "ok", "failed", "skipped"}


def _configure_stdio_encoding() -> None:
    """Keep progress JSON writable when Windows uses a non-UTF-8 codepage."""
    for stream in (sys.stdout, sys.stderr):
        if not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_configure_stdio_encoding()


def now_iso() -> str:
    """Return a UTC timestamp compatible with JavaScript Date parsing."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def progress_path(deck: Path) -> Path:
    """Return the deck-local progress metadata file path."""
    return deck / ".workbench" / "progress.json"


def read_existing_history(deck: Path) -> list[dict[str, Any]]:
    """Load bounded previous progress history if it exists."""
    try:
        payload = json.loads(progress_path(deck).read_text(encoding="utf-8"))
        history = payload.get("history", [])
        return history if isinstance(history, list) else []
    except Exception:
        return []


def stage_artifact(stage: str, page_no: int | None = None) -> str:
    """Map a known stage name to its primary output artifact."""
    if stage in {"entry", "preflight"}:
        return "task_pack.json / info_pack.json"
    if stage == "style-samples":
        return "style_samples.json"
    if stage in {"style", "creative-style"}:
        return "style_spec.json"
    if stage in {"outline", "creative-outline"}:
        return "outline.json"
    if stage in {"asset-plan", "gen-image", "batch-gen-image"}:
        return "asset_plan.json"
    if stage in {"creative-prompt"} and page_no:
        return f"pages/page_{page_no:03d}.prompt.txt"
    if stage in {"page-html", "refine-page"} and page_no:
        return f"pages/page_{page_no:03d}.html"
    if stage in {"creative-render"} and page_no:
        return f"pages/page_{page_no:03d}.png"
    if stage in {"batch-page-html", "batch-refine-page"}:
        return "pages/page_*.html"
    if stage == "export":
        return "PPTX/PDF export"
    return stage


def stage_label(stage: str, page_no: int | None = None, start_page: int | None = None, end_page: int | None = None) -> str:
    """Build a short human-readable label for the current generation step."""
    labels = {
        "entry": "初始化生成任务",
        "preflight": "准备任务与资料包",
        "style-samples": "生成三套风格样例",
        "style": "确认幻灯片风格",
        "creative-style": "生成创意模式风格",
        "outline": "生成页面大纲",
        "creative-outline": "生成创意模式大纲",
        "asset-plan": "规划图片与图表资产",
        "gen-image": "生成页面图片资产",
        "batch-gen-image": "批量生成图片资产",
        "creative-prompt": "生成单页图像提示词",
        "creative-render": "渲染单页图像",
        "page-html": "生成单页 HTML",
        "batch-page-html": "批量生成 HTML 页面",
        "refine-page": "优化单页 HTML",
        "batch-refine-page": "批量优化 HTML 页面",
        "export": "导出演示文稿",
    }
    page_label = f" P{page_no}" if page_no else ""
    range_label = f" P{start_page}-{end_page}" if start_page and end_page else ""
    return f"{labels.get(stage, stage)}{page_label or range_label}"


def parse_json(value: str | None) -> Any:
    """Parse optional inline JSON and report clear errors to callers."""
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--result-json is not valid JSON: {exc}") from exc


def write_event(
    deck: Path,
    stage: str,
    status: str,
    *,
    artifact: str | None = None,
    current_label: str | None = None,
    page_no: int | None = None,
    start_page: int | None = None,
    end_page: int | None = None,
    started_at: str | None = None,
    result: Any = None,
    error: str | None = None,
    schema_version: str = SCHEMA_VERSION,
    workflow: str = "ppt-generation",
) -> dict[str, Any]:
    """Persist one progress event and return the written payload."""
    if status not in STATUS_VALUES:
        raise ValueError(f"invalid status: {status}")

    deck = deck.expanduser().resolve()
    updated_at = now_iso()
    event = {
        "stage": stage,
        "status": status,
        "artifact": artifact or stage_artifact(stage, page_no),
        "pageNo": page_no,
        "startPage": start_page,
        "endPage": end_page,
        "currentLabel": current_label or stage_label(stage, page_no, start_page, end_page),
        "updatedAt": updated_at,
        **({"error": error} if error else {}),
    }
    history = [*read_existing_history(deck), event][-80:]
    payload = {
        "schemaVersion": schema_version,
        "workflow": workflow,
        **event,
        "startedAt": started_at or updated_at,
        "updatedAt": updated_at,
        **({"finishedAt": updated_at} if status != "running" else {}),
        **({"result": result} if result is not None else {}),
        **({"error": error} if error else {}),
        "history": history,
    }

    path = progress_path(deck)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    """Create the progress-event CLI parser."""
    parser = argparse.ArgumentParser(description="Write one generation progress event.")
    parser.add_argument("--deck-dir", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--status", required=True, choices=sorted(STATUS_VALUES))
    parser.add_argument("--artifact", default="")
    parser.add_argument("--label", default="")
    parser.add_argument("--page", "--page-no", dest="page_no", type=int, default=None)
    parser.add_argument("--start-page", type=int, default=None)
    parser.add_argument("--end-page", type=int, default=None)
    parser.add_argument("--started-at", default="")
    parser.add_argument("--result-json", default="")
    parser.add_argument("--error", default="")
    parser.add_argument("--schema-version", default=SCHEMA_VERSION, choices=[SCHEMA_VERSION, LEGACY_SCHEMA_VERSION])
    parser.add_argument("--workflow", default="ppt-generation")
    return parser


def main() -> int:
    """Parse CLI args, write the event, and print the resulting JSON."""
    args = build_parser().parse_args()
    try:
        payload = write_event(
            Path(args.deck_dir),
            args.stage,
            args.status,
            artifact=args.artifact or None,
            current_label=args.label or None,
            page_no=args.page_no,
            start_page=args.start_page,
            end_page=args.end_page,
            started_at=args.started_at or None,
            result=parse_json(args.result_json),
            error=args.error or None,
            schema_version=args.schema_version,
            workflow=args.workflow,
        )
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps({"status": "ok", "progress": payload}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
