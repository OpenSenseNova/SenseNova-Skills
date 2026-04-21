#!/usr/bin/env python3
"""把 deep-research plugin 需要的配置片段合并到 ~/.openclaw/openclaw.json

策略：
- 不存在的 JSON 文件 → 新建 `{}` 再合并
- `agents.defaults.subagents.allowAgents` → 按元素去重后求并集
- `agents.list` → 按 `id` upsert（已存在则跳过，不覆写用户已有配置；可用 --force 覆写）
- `plugins.entries.deep-research` → 整体写入（若用户未设则填默认，若已有则保留 enabled 外的用户字段）

用法：
    python3 merge_config.py [--config PATH] [--force] [--dry-run]

默认配置路径：
    $OPENCLAW_CONFIG_PATH 或 ~/.openclaw/openclaw.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

PLUGIN_CONFIG = {
    "agents": {
        "defaults": {
            "subagents": {
                "maxSpawnDepth": 1,
                "maxConcurrent": 8,
                "runTimeoutSeconds": 1800,
                "allowAgents": [
                    "scout-agent",
                    "plan-agent",
                    "research-agent",
                    "review-agent",
                    "report-agent",
                ],
            }
        },
        "list": [
            {
                "id": "scout-agent",
                "workspace": "~/.openclaw/workspace-scout-agent",
                "skills": [
                    "search-code",
                    "search-academic",
                    "search-social-cn",
                    "search-social-en",
                ],
            },
            {
                "id": "plan-agent",
                "workspace": "~/.openclaw/workspace-plan-agent",
                "skills": [
                    "search-code",
                    "search-academic",
                    "search-social-cn",
                    "search-social-en",
                    "report-format-discovery",
                ],
            },
            {
                "id": "research-agent",
                "workspace": "~/.openclaw/workspace-research-agent",
                "skills": [
                    "search-code",
                    "search-academic",
                    "search-social-cn",
                    "search-social-en",
                ],
            },
            {
                "id": "review-agent",
                "workspace": "~/.openclaw/workspace-review-agent",
                "skills": [],
            },
            {
                "id": "report-agent",
                "workspace": "~/.openclaw/workspace-report-agent",
                "skills": ["research-report", "generate-image"],
            },
        ],
    },
    "plugins": {
        "entries": {
            "deep-research": {
                "enabled": True,
                "config": {
                    "subagent": {"allowModelOverride": False},
                    "reports": {"rootDir": ""},
                },
            }
        }
    },
}


def default_config_path() -> Path:
    env = os.environ.get("OPENCLAW_CONFIG_PATH")
    if env:
        return Path(env).expanduser()
    state = os.environ.get("OPENCLAW_STATE_DIR")
    if state:
        return Path(state).expanduser() / "openclaw.json"
    return Path.home() / ".openclaw" / "openclaw.json"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    return json.loads(text)


def dict_get(d: dict, *keys: str) -> dict:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return {}
        cur = cur.setdefault(k, {})
    return cur


def merge_list_allow_agents(existing: list, incoming: list) -> list:
    seen = set(existing or [])
    out = list(existing or [])
    for item in incoming:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


def upsert_agents_list(existing: list, incoming: list, force: bool) -> tuple[list, list[str]]:
    """按 id upsert。返回 (合并后的列表, 新增/覆写的 id 列表)。"""
    by_id = {entry.get("id"): (idx, entry) for idx, entry in enumerate(existing or []) if isinstance(entry, dict)}
    changed: list[str] = []
    result = list(existing or [])
    for entry in incoming:
        eid = entry.get("id")
        if not eid:
            continue
        if eid in by_id:
            if force:
                idx, _ = by_id[eid]
                result[idx] = entry
                changed.append(f"overwrite:{eid}")
        else:
            result.append(entry)
            changed.append(f"add:{eid}")
    return result, changed


def merge_plugin_entry(existing: dict, incoming: dict) -> dict:
    """plugins.entries.deep-research：已存在则保留用户字段（只设 enabled=true 若未显式关闭），不存在则用默认。"""
    if not existing:
        return dict(incoming)
    # 用户已有：保留 config（用户微调过的设置），但确保 enabled 存在
    out = dict(existing)
    if "enabled" not in out:
        out["enabled"] = True
    # config 子树：仅补充缺失键，不覆写
    incoming_cfg = incoming.get("config", {})
    existing_cfg = out.setdefault("config", {})
    for section, section_defaults in incoming_cfg.items():
        existing_section = existing_cfg.setdefault(section, {})
        if isinstance(section_defaults, dict):
            for k, v in section_defaults.items():
                existing_section.setdefault(k, v)
    return out


def merge(cfg: dict, force: bool) -> tuple[dict, list[str]]:
    changes: list[str] = []

    # agents.defaults.subagents
    sub = dict_get(cfg, "agents", "defaults", "subagents")
    inc_sub = PLUGIN_CONFIG["agents"]["defaults"]["subagents"]
    for k in ("maxSpawnDepth", "maxConcurrent", "runTimeoutSeconds"):
        if k not in sub:
            sub[k] = inc_sub[k]
            changes.append(f"set agents.defaults.subagents.{k}={sub[k]}")
    old_allow = sub.get("allowAgents", [])
    new_allow = merge_list_allow_agents(old_allow, inc_sub["allowAgents"])
    if set(new_allow) != set(old_allow):
        sub["allowAgents"] = new_allow
        changes.append(f"merge agents.defaults.subagents.allowAgents → {new_allow}")

    # agents.list
    agents_root = dict_get(cfg, "agents")
    existing_list = agents_root.get("list", [])
    new_list, list_changes = upsert_agents_list(existing_list, PLUGIN_CONFIG["agents"]["list"], force)
    agents_root["list"] = new_list
    changes.extend(f"agents.list: {c}" for c in list_changes)

    # plugins.entries.deep-research
    entries = dict_get(cfg, "plugins", "entries")
    existing_entry = entries.get("deep-research")
    merged_entry = merge_plugin_entry(existing_entry, PLUGIN_CONFIG["plugins"]["entries"]["deep-research"])
    if existing_entry != merged_entry:
        entries["deep-research"] = merged_entry
        changes.append("plugins.entries.deep-research: set/updated")

    return cfg, changes


def main() -> int:
    p = argparse.ArgumentParser(description="Merge deep-research plugin config into openclaw.json")
    p.add_argument("--config", type=Path, default=None, help="目标 openclaw.json 路径")
    p.add_argument("--force", action="store_true", help="覆写已存在的 agents.list 条目")
    p.add_argument("--dry-run", action="store_true", help="仅输出 diff，不写入")
    args = p.parse_args()

    path = args.config if args.config else default_config_path()
    print(f"=> 目标配置文件：{path}")

    cfg = load_json(path)
    cfg, changes = merge(cfg, args.force)

    if not changes:
        print("=> 无变更（deep-research 配置已完整存在）")
        return 0

    print("=> 变更列表：")
    for c in changes:
        print(f"   - {c}")

    if args.dry_run:
        print("=> --dry-run：未写盘")
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return 0

    # 备份
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        print(f"=> 备份旧配置到：{backup}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"=> 已写入：{path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
