---
name: sn-code-video
description: Create and revise code-driven videos with Canvas, SVG, HTML/CSS, Three.js, Remotion, Manim, or p5.js, including sound, deterministic frame capture, visual review, and MP4 verification. Use for rendered explainers, procedural animations, motion graphics, promos, and music-synchronized films; not for general web apps, scroll-driven HTML stories, or footage generation with video models.
---

# SN Code Video

A code video is a program `frame(t) → image`, sampled at `t = i / fps` and encoded. Almost every failure in this kind of work is one of four things: the film is never finished, the picture depends on wall-clock time, nobody looked at the frames, or the file does not match the brief. This skill prevents those four.

## Setup and paths

Use a separate project folder for the video source, `SPEC.md`, build files, and outputs. Resolve `SKILL_DIR` to the absolute directory containing this `SKILL.md`, whether installed in the agent's skills directory or used from this repository. Run project commands from the video project folder; invoke bundled scripts through `"$SKILL_DIR/scripts/..."` so they do not depend on the current working directory. Set `SKILL_DIR` again in each shell session if needed.

Requirements: Node.js 18+ for browser capture, Python 3, FFmpeg/ffprobe with libx264 and AAC, and fonts covering the requested language. Install Playwright (with Chromium) or Puppeteer in the **video project**; the capture helper resolves its packages there first. Python audio dependencies are listed in `requirements.txt`; edge-tts needs network access, and faster-whisper needs downloaded model weights for transcription checks. Install only the tools required by the chosen renderer and audio workflow. Setup and invocation examples: [English guide](../../docs/sn-code-video.md) / [中文指南](../../docs/sn-code-video_cn.md) in the source repository; these repository guides are not required when the skill folder is installed on its own.

Deliver the playable MP4, source code and reproduction commands, `SPEC.md`, `VERIFY.md`, and a contact sheet. Audio stems and timing data belong in the project when sound is used.

## 0. Read the craft guides you need

Reference paths are relative to this skill folder; output and input paths in commands are relative to the video project. Besides this file it holds craft guides in `references/` and helper scripts in `scripts/` (audio packages in `requirements.txt`). Read every guide that matches the request before writing `SPEC.md`; most videos need two or three.

| Guide | Read when the request has… |
|---|---|
| [`references/explainer-diagrams.md`](references/explainer-diagrams.md) | anything to teach or explain: math, science, history, processes, data |
| [`references/stylized-looks.md`](references/stylized-looks.md) | a named style, medium or artist (ink wash, pixel art, cut paper, vaporwave, watercolour, …) |
| [`references/simulations-and-generative.md`](references/simulations-and-generative.md) | particles, flocks, cellular automata, physics, fields, shaders, generative patterns |
| [`references/character-and-creature-motion.md`](references/character-and-creature-motion.md) | people, animals or creatures that move or act |
| [`references/threejs-scenes-and-cameras.md`](references/threejs-scenes-and-cameras.md) | a 3D scene, product or camera move |
| [`references/motion-graphics-and-promos.md`](references/motion-graphics-and-promos.md) | kinetic type, UI, logos, product or brand promos |
| [`references/sound-design-and-narration.md`](references/sound-design-and-narration.md) | any audio: narration, music, effects, ambience |
| [`references/music-and-beat-sync.md`](references/music-and-beat-sync.md) | music-led films, beat-cut picture, supplied tracks or lyrics |

A request that names a style always needs [`references/stylized-looks.md`](references/stylized-looks.md), and a film with any audio always needs [`references/sound-design-and-narration.md`](references/sound-design-and-narration.md).

## 1. Finish the film

- The deliverable is a playable video that meets the brief. Code, stills, a plan or a preview are intermediate results. Keep working until the final file exists and has passed section 6.
- Decide composition, palette, easing and implementation details yourself and note the choices in `SPEC.md`. Ask the user only about the few open choices that would change the whole film (for example language, aspect ratio, length, or whether there is a voice), and only when you can ask; otherwise choose a sensible default and say which.
- Budget the time. Get a rough full-length render early (even ugly), then improve it. A finished, slightly plain film beats an unfinished ambitious one.
- Timebox sub-problems. If one problem (recalling an exact pattern or constant, tuning one effect, chasing one bug) has taken about 30 minutes without visible progress, change approach: simplify the effect, derive the value from its definition, use the reference data in the craft guides, or fall back to a design that does not need it. Do not spend hours reconstructing data from memory.

## 2. Turn the brief into a spec

Before writing code, write `SPEC.md` in the project folder:

- **Format:** width × height, fps, duration (target and allowed range), frame count = round(duration × fps), loop or not, and audio: required, forbidden, or left open. When it is open, decide from the brief whether sound would serve the film (section 10). Write the sound requirements (type, voice language, fixed lines, sync points) into the spec too.
- **Exact copy:** every on-screen string the brief fixes, verbatim, in order. Nothing else may claim facts, prices or specifications.
- **Facts and numbers:** every value the picture must show or obey (dates, physical constants, data values, counts). Note the source the brief gives.
- **Assets:** each supplied file and how it must be used (unaltered logo, screenshot fidelity, photo kept photographic).
- **Must-haves:** one line per requirement in the brief ("camera orbits counterclockwise ~90°", "dominoes never interpenetrate"). Each line becomes a check in section 6.

Choose the stack for the content, not out of habit:

| Content | Good default |
|---|---|
| 2D diagrams, math, particles, pixel art, painterly textures | Canvas 2D (browser or `@napi-rs/canvas` in Node) |
| Crisp vector shapes, UI, kinetic type, logos | SVG / HTML+CSS driven by a paused timeline, or Remotion |
| LaTeX-heavy math | Manim (or KaTeX/MathJax rendered to SVG) |
| 3D scenes, products, cameras | Three.js (see [`references/threejs-scenes-and-cameras.md`](references/threejs-scenes-and-cameras.md)) |
| Shaders, aurora, fields, post effects | WebGL / GLSL fragment shaders |

## 3. Time is the only input

- Expose one entry point that draws the exact state at time `t`, for example `window.seek = async (t) => {...}` plus `window.READY = true` once fonts and images are loaded. Frame `i` is rendered at `t = i / fps`.
- The same `t` must always give the same image, in any order, in a fresh page. Forbidden: `Date.now()`, `performance.now()`, `requestAnimationFrame` loops that advance state, CSS transitions/animations left running, a playing GSAP timeline, unseeded `Math.random()`, state carried over from the previous frame.
- GSAP: build a `paused: true` timeline and call `tl.seek(t)`. CSS animations: set `animation-play-state: paused` and a negative `animation-delay`, or compute styles from `t` yourself. Remotion: derive everything from `useCurrentFrame()`.
- Randomness: seed once, then keep values. A tiny seeded generator is enough:

```js
function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
```

- Simulations (physics, flocks, cellular automata, crowds) are computed once with a fixed time step and seed, stored, and sampled by `t` (interpolate between stored steps). Never integrate inside the render call.
- Easing: write it as functions of `t` (`smoothstep`, cubic in/out, closed-form damped springs). A value that changes target several times is a sum of eased segments, still a pure function of `t`.

## 4. Capture and encode

- **Browser pages:** `scripts/capture.mjs` serves the project folder, opens the page in headless Chromium (Playwright or Puppeteer, resolved from the project's `node_modules` first), calls `seek(t)` for each frame and pipes screenshots into ffmpeg:
  `node "$SKILL_DIR/scripts/capture.mjs" <project_dir> --page index.html --fps 30 --dur 12 --size 1920x1080 --out out/video.mp4`
  Test it on 2–3 frames (`--frames 3`) before anything else. If Chromium cannot start (for example missing system libraries) and you cannot fix that quickly, switch early to a path that needs no browser: Canvas 2D in Node with `@napi-rs/canvas`, or Manim. Do not spend your time fighting the browser.
- **Node canvas:** draw each frame with `@napi-rs/canvas` and write raw RGBA to ffmpeg's stdin (`-f rawvideo -pix_fmt rgba -s WxH -r FPS -i -`).
- **Remotion / Manim:** use their own renderers, then re-encode if the codec or pixel format differs from the spec.
- Encode for compatibility: `-c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium -movflags +faststart`. A film without sound has no audio stream (`-an`), not a silent track. Sound is muxed in a separate step (section 10). Width and height must be even.
- Headless WebGL may fall back to software rendering, which is slow. Measure the time per frame on a short range first and plan the full render from it. Render previews at half resolution if needed, but the final at full size.
- Keep each render in a new versioned path; never overwrite the last good film until the new one passes its checks.
- **Frame budget:** before building the whole film, time one full-resolution frame of the busiest moment. Aim for roughly ≤ 300 ms/frame (a 100 s film at 30 fps is then 15 min per full render) so that several review passes fit. If a hand-written NumPy/PIL compositor is far slower, do not optimize it for hours: move the drawing to Canvas 2D or WebGL, which composite layers natively. In NumPy, avoid per-frame work on whole huge textures (boolean-mask assignment into multi-thousand-pixel float arrays, full-frame `np.roll`); crop to the visible window and precompute static layers once.
- **Long renders:** a 2-minute film at 30 fps is 3,600 frames. Measure ms/frame early and multiply. Render independent chunks in parallel with `--start` and `--frames` (each chunk to its own file, all from the same `seek(t)` code), then join them losslessly: list the chunks in `chunks.txt` (`file 'part_000.mp4'` …) and run `ffmpeg -f concat -safe 0 -i chunks.txt -c copy video.mp4`. Check the joined frame count.

### Long jobs and background processes

- **Smoke-test before a long run.** Run any bake, simulation or render on a tiny case first and assert that it does something: state changes after N steps, the output file grows, an invariant holds. A stepping function whose result is never assigned bakes nothing for half an hour.
- Write each run to a new file name and print progress with `flush=True` to a log. Before you inspect a result, confirm it came from the run you just started (timestamp, a config line in the log), not from an older file.
- Record the PID of a background job (`echo $! > build/sim.pid`) and stop it with `kill $(cat build/sim.pid)`. `pkill -f <pattern>` can match your own shell command and kill it.
- The machine may be shared with other jobs. Measure throughput on the real run and re-plan from that; do not assume an earlier measurement still holds.

## 5. Look at the frames

Pixels are the only evidence. Repeat this loop at least twice.

You know what the code is meant to draw, so you will tend to see it in the frame even when it is not there. Read every still in two steps:

- **Cold read first.** Describe the image as a stranger would, without thinking of the code: what is the main subject, could someone name it within a second, how large is it, what is the brightest and most contrasting thing, what can be read. Write that description down.
- **Then compare** it with the brief. Every required object must show up in the cold read. If the brief says "koi" and the cold read says "a dark arrow-shaped blob", the koi is not there yet, whatever the code is meant to draw.
- **Measure, do not estimate:** the subject's bounding box at key moments (at least about 1/3 of the frame height unless the brief wants it small), the smallest text height in pixels (at least about 28 px at 1080p), and whether the hero effect is brighter or more contrasting than the background details around it.

1. **Stills first.** Render the few moments that carry the most risk (the brief usually names them), view them directly, and fix the problems before rendering the whole film.
2. **Contact sheet.** After a full render: `sh "$SKILL_DIR/scripts/contact_sheet.sh" out/video.mp4 out/sheet.jpg 1` (one frame per second; use 2 s steps and 8 columns for films over a minute) and read it end to end: composition, readability, continuity, empty or broken frames, and for long films whether sections look alike.
3. **Action strips.** For every key action (a collision, a morph, a catch, a reveal), extract frames 0.1–0.2 s apart around it. Stills hide teleports, pops and sliding; strips show them.
4. **Watch at normal speed.** Then name the weakest moment, fix it, re-render, compare both versions and keep the better one.

Readability rule of thumb: after a text finishes animating in, hold it about `letters / 15 + 1.5` s (English) or `characters / 4.5 + 1.5` s (Chinese); a title card at least 2 s in a short film. Never shrink text below about 28 px at 1080p to make it fit.

## 6. Verify before delivery

Run `sh "$SKILL_DIR/scripts/check_video.sh" out/final.mp4 1920 1080 30 10 15` (add `1` or `0` at the end to require or forbid an audio stream). It reports resolution, fps, duration, frame count, codec, pixel format, audio streams and their length, black segments and frozen segments, and fails on mismatches. Then go through `SPEC.md` line by line against the actual frames and write `VERIFY.md`: each must-have, pass/fail, and the timestamp or still that shows it. Do not write "checked" for anything you did not look at.

Evidence in `VERIFY.md` is what the pixels show, not what the code does. "Pavilion mid-slope, drawn by `draw_pavilion()`" is not evidence. "t=38 s still: a small roofed pavilion is visible at about (820, 410), about 60 px tall" is. If the pixels do not show a must-have clearly, mark it FAIL and fix it, or list it as a known gap.

## 7. Failures seen most often

| Symptom | Cause | Fix |
|---|---|---|
| Video plays too fast or jitters | Animation driven by wall clock or rAF during capture | Drive everything from `t` |
| First frames blank or fonts wrong | Captured before fonts/images loaded | Set `READY` after `document.fonts.ready` and image decode |
| Particles or textures shimmer | Randomness re-drawn every frame | Seed once, store per-object values |
| Subject too small or pushed to an edge | Never checked stills at final size | Subject ≥ 1/3 frame height at key moments |
| Subject not recognizable (a koi that reads as a leaf, a mountain that is a triangle) | Shape built from primitives and judged against intent | Cold read (section 5); design the silhouette first and check it at thumbnail size |
| Hero effect weak (tiny, dim fireworks; reflections brighter than the bursts) | Background details compete with the subject | Make the subject the highest-contrast element; dim the rest |
| Hours lost reconstructing a pattern or constant | Recalled from memory and debugged by trial | Timebox (section 1); use reference data in the craft guides |
| Text overlaps or leaves the frame | Positions estimated, not measured | Measure text boxes with the real font; keep a 5% safe margin |
| Duration or fps off by a few frames | Rounding or a CSS/GSAP duration mismatch | Frame count = round(dur × fps); check with `check_video.sh` |
| Invented claims on screen | Copy written from memory | Only the strings in `SPEC.md` |

## 8. Long films (1–2 minutes)

- **Plan the structure before coding.** Write `STRUCTURE.md`: the sections or movements in order, what each one shows and changes, roughly how long each takes, and how each hands over to the next. Total the estimates against the target length.
- **Every section needs its own visual state** (a new scale, place, palette, camera, density or mechanism) and something meaningful should change at least every few seconds. The typical failure of a long code film is one effect repeated for two minutes.
- **Vary the pace:** a hook early, the main content in the middle with at least one acceleration and one breathing pause, a clear ending that echoes the opening.
- **Continuity:** keep one world, one palette logic and one type system across sections; transitions grow out of shared shapes or motion rather than generic fades.
- **Work in passes:** get a rough full-length cut early (simple shapes, real timing), then refine section by section. Re-render only the sections you changed (chunks) and re-join.
- **Review budget:** check stills from every section, not just the opening. Watch the whole film at least twice before delivery.

## 9. Seamless loops

When the brief asks for a loop, make every animated quantity periodic with a period that divides the loop length (rotations, oscillations, noise offsets, camera paths, overlay grain). Frame `N` would equal frame `0`; render frames `0 … N-1`. Check by playing the end into the start and by comparing the last and first frames: they must be consecutive states, not duplicates. Simulations that must loop are designed on the loop period from the start (see [`references/simulations-and-generative.md`](references/simulations-and-generative.md)).

## 10. Sound

- The brief says whether the film has sound and what kind (narration, voiceover, music, effects, ambience, sonification). When it says nothing, a film usually benefits from music and effects; choose a sound plan that fits and state it in `SPEC.md`. When it asks for sound, plan and build it with [`references/sound-design-and-narration.md`](references/sound-design-and-narration.md); for music-led films also [`references/music-and-beat-sync.md`](references/music-and-beat-sync.md). When it says no audio, deliver no audio stream.
- Sound is built from the same timeline as the picture: export the animation's events and state, then synthesize and place sounds from them. Never hand-type a second timing list.
- Deliver stereo AAC at 48 kHz, exactly as long as the video, mastered to about −16 to −14 LUFS with true peak ≤ −1 dBTP, and check it with `scripts/audio_check.sh` and `scripts/sync_check.py`.

## 11. Assets, fonts and tools

- Supplied assets are used as given: no recolouring, stretching or redrawing of logos; UI rebuilt in code must match the screenshots; photos stay photographic.
- Prefer the tools and fonts that are already installed; check fonts with `fc-list`. Use fonts from the environment or from the project's `assets/` (install others only if you may, and respect their licences); check that every glyph renders (no tofu boxes, especially for Chinese).
- The picture is made by code. Use image or video generation models, stock footage or downloaded artwork only when the user asks for them or supplies them.

### Video assets inside the film

When the brief supplies video clips to show inside the film (in a card, a screen, a wall of tiles):

- **Probe first:** `ffprobe` each clip for size, fps, duration and audio. Write in `SPEC.md` which window of which clip appears where (clip in/out time, film start time, speed, size on screen).
- **Do not play `<video>` elements during capture.** Seeking a video in headless Chromium is asynchronous, slow and may show the wrong or a blank frame. Extract each window to an image sequence first, at the film's fps and the size it is shown at:
  `ffmpeg -ss IN -t DUR -i assets/clip.mp4 -vf "fps=30,scale=1280:720" -q:v 3 build/clips/clip/%04d.jpg`
  Preload the images before `READY`. In `seek(t)`, draw frame `floor((t - start) * fps)`, clamped to the window, so frame `i` of the film always shows the same clip frame. Several tiles of the same clip can reuse one sequence with different offsets.
- If the clip's fps differs from the film's, let `fps=` in the extraction resample it; never change the speed by dropping or repeating frames by hand.
- Many large tiles can exhaust memory: extract small sizes for small tiles, and count the images before loading (frames × tiles).
- For Node canvas or Python renderers, the same idea applies: load the extracted frames, or read them on the fly with one ffmpeg process per clip piping raw frames.
- **Clip audio** is ignored unless the brief asks for it. If it does, extract the same window with ffmpeg (`-ss IN -t DUR -vn`) and mix it as its own stem, aligned to the film start time.
- **Check:** at two or three times per clip, put the film frame next to the source frame extracted straight from the asset at the matching clip time; they must show the same moment (same content, not shifted by a few frames, not mirrored or stretched).
