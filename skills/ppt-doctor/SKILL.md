---
name: ppt-doctor
description: |
  Environment diagnostic for the PPT family. Validates u1-image-base, API keys,
  Node runtime, and optional deps; interactively writes .env for required vars.
  Runs before ppt-entry; does not modify u1-* skills.
metadata:
  project: SenseNova-Skills
  tier: aux
  category: diagnostic
  user_visible: true
triggers:
  - "ppt-doctor"
  - "ppt 体检"
---

# ppt-doctor

## When to use

- Before the first time you use `ppt-entry` / `ppt-creative` / `ppt-standard`, to verify env is wired
- After you change `.env`, to confirm
- When `ppt-entry` reports missing-env error and tells you to come here

## Hard checks (must pass before ppt-entry can run)

1. `U1_LM_API_KEY` is set
2. `U1_LM_BASE_URL` is set
3. `U1_API_KEY` is set
4. `u1-image-base` is discoverable and `openclaw_runner.py --help` works
5. `node --version` >= 18

## Soft checks (warnings only)

- `PPT_DECK_ROOT` writable (or cwd can create `ppt_decks/`)
- `ppt-standard/scripts/export_pptx/node_modules` exists (run `npm install` on first use otherwise)
- Optional env vars (`U1_IMAGE_GEN_*`, `VLM_*`, `LLM_*`) — displays current value or "unset"
- `pypdf` / `python-docx` Python deps for doc parsing in ppt-entry

## Invocation

```bash
python -m ppt_doctor                # from repo root; interactive
python -m ppt_doctor --non-interactive
python -m ppt_doctor --env-path /custom/.env
```

When used inside OpenClaw, `/skill ppt-doctor` runs the same entry.

## Output

Plain text report — one line per check — then a summary. On any hard-check failure, enters interactive mode to fill `.env` (unless `--non-interactive`).

## Does NOT

- Modify `u1-*` skills or their `.env`
- Install packages automatically (prints install commands instead)
- Run any PPT pipeline
