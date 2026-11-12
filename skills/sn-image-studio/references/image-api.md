# Image size handling

SenseNova API documentation:
https://platform.sensenova.cn/docs (SenseNova U1.5 Lite, synchronous image generation, `size`).

- Each output edge must be 512–4096 pixels and a multiple of 32.
- Width-to-height ratio must be between 1:3 and 3:1, inclusive.
- The documented 2K landscape recommendation is 2720×1536. 16:9 is a nominal ratio, not a strict API upper bound.

For text-to-image, Studio resolves “sample ratio” from the pinned case's width and height. `images.py` scales that ratio toward a 2048² or 4096² pixel budget, caps the longest edge at 4096, rounds both edges to multiples of 32, and keeps rounding within the ratio boundaries. It validates the final pixel size before sending the request. Sample dimensions such as 2752×1536 are valid ratios and must not be rejected for being slightly wider than 16:9.

The 4K option remains scoped to `sensenova-u1.5-lite` in this client. Image editing retains its existing `size=auto` behavior so the provider adapts to the main input image.


## Execution timeouts

All default budgets live in `scripts/execution_limits.py`:

| Stage | Seconds |
| --- | ---: |
| Connect / acquire connection | 30 |
| Upload request | 120 |
| Wait for image API response | 900 |
| Download result | 120 |
| Image subprocess, total wall time | 1200 |
| Task script waiting for durable receipt | 1260 |
| Agent prompt turn, including image execution | 1800 |

HTTP timeouts limit inactivity in each network phase; the subprocess timeout caps total wall time. Outer budgets leave room for image download, decoding, receipt publication and Agent cleanup. The Agent is instructed to poll the same terminal execution if its tool has a shorter foreground limit.

Timeout errors identify the phase, configured limit and exception type. An empty exception message has a nonempty type-based fallback. A timeout after submission means the provider outcome may be unknown: no layer automatically retries a paid request. Updating these defaults requires restarting Studio when idle; copying the limits module into each new Agent job keeps its task script independent of the launching skill directory.
