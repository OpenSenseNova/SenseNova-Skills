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

Official references:

- https://www.volcengine.com/docs/82379/1520757?lang=zh
- https://www.volcengine.com/docs/82379/1521309?lang=zh
