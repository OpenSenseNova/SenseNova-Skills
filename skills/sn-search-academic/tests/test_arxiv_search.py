"""Regression tests for arXiv query construction."""

import sys
import types
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    import arxiv  # noqa: F401
except ModuleNotFoundError:
    # Query construction is independent of the optional runtime client package.
    sys.modules["arxiv"] = types.ModuleType("arxiv")

from arxiv_search import build_search_query  # noqa: E402


class BuildSearchQueryTests(unittest.TestCase):
    def test_boolean_and_fielded_expression_is_not_quoted_as_a_phrase(self):
        self.assertEqual(
            "all:transformer AND cat:cs.AI",
            build_search_query("transformer AND cat:cs.AI"),
        )

    def test_boolean_expression_without_field_keeps_operator(self):
        self.assertEqual(
            "all:transformer OR diffusion",
            build_search_query("transformer OR diffusion"),
        )

    def test_andnot_expression_keeps_operator_and_field(self):
        self.assertEqual(
            "all:transformer ANDNOT cat:cs.AI",
            build_search_query("transformer ANDNOT cat:cs.AI"),
        )

    def test_query_with_leading_field_prefix_is_preserved(self):
        self.assertEqual(
            "ti:transformer AND cat:cs.AI",
            build_search_query("ti:transformer AND cat:cs.AI"),
        )

    def test_operators_inside_quotes_do_not_make_a_query_structured(self):
        self.assertEqual(
            'all:"\\\"AND\\\" machine learning"',
            build_search_query('"AND" machine learning'),
        )

    def test_plain_phrase_stays_quoted(self):
        self.assertEqual(
            'all:"machine learning"',
            build_search_query("machine learning"),
        )

    def test_title_phrase_stays_in_title_field(self):
        self.assertEqual(
            'ti:"machine learning"',
            build_search_query("machine learning", title_only=True),
        )

    def test_existing_quoted_phrase_is_preserved(self):
        self.assertEqual(
            'all:"machine learning"',
            build_search_query('"machine learning"'),
        )

    def test_fielded_query_with_category_and_multiple_authors(self):
        self.assertEqual(
            'ti:"transformer models" AND (au:"Jane Doe" OR au:"John Smith") AND cat:cs.AI',
            build_search_query(
                "transformer models",
                category="cs.AI",
                author="Jane Doe, John Smith",
                title_only=True,
            ),
        )

    def test_category_filter_applies_to_the_entire_boolean_expression(self):
        self.assertEqual(
            "(all:transformer OR diffusion) AND cat:cs.AI",
            build_search_query("transformer OR diffusion", category="cs.AI"),
        )


if __name__ == "__main__":
    unittest.main()
