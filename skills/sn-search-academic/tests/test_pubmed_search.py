"""PubMed search regression tests."""

import importlib
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

normalize_pmc_id = importlib.import_module("pubmed_search").normalize_pmc_id


class NormalizePmcIdTests(unittest.TestCase):
    """Verify that PMC normalization removes only an actual prefix."""

    def test_removes_case_insensitive_pmc_prefix(self) -> None:
        self.assertEqual(normalize_pmc_id(" PMC123 "), "123")
        self.assertEqual(normalize_pmc_id("pmc456"), "456")

    def test_preserves_other_leading_characters(self) -> None:
        self.assertEqual(normalize_pmc_id("PMCC456"), "C456")
        self.assertEqual(normalize_pmc_id("PMP500"), "PMP500")
        self.assertEqual(normalize_pmc_id("C123"), "C123")


if __name__ == "__main__":
    unittest.main()
