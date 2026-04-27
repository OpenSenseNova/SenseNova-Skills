"""Shared timing.json authoring helper used by all ppt-* mode skills.

Subcommands:
    init                         - create empty timing.json
    record-stage                 - accumulate seconds into stages.<name>
    record-page                  - set a per_page[i].<field> value

Accumulation semantics follow spec section 15.3: repeated writes to the same
stage ADD seconds rather than overwrite. total_seconds tracks the sum of all
stages.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path: Path) -> dict:
    if not path.exists():
        return {"total_seconds": 0.0, "stages": {}, "per_page": []}
    return json.loads(path.read_text())


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_init(path: Path) -> None:
    _save(path, {"total_seconds": 0.0, "stages": {}, "per_page": []})


def cmd_record_stage(path: Path, stage: str, seconds: float) -> None:
    data = _load(path)
    data["stages"][stage] = round(data["stages"].get(stage, 0.0) + seconds, 2)
    data["total_seconds"] = round(sum(data["stages"].values()), 2)
    _save(path, data)


def cmd_record_page(path: Path, page_no: int, field: str, seconds: float) -> None:
    data = _load(path)
    entry = next((p for p in data["per_page"] if p["page_no"] == page_no), None)
    if entry is None:
        entry = {"page_no": page_no}
        data["per_page"].append(entry)
        data["per_page"].sort(key=lambda p: p["page_no"])
    entry[field] = round(entry.get(field, 0.0) + seconds, 2)
    _save(path, data)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init"); p_init.add_argument("--path", type=Path, required=True)
    p_stg = sub.add_parser("record-stage")
    p_stg.add_argument("--path", type=Path, required=True)
    p_stg.add_argument("--stage", required=True)
    p_stg.add_argument("--seconds", type=float, required=True)
    p_pg = sub.add_parser("record-page")
    p_pg.add_argument("--path", type=Path, required=True)
    p_pg.add_argument("--page-no", type=int, required=True)
    p_pg.add_argument("--field", required=True)
    p_pg.add_argument("--seconds", type=float, required=True)

    args = p.parse_args(argv)
    if args.cmd == "init":
        cmd_init(args.path)
    elif args.cmd == "record-stage":
        cmd_record_stage(args.path, args.stage, args.seconds)
    elif args.cmd == "record-page":
        cmd_record_page(args.path, args.page_no, args.field, args.seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
