#!/usr/bin/env python3
"""Deterministic tests for the executable research-plan contract."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_plan import validate


def dimension(dimension_id: str, owned_scope: str) -> dict:
    return {
        "id": dimension_id,
        "name": f"维度 {dimension_id}",
        "description": f"独立收集 {owned_scope} 的证据",
        "key_questions": [f"{owned_scope} 有哪些可验证事实？"],
        "focus": "事实、变化与证据边界",
        "context_from_briefing": "",
        "sources": [{"category": "official", "description": "权威原始资料"}],
        "lenses": [],
        "depth": "moderate",
        "time_sensitivity": "变化较慢，以最新有效资料为准，回看近三年",
        "scope_ownership": {
            "owns": [owned_scope],
            "excludes": [],
            "shared_topics": [],
            "overlap_policy": "无共享主题，各维度按 owns 独立取证",
        },
        "wave": 1,
        "depends_on": [],
        "dependency_inputs": [],
    }


def plan(mode: str, dimensions: list[dict]) -> dict:
    return {
        "schema_version": "1.0",
        "mode": mode,
        "format_id": "research_report",
        "strategy": {
            "relevant_dimensions": ["by_topic"],
            "primary_dimension": "by_topic",
            "rationale": "按独立主题划分取证边界",
        },
        "dimensions": dimensions,
        "notes": "",
    }


class ValidatePlanTests(unittest.TestCase):
    def test_cli_checks_confirmed_format_binding(self):
        data = plan("normal", [dimension("d1", "主题一"), dimension("d2", "主题二")])
        confirmed_format = {
            "confirmed_by_user": True,
            "selected_format": {"id": "research_report"},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan_path = root / "plan.json"
            format_path = root / "format.json"
            plan_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            format_path.write_text(json.dumps(confirmed_format), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("validate_plan.py")),
                    str(plan_path),
                    "--format",
                    str(format_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_plan_format_binding_is_enforced(self):
        data = plan("normal", [dimension("d1", "主题一"), dimension("d2", "主题二")])
        confirmed_format = {
            "confirmed_by_user": True,
            "selected_format": {"id": "decision_memo"},
        }
        self.assertIn("P005", {item["rule"] for item in validate(data, confirmed_format)})
        data["format_id"] = "decision_memo"
        self.assertEqual(validate(data, confirmed_format), [])

    def test_normal_accepts_two_independent_dimensions(self):
        data = plan("normal", [dimension("d1", "主题一"), dimension("d2", "主题二")])
        self.assertEqual(validate(data), [])

    def test_heavy_accepts_many_independent_dimensions_in_wave_one(self):
        data = plan("heavy", [
            dimension(f"d{index}", f"主题{index}") for index in range(1, 7)
        ])
        self.assertEqual(validate(data), [])

    def test_heavy_accepts_true_dependency_and_derived_wave(self):
        upstream = dimension("d1", "候选对象发现")
        downstream = dimension("d2", "入选对象采用证据")
        downstream["wave"] = 2
        downstream["depends_on"] = ["d1"]
        downstream["dependency_inputs"] = [{
            "dimension_id": "d1",
            "needed_for": "entity_selection",
            "consume": "key_findings",
            "scope_rule": "读取上游确认的对象名单，只检索入选对象的采用证据，不重复对象发现",
        }]
        self.assertEqual(validate(plan("heavy", [upstream, downstream])), [])

    def test_wrong_wave_is_rejected(self):
        data = plan("heavy", [dimension("d1", "主题一"), dimension("d2", "主题二")])
        data["dimensions"][1]["wave"] = 2
        self.assertIn("P049", {item["rule"] for item in validate(data)})

    def test_duplicate_lens_pair_is_rejected(self):
        item = dimension("d1", "主题一")
        item["lenses"] = [
            {"axis": "stakeholder", "value": "buyer", "rationale": "检查采购方视角"},
            {"axis": "stakeholder", "value": "buyer", "rationale": "重复视角"},
        ]
        data = plan("heavy", [item])
        self.assertIn("P029", {error["rule"] for error in validate(data)})

    def test_generic_dependency_scope_rule_is_rejected(self):
        data = plan("heavy", [dimension("d1", "主题一"), dimension("d2", "主题二")])
        target = data["dimensions"][1]
        target["wave"] = 2
        target["depends_on"] = ["d1"]
        target["dependency_inputs"] = [{
            "dimension_id": "d1",
            "needed_for": "entity_selection",
            "consume": "key_findings",
            "scope_rule": "参考上游结果",
        }]
        self.assertIn("P042", {item["rule"] for item in validate(data)})

    def test_duplicate_owned_scope_is_rejected(self):
        data = plan("heavy", [dimension("d1", "同一主题"), dimension("d2", "同一主题")])
        self.assertIn("P050", {item["rule"] for item in validate(data)})

    def test_malformed_enum_types_return_errors_instead_of_crashing(self):
        base = plan("heavy", [dimension("d1", "主题一")])
        mutations = [
            ("mode", [], "P002"),
            ("source", {}, "P028"),
            ("depth", {}, "P031"),
            ("needed_for", {}, "P040"),
        ]
        for kind, value, expected_rule in mutations:
            with self.subTest(kind=kind):
                data = copy.deepcopy(base)
                if kind == "mode":
                    data["mode"] = value
                elif kind == "source":
                    data["dimensions"][0]["sources"][0]["category"] = value
                elif kind == "depth":
                    data["dimensions"][0]["depth"] = value
                else:
                    second = dimension("d2", "主题二")
                    second["wave"] = 2
                    second["depends_on"] = ["d1"]
                    second["dependency_inputs"] = [{
                        "dimension_id": "d1",
                        "needed_for": value,
                        "consume": "key_findings",
                        "scope_rule": "读取上游确认的对象名单，只检索入选对象的采用证据，不重复对象发现",
                    }]
                    data["dimensions"].append(second)
                self.assertIn(expected_rule, {item["rule"] for item in validate(data)})


if __name__ == "__main__":
    unittest.main()
