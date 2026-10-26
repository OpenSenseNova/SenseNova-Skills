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

## First-clip gate

Within authorized scope, test a representative scene clip and each materially different connector motion before their full batches. Reuse accepted tests when inputs and requirements still apply. Use [prompting.md](prompting.md) for camera planning, motion acceptance and style-drift criteria.

1. Use `ffprobe` to verify the declared canvas, constant frame rate, exact duration, frame count, `h264`/`yuv420p`, and audio policy. Silent projects require no audio stream.
2. Compare source still and frame 0 side by side; inspect a progression sheet for unwanted text, watermark, deformation and identity drift.
3. Play each connector to assess continuity and flicker. Inspect adjacent frames around suspected cuts; a sparse sheet can miss them. Record actual phases, timestamps and pass/fail against the approved shot plan.

For a normalized clip with at least four frames, sample across its actual frame count instead of assuming a duration or frame rate:

```bash
clip_frames=$(ffprobe -v error -select_streams v:0 -count_frames \
  -show_entries stream=nb_read_frames -of default=nw=1:nk=1 clip.mp4)
ffmpeg -i clip.mp4 -vf "select='eq(n\,0)+eq(n\,$(((clip_frames-1)/3)))+eq(n\,$((2*(clip_frames-1)/3)))+eq(n\,$((clip_frames-1)))',scale=420:-1,tile=4x1" \
  -frames:v 1 sheet.jpg
```

Keep accepted clips and failed variants; assign new IDs to authorized replacements. Encoding and endpoint fidelity cannot override failed motion, and CSS zoom cannot repair a missing camera path.

Official references:

- https://www.volcengine.com/docs/82379/1520757?lang=zh
- https://www.volcengine.com/docs/82379/1521309?lang=zh
