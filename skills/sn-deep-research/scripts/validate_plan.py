#!/usr/bin/env python3
"""Validate plan.json against schemas/plan.schema.md.

Stdlib-only. The validator checks the executable plan contract, including
scope ownership and independently executable research dimensions.

Usage:
    python3 validate_plan.py path/to/plan.json

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
DIM_ID_RE = re.compile(r"^d[1-9]\d*$")


def err(rule: str, message: str, **fields: object) -> dict:
    return {"rule": rule, "severity": "error", "message": message, **fields}


def is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


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


def validate(data: object) -> list[dict]:
    errors: list[dict] = []
    if not isinstance(data, dict):
        return [err("STRUCT", "Root must be a JSON object")]

    mode = data.get("mode")
    if not isinstance(mode, str) or mode not in MODE_VALUES:
        errors.append(err("P002", f"mode must be one of {sorted(MODE_VALUES)}", got=mode))

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

        records.append({
            "index": index,
            "id": dimension_id,
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

    if mode == "normal":
        for record in records:
            dimension_id = record["id"] if isinstance(record["id"], str) else (
                f"dimensions[{record['index']}]"
            )
            if record["lenses"]:
                errors.append(err("P064", f"normal dimension {dimension_id} must have lenses: []"))

    return errors


def build_stats(data: dict) -> dict:
    dimensions = [item for item in data.get("dimensions", []) if isinstance(item, dict)]
    return {
        "mode": data.get("mode"),
        "dimensions": len(dimensions),
        "lenses": sum(
            len(item.get("lenses", []))
            for item in dimensions
            if isinstance(item.get("lenses"), list)
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a plan.json file.")
    parser.add_argument("path", help="path to plan.json")
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

    errors = validate(data)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(json.dumps({"ok": True, "errors": [], "stats": build_stats(data)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
