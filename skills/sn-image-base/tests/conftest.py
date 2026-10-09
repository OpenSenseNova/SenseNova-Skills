"""Make the ``sn_image_base`` package importable from the tests directory.

The package lives in ``skills/sn-image-base/scripts/sn_image_base``; the tests
run from the repository root, so put that directory on ``sys.path``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
