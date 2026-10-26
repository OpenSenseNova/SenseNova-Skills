# Seedance integration

Use the current official model documentation when model IDs or supported parameters may have changed. The reusable script targets the Ark asynchronous content-generation API.

## Request flow

- Base URL: `https://ark.cn-beijing.volces.com/api/v3`
- Create: `POST /contents/generations/tasks`
- Poll: `GET /contents/generations/tasks/{id}`
- Terminal states: `succeeded`, `failed`, `cancelled`, and sometimes `expired`
- Download `content.video_url` immediately after success; provider URLs are temporary.

The default content array is a text prompt followed by one or two local images encoded as data URLs. `reference_images` sends each with `role: reference_image`. `first_last` sends connector frames with `first_frame` and `last_frame` roles.

## Configuration

Keep these in the project manifest rather than the script:

- model ID;
- requested duration, resolution, and ratio;
- audio and watermark policy;
- conditioning mode;
- dive and connector records.

Keep credentials in `.env`:

```dotenv
ARK_API_KEY=
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
SEEDANCE_MODEL=
```

`SEEDANCE_MODEL` is an optional runtime override. Never send a key to the frontend or include it in task metadata.

## Concurrency and recovery

Use a bounded thread pool. Run dives first; a connector cannot begin until both adjacent dive boundary frames exist. Within each phase, clips are independent and can run concurrently. Start with four workers unless the account's documented quota suggests another value.

Skip non-empty final outputs unless `--force` is explicit. Save task IDs and sanitized request metadata so interrupted runs can be audited. Do not record the Authorization header, data URLs, or secrets.

Retry transient task or network failures at most once by default. Do not retry `ModelNotOpen`, authentication, access, billing, or invalid-parameter failures without a configuration change.

## Normalization

For interactive frame scrubbing, provider output is an input, not the final web asset. Normalize with FFmpeg to a fixed canvas, constant frame rate, exact duration, H.264 `yuv420p`, short GOP, no audio when silent, and `+faststart`. Extract boundary frames from the normalized dives, not from the source stills.

## Motion prompts that survive the model

If a connector returns a calm following shot instead of its planned dive or crane move, make that camera event the subject of the prompt and describe its physical stages. For a connector that calls for decisive motion, use a direction such as:

> The camera move itself is the subject of this shot: make the displacement large, decisive and clearly readable — NOT a calm following shot, no slow drift, no tracking behind a walking figure (any figure stays small and incidental).

Keep ONE continuous move per clip. Stacking three stages into a five-second clip — pass through a gate, climb to an aerial view, dive onto the destination — can produce a hard cut at a stage boundary or hide the jump behind an object sweeping across the lens. When this happens, simplify the path and let one move carry the clip: through the archway, then along the approach road while the destination grows. Forbid the escapes explicitly (`no cut, no wipe, no object sweeping across the lens, no black frame, no scene jump; the environment must evolve gradually`) and inspect the result rather than assuming those constraints were followed.

Decisive motion does not conflict with the shared style preamble: rendering, palette and material continuity stay in the preamble, speed and displacement stay in the per-clip prompt.

## First-clip gate

Within the authorized scope, test a representative scene clip and representative connectors for the materially different motion types before their full batches. A successful slow scene clip proves neither pass-through nor aerial-transition quality. Reuse previously accepted tests when their inputs and motion requirements still apply.

1. `ffprobe` the normalized file and require the declared codec (`h264`, `yuv420p`), canvas, constant frame rate, exact duration, expected frame count, and the declared audio policy. For a silent project, require **no audio stream**.
2. Extract start, middle, and end frames with `ffmpeg -ss <t> -frames:v 1` and check each for burned-in text or watermarks, structural deformation, extra faces, and flicker. Judge deformation on at least two frames, since a single frame cannot show it.
3. Build a side-by-side composite of the source still next to extracted frame 0 (Pillow) and compare style and elements directly. Judging "is this still the same style?" from the video frame alone is unreliable; the composite makes the drift visible.
4. Separate cosmetic drift from motion failure. A small rendering change can be recorded as acceptable if the approved visual direction survives. A requested pass-through or aerial dive replaced by a gentle follow, dissolve or morph fails the shot intent even if architecture, characters and endpoints match.
5. Inspect each connector with a frame-number progression sheet — one command, no seeking: `ffmpeg -i clip.mp4 -vf "select='eq(n\,14)+eq(n\,43)+eq(n\,72)+eq(n\,101)',scale=420:-1,tile=4x1" -frames:v 1 sheet.jpg`. Then sample densely, every 0.3–0.4 s, across any region where a cut is suspected and read adjacent frames for a whole-picture jump. A specified pass-through or aerial dive replaced by a dissolve, morph or walking follow fails even when endpoints and file specs match; endpoints plus a midpoint can sit either side of a hidden cut and still look continuous.
6. Check the landing margin, not just the arrival: the destination landmark must already be legible with about a second of clip left. A transition that resolves through a cloud or light dissolve only in the final second is endpoint-correct and still reads as unfinished.
7. Apply the planned event's criteria: pass-through needs approach, near-field parallax and exit reveal; rise-and-dive needs departure shrinking, a legible elevated viewpoint, then descent toward the destination. Record observed phases, timestamps, missing motion and pass/fail in video QA. Endpoint fidelity and encoding checks cannot override failed motion.

Revise the affected prompt, boundary framing or duration before a replacement request. Keep accepted clips and failed variants; new paid variants need new IDs within the user's authorized scope. Do not claim that CSS zoom repairs a missing physical camera path.

Official references:

- https://www.volcengine.com/docs/82379/1520757?lang=zh
- https://www.volcengine.com/docs/82379/1521309?lang=zh
