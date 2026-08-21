import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CAPTION_SCRIPT = REPOSITORY_ROOT / "skills/sn-ppt-entry/scripts/caption_images.py"


class CaptionImagesTest(unittest.TestCase):
    def test_reports_malformed_input_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            deck_dir = Path(temp_dir)
            (deck_dir / "raw_documents.json").write_text(
                '{"documents": [{', encoding="utf-8"
            )

            result = subprocess.run(
                [sys.executable, str(CAPTION_SCRIPT), "--deck-dir", str(deck_dir)],
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("raw_documents.json", payload["error"])
        self.assertIn("invalid JSON", payload["error"])
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
