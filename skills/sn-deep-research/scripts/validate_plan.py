#!/usr/bin/env python3
"""Validate plan.json against schemas/plan.schema.md.

Stdlib-only. The validator checks the executable plan contract, including
scope ownership, dependency-input parity, graph validity, and derived waves.

Usage:
    python3 validate_plan.py path/to/plan.json --format path/to/format.json

Exit code:
    0 - pass
    1 - schema or contract errors
    2 - file not found or invalid JSON
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


SCHEMA_VERSION = "1.0"
MODE_VALUES = {"normal", "heavy"}
DEPTH_VALUES = {"skim", "moderate", "thorough"}
STRATEGY_DIMENSION_VALUES = {
    "by_topic",
    "by_entity",
    "by_timeline",
    "by_stakeholder",
    "by_causal_chain",
    "by_evidence_type",
    "by_region",
    "by_value_chain",
    "by_methodology",
    "by_process_stage",
    "by_requirement",
    "by_risk",
}
SOURCE_CATEGORY_VALUES = {
    "official",
    "news",
    "social_media",
    "github",
    "developer",
    "community",
    "trend",
    "academic",
    "forum",
    "analyst",
    "review",
    "data",
    "legal",
    "financial",
    "finance",
    "securities",
    "annual_report",
    "filing",
    "market_cn",
    "policy",
    "regulation",
    "multi_platform",
}
NEEDED_FOR_VALUES = {
    "entity_selection",
    "taxonomy_definition",
    "time_window",
    "hypothesis_definition",
    "source_targeting",
}
DIM_ID_RE = re.compile(r"^d[1-9]\d*$")


def err(rule: str, message: str, **fields: object) -> dict:
    return {"rule": rule, "severity": "error", "message": message, **fields}


def is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


GENERIC_SCOPE_RULES = {
    "参考上游结果",
    "参考前序研究",
    "综合上游结果",
    "综合前序研究",
    "进行综合分析",
}


def is_meaningful_scope_rule(value: object) -> bool:
    if not is_nonempty_string(value):
        return False
    normalized = "".join(str(value).split()).rstrip("。；;.")
    return len(normalized) >= 16 and normalized not in GENERIC_SCOPE_RULES


def validate_string_array(
    value: object,
    *,
    location: str,
    rule: str,
    min_items: int = 0,
) -> tuple[list[dict], list[str]]:
    errors: list[dict] = []
    if not isinstance(value, list):
        return [err(rule, f"{location} must be an array")], []

    if len(value) < min_items:
        errors.append(err(rule, f"{location} must contain at least {min_items} item(s)",
                          length=len(value)))

    strings: list[str] = []
    for index, item in enumerate(value):
        if not is_nonempty_string(item):
            errors.append(err(rule, f"{location}[{index}] must be a non-empty string",
                              got=item))
        else:
            strings.append(item)

    duplicates = sorted(item for item, count in Counter(strings).items() if count > 1)
    if duplicates:
        errors.append(err(rule, f"{location} must not contain duplicates",
                          duplicates=duplicates))
    return errors, strings


def validate(data: object, format_data: object | None = None) -> list[dict]:
    errors: list[dict] = []
    if not isinstance(data, dict):
        return [err("STRUCT", "Root must be a JSON object")]

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(err("P001", f"schema_version must be '{SCHEMA_VERSION}'",
                          got=data.get("schema_version")))

    mode = data.get("mode")
    if not isinstance(mode, str) or mode not in MODE_VALUES:
        errors.append(err("P002", f"mode must be one of {sorted(MODE_VALUES)}", got=mode))

    format_id = data.get("format_id")
    if not is_nonempty_string(format_id):
        errors.append(err("P003", "format_id must be a non-empty string"))

    if format_data is not None:
        if not isinstance(format_data, dict):
            errors.append(err("P005", "format root must be an object"))
        else:
            selected_format = format_data.get("selected_format")
            confirmed = format_data.get("confirmed_by_user")
            selected_id = selected_format.get("id") if isinstance(selected_format, dict) else None
            if confirmed is not True:
                errors.append(err("P005", "format.confirmed_by_user must be true"))
            if not is_nonempty_string(selected_id):
                errors.append(err("P005", "format.selected_format.id must be a non-empty string"))
            elif format_id != selected_id:
                errors.append(err(
                    "P005",
                    "format_id must equal format.selected_format.id",
                    got=format_id,
                    expected=selected_id,
                ))

    notes = data.get("notes")
    if notes is not None and not isinstance(notes, str):
        errors.append(err("P004", "notes must be a string when present", got=notes))

    strategy = data.get("strategy")
    if not isinstance(strategy, dict):
        errors.append(err("P010", "strategy must be an object"))
    else:
        strategy_errors, relevant_dimensions = validate_string_array(
            strategy.get("relevant_dimensions"),
            location="strategy.relevant_dimensions",
            rule="P011",
            min_items=1,
        )
        errors.extend(strategy_errors)
        for value in relevant_dimensions:
            if value not in STRATEGY_DIMENSION_VALUES:
                errors.append(err(
                    "P011",
                    f"strategy.relevant_dimensions values must be one of "
                    f"{sorted(STRATEGY_DIMENSION_VALUES)}",
                    got=value,
                ))

        primary_dimension = strategy.get("primary_dimension")
        if not is_nonempty_string(primary_dimension):
            errors.append(err("P012", "strategy.primary_dimension must be a non-empty string"))
        elif primary_dimension not in relevant_dimensions:
            errors.append(err("P012", "strategy.primary_dimension must occur in "
                                      "strategy.relevant_dimensions",
                              got=primary_dimension))

        if not is_nonempty_string(strategy.get("rationale")):
            errors.append(err("P013", "strategy.rationale must be a non-empty string"))

    dimensions = data.get("dimensions")
    if not (isinstance(dimensions, list) and dimensions):
        errors.append(err("P020", "dimensions must be a non-empty array"))
        return errors

    records: list[dict] = []
    all_ids: list[str] = []

    for index, dimension in enumerate(dimensions):
        location = f"dimensions[{index}]"
        if not isinstance(dimension, dict):
            errors.append(err("P021", f"{location} must be an object"))
            continue

        dimension_id = dimension.get("id")
        if not (isinstance(dimension_id, str) and DIM_ID_RE.fullmatch(dimension_id)):
            errors.append(err("P022", f"{location}.id must match ^d[1-9]\\d*$",
                              got=dimension_id))
        else:
            all_ids.append(dimension_id)

        for field, rule in (
            ("name", "P023"),
            ("description", "P024"),
            ("focus", "P026"),
            ("time_sensitivity", "P030"),
        ):
            if not is_nonempty_string(dimension.get(field)):
                errors.append(err(rule, f"{location}.{field} must be a non-empty string"))

        key_question_errors, _ = validate_string_array(
            dimension.get("key_questions"),
            location=f"{location}.key_questions",
            rule="P025",
            min_items=1,
        )
        errors.extend(key_question_errors)

        if not isinstance(dimension.get("context_from_briefing"), str):
            errors.append(err("P027", f"{location}.context_from_briefing must be a string"))

        sources = dimension.get("sources")
        if not (isinstance(sources, list) and sources):
            errors.append(err("P028", f"{location}.sources must be a non-empty array"))
        else:
            for source_index, source in enumerate(sources):
                source_location = f"{location}.sources[{source_index}]"
                if not isinstance(source, dict):
                    errors.append(err("P028", f"{source_location} must be an object"))
                    continue
                category = source.get("category")
                if not isinstance(category, str) or category not in SOURCE_CATEGORY_VALUES:
                    errors.append(err("P028", f"{source_location}.category must be one of "
                                              f"{sorted(SOURCE_CATEGORY_VALUES)}",
                                      got=category))
                if not is_nonempty_string(source.get("description")):
                    errors.append(err("P028", f"{source_location}.description must be a "
                                              "non-empty string"))

        lenses = dimension.get("lenses")
        if not isinstance(lenses, list):
            errors.append(err("P029", f"{location}.lenses must be an array"))
            lenses = []
        else:
            lens_pairs: list[tuple[str, str]] = []
            for lens_index, lens in enumerate(lenses):
                lens_location = f"{location}.lenses[{lens_index}]"
                if not isinstance(lens, dict):
                    errors.append(err("P029", f"{lens_location} must be an object"))
                    continue
                for field in ("axis", "value", "rationale"):
                    if not is_nonempty_string(lens.get(field)):
                        errors.append(err("P029", f"{lens_location}.{field} must be a "
                                                  "non-empty string"))
                if is_nonempty_string(lens.get("axis")) and is_nonempty_string(lens.get("value")):
                    lens_pairs.append((lens["axis"], lens["value"]))
            duplicate_lenses = sorted(
                pair for pair, count in Counter(lens_pairs).items() if count > 1
            )
            if duplicate_lenses:
                errors.append(err(
                    "P029",
                    f"{location}.lenses must not repeat an axis/value pair",
                    duplicates=duplicate_lenses,
                ))

        if not isinstance(dimension.get("depth"), str) or dimension.get("depth") not in DEPTH_VALUES:
            errors.append(err("P031", f"{location}.depth must be one of "
                                      f"{sorted(DEPTH_VALUES)}",
                              got=dimension.get("depth")))

        scope = dimension.get("scope_ownership")
        scope_values: dict[str, list[str]] = {}
        if not isinstance(scope, dict):
            errors.append(err("P032", f"{location}.scope_ownership must be an object"))
        else:
            for field, min_items in (("owns", 1), ("excludes", 0), ("shared_topics", 0)):
                scope_errors, values = validate_string_array(
                    scope.get(field),
                    location=f"{location}.scope_ownership.{field}",
                    rule="P033",
                    min_items=min_items,
                )
                errors.extend(scope_errors)
                scope_values[field] = values

            if not is_nonempty_string(scope.get("overlap_policy")):
                errors.append(err("P034", f"{location}.scope_ownership.overlap_policy "
                                          "must be a non-empty string"))

            ownership_conflicts = sorted(
                (set(scope_values.get("owns", [])) & set(scope_values.get("excludes", [])))
                | (set(scope_values.get("owns", [])) & set(scope_values.get("shared_topics", [])))
                | (set(scope_values.get("excludes", [])) & set(scope_values.get("shared_topics", [])))
            )
            if ownership_conflicts:
                errors.append(err("P035", f"{location}.scope_ownership fields must not contain "
                                          "the same exact scope",
                                  conflicts=ownership_conflicts))

        wave = dimension.get("wave")
        if not (isinstance(wave, int) and not isinstance(wave, bool) and wave >= 1):
            errors.append(err("P036", f"{location}.wave must be a positive integer", got=wave))

        dependency_errors, depends_on = validate_string_array(
            dimension.get("depends_on"),
            location=f"{location}.depends_on",
            rule="P037",
        )
        errors.extend(dependency_errors)
        for dependency_id in depends_on:
            if not DIM_ID_RE.fullmatch(dependency_id):
                errors.append(err("P037", f"{location}.depends_on values must match "
                                          "^d[1-9]\\d*$",
                                  got=dependency_id))

        dependency_inputs = dimension.get("dependency_inputs")
        dependency_input_ids: list[str] = []
        if not isinstance(dependency_inputs, list):
            errors.append(err("P038", f"{location}.dependency_inputs must be an array"))
            dependency_inputs = []
        else:
            for input_index, dependency_input in enumerate(dependency_inputs):
                input_location = f"{location}.dependency_inputs[{input_index}]"
                if not isinstance(dependency_input, dict):
                    errors.append(err("P038", f"{input_location} must be an object"))
                    continue

                upstream_id = dependency_input.get("dimension_id")
                if not (isinstance(upstream_id, str) and DIM_ID_RE.fullmatch(upstream_id)):
                    errors.append(err("P039", f"{input_location}.dimension_id must match "
                                              "^d[1-9]\\d*$",
                                      got=upstream_id))
                else:
                    dependency_input_ids.append(upstream_id)

                needed_for = dependency_input.get("needed_for")
                if not isinstance(needed_for, str) or needed_for not in NEEDED_FOR_VALUES:
                    errors.append(err("P040", f"{input_location}.needed_for must be one of "
                                              f"{sorted(NEEDED_FOR_VALUES)}",
                                      got=needed_for))

                if dependency_input.get("consume") != "key_findings":
                    errors.append(err("P041", f"{input_location}.consume must be "
                                              "'key_findings'",
                                      got=dependency_input.get("consume")))

                if not is_meaningful_scope_rule(dependency_input.get("scope_rule")):
                    errors.append(err("P042", f"{input_location}.scope_rule must be a "
                                              "specific rule (at least 16 non-whitespace "
                                              "characters), not a generic upstream reference"))

        duplicate_input_ids = sorted(
            item for item, count in Counter(dependency_input_ids).items() if count > 1
        )
        if duplicate_input_ids:
            errors.append(err("P043", f"{location}.dependency_inputs must contain one item "
                                      "per upstream dimension",
                              duplicates=duplicate_input_ids))

        dependency_set = set(depends_on)
        input_set = set(dependency_input_ids)
        if dependency_set != input_set:
            errors.append(err(
                "P044",
                f"{location}.depends_on and dependency_inputs[].dimension_id must match exactly",
                missing_inputs=sorted(dependency_set - input_set),
                unexpected_inputs=sorted(input_set - dependency_set),
            ))

        records.append({
            "index": index,
            "id": dimension_id,
            "wave": wave,
            "depends_on": depends_on,
            "dependency_inputs": dependency_inputs,
            "lenses": lenses,
            "owns": scope_values.get("owns", []),
        })

    duplicate_ids = sorted(item for item, count in Counter(all_ids).items() if count > 1)
    if duplicate_ids:
        errors.append(err("P045", "dimension ids must be unique", duplicates=duplicate_ids))

    owned_by: dict[str, list[str]] = {}
    for record in records:
        dimension_id = record["id"]
        if not isinstance(dimension_id, str):
            continue
        for owned_scope in record["owns"]:
            owned_by.setdefault(owned_scope, []).append(dimension_id)
    duplicated_ownership = {
        scope: owners for scope, owners in owned_by.items() if len(owners) > 1
    }
    if duplicated_ownership:
        errors.append(err(
            "P050",
            "the same exact scope must not be owned by multiple dimensions; use "
            "shared_topics plus overlap_policy for intentional overlap",
            duplicated_ownership=duplicated_ownership,
        ))

    id_set = set(all_ids)
    graph_has_invalid_edges = bool(duplicate_ids)
    graph: dict[str, list[str]] = {}

    for record in records:
        dimension_id = record["id"]
        if not (isinstance(dimension_id, str) and DIM_ID_RE.fullmatch(dimension_id)):
            graph_has_invalid_edges = True
            continue
        graph[dimension_id] = []
        for dependency_id in record["depends_on"]:
            if dependency_id == dimension_id:
                errors.append(err("P046", f"dimension {dimension_id} must not depend on itself"))
                graph_has_invalid_edges = True
            elif dependency_id not in id_set:
                errors.append(err("P047", f"dimension {dimension_id} depends on missing dimension "
                                          f"{dependency_id}"))
                graph_has_invalid_edges = True
            else:
                graph[dimension_id].append(dependency_id)

    cycle_paths: list[list[str]] = []
    state = {dimension_id: 0 for dimension_id in graph}
    stack: list[str] = []

    def visit(dimension_id: str) -> None:
        state[dimension_id] = 1
        stack.append(dimension_id)
        for dependency_id in graph.get(dimension_id, []):
            if dependency_id not in state:
                continue
            if state[dependency_id] == 0:
                visit(dependency_id)
            elif state[dependency_id] == 1:
                start = stack.index(dependency_id)
                cycle_paths.append(stack[start:] + [dependency_id])
        stack.pop()
        state[dimension_id] = 2

    for dimension_id in graph:
        if state[dimension_id] == 0:
            visit(dimension_id)

    if cycle_paths:
        errors.append(err("P048", "dependency graph must be acyclic", cycles=cycle_paths))

    if not graph_has_invalid_edges and not cycle_paths and len(graph) == len(records):
        expected_waves: dict[str, int] = {}

        def expected_wave(dimension_id: str) -> int:
            if dimension_id not in expected_waves:
                dependencies = graph[dimension_id]
                expected_waves[dimension_id] = (
                    1 if not dependencies
                    else 1 + max(expected_wave(upstream_id) for upstream_id in dependencies)
                )
            return expected_waves[dimension_id]

        for record in records:
            dimension_id = record["id"]
            expected = expected_wave(dimension_id)
            if record["wave"] != expected:
                errors.append(err("P049", f"dimension {dimension_id}.wave must be derived from "
                                          "its dependency topology",
                                  expected=expected, got=record["wave"]))

    if mode == "normal":
        if not 2 <= len(dimensions) <= 5:
            errors.append(err("P060", "normal mode must contain 2-5 dimensions",
                              dimensions=len(dimensions)))
        for record in records:
            dimension_id = record["id"] if isinstance(record["id"], str) else (
                f"dimensions[{record['index']}]"
            )
            if record["wave"] != 1:
                errors.append(err("P061", f"normal dimension {dimension_id} must have wave 1",
                                  got=record["wave"]))
            if record["depends_on"]:
                errors.append(err("P062", f"normal dimension {dimension_id} must have "
                                          "depends_on: []"))
            if record["dependency_inputs"]:
                errors.append(err("P063", f"normal dimension {dimension_id} must have "
                                          "dependency_inputs: []"))
            if record["lenses"]:
                errors.append(err("P064", f"normal dimension {dimension_id} must have lenses: []"))

    return errors


def build_stats(data: dict) -> dict:
    dimensions = [item for item in data.get("dimensions", []) if isinstance(item, dict)]
    wave_distribution = Counter(
        item.get("wave") for item in dimensions
        if isinstance(item.get("wave"), int) and not isinstance(item.get("wave"), bool)
    )
    return {
        "mode": data.get("mode"),
        "dimensions": len(dimensions),
        "dependencies": sum(
            len(item.get("depends_on", []))
            for item in dimensions
            if isinstance(item.get("depends_on"), list)
        ),
        "wave_distribution": {
            str(wave): wave_distribution[wave] for wave in sorted(wave_distribution)
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a plan.json file.")
    parser.add_argument("path", help="path to plan.json")
    parser.add_argument(
        "--format",
        dest="format_path",
        help="path to confirmed format.json; validates format_id binding",
    )
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(json.dumps({"ok": False, "errors": [
            err("FILE", f"File not found: {path}")
        ]}, ensure_ascii=False, indent=2))
        sys.exit(2)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        print(json.dumps({"ok": False, "errors": [
            err("FILE", f"Could not read {path}: {exc}")
        ]}, ensure_ascii=False, indent=2))
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "errors": [
            err("JSON", f"Invalid JSON: {exc.msg} at line {exc.lineno} col {exc.colno}")
        ]}, ensure_ascii=False, indent=2))
        sys.exit(2)

    format_data = None
    if args.format_path:
        format_path = Path(args.format_path)
        if not format_path.exists():
            print(json.dumps({"ok": False, "errors": [
                err("FILE", f"File not found: {format_path}")
            ]}, ensure_ascii=False, indent=2))
            sys.exit(2)
        try:
            format_data = json.loads(format_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            print(json.dumps({"ok": False, "errors": [
                err("FILE", f"Could not read {format_path}: {exc}")
            ]}, ensure_ascii=False, indent=2))
            sys.exit(2)
        except json.JSONDecodeError as exc:
            print(json.dumps({"ok": False, "errors": [
                err("JSON", f"Invalid JSON: {exc.msg} at line {exc.lineno} col {exc.colno}")
            ]}, ensure_ascii=False, indent=2))
            sys.exit(2)

    errors = validate(data, format_data)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(json.dumps({"ok": True, "errors": [], "stats": build_stats(data)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
