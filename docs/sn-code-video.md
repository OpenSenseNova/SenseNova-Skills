# Code-driven Video Creation

English | [简体中文](sn-code-video_cn.md)

[`sn-code-video`](../skills/sn-code-video/SKILL.md) turns a brief into a playable
MP4 made with code. It covers explainers, procedural animation, motion graphics,
promos, 3D scenes, and music-led films, with optional narration, music, and effects.
Use `sn-motion-html` for scroll-driven web stories.

## Requirements

- An Agent Skills-compatible agent with shell access and image viewing for frame review.
- Node.js 18+ for browser capture; use the newer Node version required by your agent runtime.
- Python 3 and FFmpeg/ffprobe with libx264, AAC, and the filters used by the checking scripts
  (`drawtext`, `blackdetect`, `freezedetect`, `ebur128`, `astats`, and `silencedetect`).
- Fonts covering the requested language; inspect available fonts with `fc-list`.
- For browser rendering, project-local Playwright + Chromium or Puppeteer + its browser.
  Other renderers (for example Manim or Node Canvas) need their own dependencies.
- For sound, the Python dependencies in the skill's `requirements.txt`. `edge-tts`
  requires network access; `faster-whisper` transcription checks require model weights.

The bundled rendering and checking tools do not need a SenseNova image or video API key.
The agent's LLM is configured separately as described in [INSTALL.md](../INSTALL.md).

## Install and prepare

Install the complete `skills/sn-code-video/` folder using the repository's
[installation guide](../INSTALL.md#3-load-this-repos-skills). Keep its `references/`,
`scripts/`, and `requirements.txt` together.

The following commands start from the cloned **SenseNova-Skills repository root**.
If the skill is already installed in an agent, replace `SKILL_DIR` with that absolute path.

```bash
export SKILL_DIR="$PWD/skills/sn-code-video"
mkdir -p ../my-code-video
cd ../my-code-video
npm install playwright
npx playwright install chromium
```

On Linux, install missing Chromium system libraries using Playwright's documented
setup (`npx playwright install --with-deps chromium`) when system installation is available.
For the audio workflow, install dependencies in a project virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r "$SKILL_DIR/requirements.txt"
```

Rendering and all outputs belong in the **video project**. Set `SKILL_DIR` in each
new shell session; invoke the bundled tools by absolute path so copying the skill
into `~/.openclaw/skills/` or `~/.hermes/skills/` does not break script lookup.

## Ask the agent

> Use sn-code-video to make a 12-second, 1920×1080, 30 fps explainer of how a
> pendulum exchanges kinetic and potential energy. Use English labels and
> procedural sound effects, with no narration. Deliver out/final.mp4, source code,
> reproduction commands, SPEC.md, VERIFY.md, and a contact sheet. Read the relevant
> references, review the rendered frames, and verify the final file.

## Workflow and tools

1. Read only the matching craft references from the skill's routing table.
2. Write `SPEC.md`: exact copy, facts, assets, duration, dimensions, frame rate,
   sound policy, and checkable requirements. For a long film, also write `STRUCTURE.md`.
3. Implement each frame as a deterministic function of time. For browser capture,
   expose `window.seek(t)` and set `window.READY = true` after fonts and assets load.
4. Smoke-test a few frames, render a rough full-length film, then refine it.
5. Review key stills, a contact sheet, action strips, and normal-speed playback;
   complete at least two review passes.
6. When audio is required, read the sound reference, write `SOUND.md`, and export
   events from the animation timeline. Build sound from those events, mux, and verify.
7. Check the actual final file and record each requirement's evidence in `VERIFY.md`.

Run these from the video project (the example expects `index.html` to be ready):

```bash
node "$SKILL_DIR/scripts/capture.mjs" . --page index.html \
  --fps 30 --dur 12 --size 1920x1080 --frames 3 --out out/smoke.mp4
node "$SKILL_DIR/scripts/capture.mjs" . --page index.html \
  --fps 30 --dur 12 --size 1920x1080 --out out/video.mp4
sh "$SKILL_DIR/scripts/contact_sheet.sh" out/video.mp4 out/sheet.jpg 1
sh "$SKILL_DIR/scripts/check_video.sh" out/video.mp4 1920 1080 30 12 12 0
```

`capture.mjs` produces a silent MP4. The last argument of `check_video.sh` is `0`
(no audio), `1` (audio required), or omitted (report audio without enforcing it).
For a film with sound, mux it into `out/final.mp4`, check that final file with `1`,
and also run:

```bash
sh "$SKILL_DIR/scripts/audio_check.sh" out/final.mp4 -14
python3 "$SKILL_DIR/scripts/sync_check.py" out/final.mp4 build/events.json --fps 30
```

The eight references cover explainers, stylized looks, simulations, character
motion, Three.js scenes/cameras, motion graphics/promos, sound/narration, and music sync.
The sound reference documents `tts.py` and the importable `synth.py` sound kit.

## Deliverables and failure handling

Deliver the final MP4, editable source and assets, reproduction commands,
`SPEC.md`, `VERIFY.md`, and a contact sheet. Keep sound stems and timing data when used.

If Chromium cannot run, fix the missing dependencies or switch to a suitable
Node Canvas/Manim renderer. If TTS is unavailable, report the missing narration;
do not substitute a silent track and mark the requirement as passed. Record
unresolved rendering, visual, or audio gaps explicitly in `VERIFY.md`.

## Source

Adapted from OpenSenseNova's
[`code-video` skill](https://github.com/OpenSenseNova/SenseNova-6.8-Code2Video/tree/776ae79824e338ba5d63fef66167455edc94ad26/skills/code-video).
The integration uses this repository's `sn-` naming and `references/` layout while
preserving the original production workflow, eight craft guides, and seven helpers.
