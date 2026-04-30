---
name: sn-update
description: |
  Update SenseNova Skills (the sn-* bundle) inside an OpenClaw or hermes-agent
  install. ALWAYS use this skill when the user says any of: "update SenseNova
  skills", "update SN skills", "更新 sensenova skills", "更新 sn skills",
  "刷新 sn-*", "升级 sn-* skills", or names a specific sn-* skill to update
  (e.g. "更新 sn-ppt-standard", "refresh sn-image-base"). Default scope is the
  whole sn-* bundle; if the user names specific skills, update ONLY those.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: meta
  user_visible: true
triggers:
  - "sn-update"
  - "更新 sn"
  - "更新 sensenova"
  - "update sn skills"
  - "update sensenova skills"
---

# sn-update

Refresh installed `sn-*` skills from upstream
[SenseNova-Skills](https://github.com/OpenSenseNova/SenseNova-Skills).

---

## Decide the scope

- No list given → every `sn-*` skill upstream.
- Specific skills named → only those. Don't expand.
- A named skill missing upstream → surface as error and stop.
- User said "force / 强制" → re-install even when up-to-date.

---

## Decide the target agent

Check which directories exist:

| `~/.openclaw/skills/` | `~/.hermes/skills/` | Target |
|---|---|---|
| exists | absent | openclaw |
| absent | exists | hermes |
| exists | exists | **ask the user** — never silently dual-write |
| absent | absent | no install found, stop |

---

## Sync the upstream repo

Persistent cache at `~/.cache/sn-update/repo/`. Default URL:
`https://github.com/OpenSenseNova/SenseNova-Skills.git`. User may override
with a fork URL.

- **First run**: partial clone (`--filter=blob:none`) — keeps the cache
  small while preserving history metadata for SHA queries.
- **Subsequent runs**: fetch + hard-reset to the upstream default branch.
- **URL changed**: if cache's `origin` differs from the requested URL,
  delete and re-clone.

---

## Compare versions per skill (A → B → C)

For each skill, pick the highest-precedence signal present on **both**
sides (installed + upstream); equal → skip, differ → install.

Upstream "version" is the per-subtree commit SHA — using repo HEAD would
mark unrelated skills as stale every time:

```text
git -C <cache> log -1 --format=%H -- skills/<skill-name>
```

- **A — `.sn-version` marker**: one-line file inside the installed skill
  holding the SHA from its last install.
- **B — `.sn-release` marker** (fallback): one-line file holding the
  upstream tag name. Compare against `git describe --tags --abbrev=0`.
- **C — `version:` field in SKILL.md frontmatter**: parse from YAML on
  both sides.
- **Nothing usable** → treat as stale and install.

Always write `.sn-version` on install so future runs can use A.

---

## Install with backup

For each skill flagged "install":

1. **Move** (not copy) any existing `<agent-skills>/<skill-name>/` into a
   single timestamped backup bucket shared by all skills in this run:
   `~/.<agent>/skills_backup/<UTC-timestamp>/<skill-name>/`
   (e.g. `2026-04-30T15-29-07Z`).
2. **Copy** `<cache>/skills/<skill-name>/` → `<agent-skills>/<skill-name>/`.
3. **Write `.sn-version`** with the upstream subtree SHA inside the new copy.

If the bucket ends up empty (all targets were fresh installs), remove it.

The backup tree is a **sibling** of `skills/`, never a `.bak` folder
inside it — most agent runtimes scan the whole `skills/` directory and
would pick up stale duplicates.

---

## Enforce backup retention

After every run, prune the per-agent backup root to **at most 3** buckets.
Timestamps sort lexicographically; keep the newest 3, delete the rest.
Run this even when the current run produced no backup of its own.

---

## Report to the user

Group by status, keep it short:

```text
Updated (3): sn-ppt-standard, sn-image-base, sn-deep-research
Already up-to-date (5): sn-ppt-creative, sn-ppt-doctor, ...
Backup: ~/.openclaw/skills_backup/2026-04-30T15-29-07Z/
```

- Omit `Backup:` when nothing was backed up.
- Show SHA pairs (`abc1234 → def5678`) only if the user asks for detail.
- Errors get their own line — never bury them in a success summary.

---

## Edge cases

- **Asks to delete sn-* skills** — not this skill's job. Decline; point at
  `~/.<agent>/skills_backup/` if they want to roll back.
- **User is in the dev repo** and asks to "update sn skills" — they mean
  push to their agent install. Proceed normally; this skill only touches
  the cache and the agent install dirs, never the dev checkout.
- **`sn-update` updating itself** — fine; the new copy takes effect on
  the next invocation.
