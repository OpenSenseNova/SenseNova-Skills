import asyncio
import tempfile
from pathlib import Path

from PIL import Image

from sn_image_base.generation.sensenova import (
    IMAGE_EDIT_ENDPOINT,
    SensenovaText2ImageClient,
)


async def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        image_path = Path(directory) / "source.png"
        Image.new("RGB", (1, 1), "red").save(image_path)
        client = SensenovaText2ImageClient(
            api_key="test-key",
            base_url="https://token.sensenova.cn/v1",
            model="sensenova-u1.5-lite",
        )
        captured: dict = {}

        async def capture(payload, endpoint, _output_path, _output_format, _filename_prefix):
            captured.update(payload=payload, endpoint=endpoint)
            return {"status": "ok"}

        client._request_and_save = capture  # type: ignore[method-assign]
        result = await client.edit(
            "Change the background",
            [str(image_path), "https://example.com/reference.png"],
        )
        assert result["status"] == "ok"
        assert captured["endpoint"] == IMAGE_EDIT_ENDPOINT
        assert captured["payload"]["model"] == "sensenova-u1.5-lite"
        assert captured["payload"]["n"] == 1
        assert captured["payload"]["size"] == "auto"
        assert captured["payload"]["watermark"] is False
        assert captured["payload"]["prompt_extend"] is True
        assert captured["payload"]["images"][0]["image_url"].startswith("data:image/png;base64,")
        assert captured["payload"]["images"][1]["image_url"] == "https://example.com/reference.png"
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
    print("image edit self-check: ok")
