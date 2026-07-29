#!/usr/bin/env python3
"""Validate a newly generated supplement_plan.json.

This validator is the Supplement Planner's generation gate. It checks the
plan schema, its binding to plan.json, and the initial work-order state:
every supplement item is pending and has no resolution note. It does not
validate supplement execution or updated evidence.

Usage:
    python3 validate_supplement_plan.py supplement_plan.json \
        --plan plan.json

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
from datetime import date
from pathlib import Path


DIM_ID_RE = re.compile(r"^d[1-9]\d*$")
SUPPLEMENT_TYPE_VALUES = {"coverage", "claim_fix", "both"}
SUPPLEMENT_STATUS_VALUES = {
    "pending",
    "resolved",
    "partial",
    "no_data",
    "out_of_scope",
}
DEFERRED_REASON_VALUES = {
    "writing_context_only",
    "low_value",
    "not_actionable",
    "out_of_scope",
    "already_covered",
    "unavailable",
}
TOP_LEVEL_KEYS = {
    "meta",
    "dimension_id",
    "dimension_name",
    "supplement_items",
    "deferred_items",
}
META_KEYS = {"task", "generated_from", "target_report", "date", "principle"}
SUPPLEMENT_ITEM_KEYS = {
    "id",
    "type",
    "gap",
    "question",
    "rationale",
    "suggested_sources",
    "candidate_leads",
    "source_refs",
    "review_refs",
    "impact_if_skipped",
    "status",
    "resolution_note",
}
DEFERRED_ITEM_KEYS = {
    "id",
    "reason",
    "item",
    "source_refs",
    "writing_context_use",
}


def err(rule: str, message: str, **fields: object) -> dict:
    return {"rule": rule, "severity": "error", "message": message, **fields}


def is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_keys(
    value: object,
    expected: set[str],
    *,
    location: str,
    rule: str,
) -> tuple[list[dict], dict | None]:
    if not isinstance(value, dict):
        return [err(rule, f"{location} must be an object")], None

    errors: list[dict] = []
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing:
        errors.append(err(rule, f"{location} is missing required fields", missing=missing))
    if unknown:
        errors.append(err(rule, f"{location} contains unknown fields", unknown=unknown))
    return errors, value


def validate_string_array(
    value: object,
    *,
    location: str,
    rule: str,
    min_items: int = 0,
) -> tuple[list[dict], list[str]]:
    if not isinstance(value, list):
        return [err(rule, f"{location} must be an array")], []

    errors: list[dict] = []
    if len(value) < min_items:
        errors.append(
            err(
                rule,
                f"{location} must contain at least {min_items} item(s)",
                length=len(value),
            )
        )

    strings: list[str] = []
    for index, item in enumerate(value):
        if not is_nonempty_string(item):
            errors.append(
                err(rule, f"{location}[{index}] must be a non-empty string", got=item)
            )
        else:
            strings.append(item)

    duplicates = sorted(item for item, count in Counter(strings).items() if count > 1)
    if duplicates:
        errors.append(
            err(rule, f"{location} must not contain duplicates", duplicates=duplicates)
        )
    return errors, strings


def validate(
    data: object,
    plan_data: object | None = None,
) -> list[dict]:
    errors: list[dict] = []
    root_errors, root = validate_keys(
        data,
        TOP_LEVEL_KEYS,
        location="root",
        rule="SP001",
    )
    errors.extend(root_errors)
    if root is None:
        return errors

    meta_errors, meta = validate_keys(
        root.get("meta"),
        META_KEYS,
        location="meta",
        rule="SP002",
    )
    errors.extend(meta_errors)
    if meta is not None:
        for field in ("task", "generated_from", "principle"):
            if not is_nonempty_string(meta.get(field)):
                errors.append(err("SP003", f"meta.{field} must be a non-empty string"))
        if not isinstance(meta.get("target_report"), str):
            errors.append(err("SP003", "meta.target_report must be a string"))
        raw_date = meta.get("date")
        if not is_nonempty_string(raw_date):
            errors.append(err("SP004", "meta.date must use YYYY-MM-DD"))
        else:
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                errors.append(err("SP004", "meta.date must be a real YYYY-MM-DD date",
                                  got=raw_date))

    dimension_id = root.get("dimension_id")
    valid_dimension_id = (
        isinstance(dimension_id, str) and DIM_ID_RE.fullmatch(dimension_id) is not None
    )
    if not valid_dimension_id:
        errors.append(
            err("SP005", "dimension_id must match ^d[1-9]\\d*$", got=dimension_id)
        )
        dimension_id = None

    dimension_name = root.get("dimension_name")
    if not is_nonempty_string(dimension_name):
        errors.append(err("SP006", "dimension_name must be a non-empty string"))

    if plan_data is not None:
        if not isinstance(plan_data, dict):
            errors.append(err("SP007", "plan root must be an object"))
        else:
            dimensions = plan_data.get("dimensions")
            if not isinstance(dimensions, list):
                errors.append(err("SP007", "plan.dimensions must be an array"))
            elif dimension_id is not None:
                planned_dimension = next(
                    (
                        item
                        for item in dimensions
                        if isinstance(item, dict) and item.get("id") == dimension_id
                    ),
                    None,
                )
                if planned_dimension is None:
                    errors.append(
                        err("SP007", f"dimension {dimension_id!r} is not present in plan")
                    )
                elif dimension_name != planned_dimension.get("name"):
                    errors.append(
                        err(
                            "SP008",
                            "dimension_name must exactly match the plan dimension name",
                            expected=planned_dimension.get("name"),
                            got=dimension_name,
                        )
                    )

    supplement_items = root.get("supplement_items")
    if not isinstance(supplement_items, list):
        errors.append(err("SP009", "supplement_items must be an array"))
        supplement_items = []
    elif len(supplement_items) > 8:
        errors.append(
            err("SP009", "supplement_items must contain at most 8 items",
                length=len(supplement_items))
        )

    seen_ids: list[str] = []
    for index, item in enumerate(supplement_items):
        location = f"supplement_items[{index}]"
        item_errors, item_obj = validate_keys(
            item,
            SUPPLEMENT_ITEM_KEYS,
            location=location,
            rule="SP010",
        )
        errors.extend(item_errors)
        if item_obj is None:
            continue

        item_id = item_obj.get("id")
        expected_id_re = (
            re.compile(rf"^{re.escape(dimension_id)}-s[1-9]\d*$")
            if dimension_id is not None
            else None
        )
        if not (
            isinstance(item_id, str)
            and expected_id_re is not None
            and expected_id_re.fullmatch(item_id)
        ):
            errors.append(
                err(
                    "SP011",
                    f"{location}.id must match <dimension_id>-sN",
                    got=item_id,
                )
            )
        else:
            seen_ids.append(item_id)

        item_type = item_obj.get("type")
        if item_type not in SUPPLEMENT_TYPE_VALUES:
            errors.append(
                err(
                    "SP012",
                    f"{location}.type must be one of {sorted(SUPPLEMENT_TYPE_VALUES)}",
                    got=item_type,
                )
            )

        for field in (
            "gap",
            "question",
            "rationale",
            "impact_if_skipped",
        ):
            if not is_nonempty_string(item_obj.get(field)):
                errors.append(
                    err("SP013", f"{location}.{field} must be a non-empty string")
                )

        for field, min_items in (
            ("suggested_sources", 1),
            ("candidate_leads", 0),
            ("source_refs", 1),
            ("review_refs", 0),
        ):
            array_errors, _ = validate_string_array(
                item_obj.get(field),
                location=f"{location}.{field}",
                rule="SP014",
                min_items=min_items,
            )
            errors.extend(array_errors)

        if item_type in {"claim_fix", "both"}:
            review_refs = item_obj.get("review_refs")
            if isinstance(review_refs, list) and not review_refs:
                errors.append(
                    err(
                        "SP015",
                        f"{location}.review_refs must be non-empty for type={item_type}",
                    )
                )

        status = item_obj.get("status")
        if status not in SUPPLEMENT_STATUS_VALUES:
            errors.append(
                err(
                    "SP016",
                    f"{location}.status must be one of "
                    f"{sorted(SUPPLEMENT_STATUS_VALUES)}",
                    got=status,
                )
            )
        elif status != "pending":
            errors.append(
                err(
                    "SP018",
                    f"{location}.status must be pending in a newly generated plan",
                    got=status,
                )
            )

        resolution_note = item_obj.get("resolution_note")
        if not isinstance(resolution_note, str):
            errors.append(err("SP017", f"{location}.resolution_note must be a string"))
        elif resolution_note:
            errors.append(
                err(
                    "SP018",
                    f"{location}.resolution_note must be empty in a newly generated plan",
                )
            )

    deferred_items = root.get("deferred_items")
    if not isinstance(deferred_items, list):
        errors.append(err("SP020", "deferred_items must be an array"))
        deferred_items = []

    for index, item in enumerate(deferred_items):
        location = f"deferred_items[{index}]"
        item_errors, item_obj = validate_keys(
            item,
            DEFERRED_ITEM_KEYS,
            location=location,
            rule="SP021",
        )
        errors.extend(item_errors)
        if item_obj is None:
            continue

        item_id = item_obj.get("id")
        expected_id_re = (
            re.compile(rf"^{re.escape(dimension_id)}-d[1-9]\d*$")
            if dimension_id is not None
            else None
        )
        if not (
            isinstance(item_id, str)
            and expected_id_re is not None
            and expected_id_re.fullmatch(item_id)
        ):
            errors.append(
                err(
                    "SP022",
                    f"{location}.id must match <dimension_id>-dN",
                    got=item_id,
                )
            )
        else:
            seen_ids.append(item_id)

        reason = item_obj.get("reason")
        if reason not in DEFERRED_REASON_VALUES:
            errors.append(
                err(
                    "SP023",
                    f"{location}.reason must be one of {sorted(DEFERRED_REASON_VALUES)}",
                    got=reason,
                )
            )
        if not is_nonempty_string(item_obj.get("item")):
            errors.append(err("SP024", f"{location}.item must be a non-empty string"))
        source_errors, _ = validate_string_array(
            item_obj.get("source_refs"),
            location=f"{location}.source_refs",
            rule="SP025",
            min_items=1,
        )
        errors.extend(source_errors)
        writing_context_use = item_obj.get("writing_context_use")
        if not isinstance(writing_context_use, str):
            errors.append(
                err("SP026", f"{location}.writing_context_use must be a string")
            )
        elif reason == "writing_context_only" and not writing_context_use.strip():
            errors.append(
                err(
                    "SP026",
                    f"{location}.writing_context_use must be non-empty "
                    "for reason=writing_context_only",
                )
            )

    duplicates = sorted(item_id for item_id, count in Counter(seen_ids).items() if count > 1)
    if duplicates:
        errors.append(err("SP027", "item ids must be unique", duplicates=duplicates))

    return errors


def build_stats(data: dict) -> dict:
    supplement_items = [
        item for item in data.get("supplement_items", []) if isinstance(item, dict)
    ]
    return {
        "dimension_id": data.get("dimension_id"),
        "supplement_items": len(supplement_items),
        "deferred_items": len(
            [item for item in data.get("deferred_items", []) if isinstance(item, dict)]
        ),
        "status_distribution": {
            status: sum(1 for item in supplement_items if item.get("status") == status)
            for status in sorted(SUPPLEMENT_STATUS_VALUES)
        },
    }


def load_json(path: Path, label: str) -> tuple[object | None, dict | None]:
    if not path.exists():
        return None, err("FILE", f"File not found: {path}", input=label)
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeError) as exc:
        return None, err("FILE", f"Could not read {path}: {exc}", input=label)
    except json.JSONDecodeError as exc:
        return None, err(
            "JSON",
            f"Invalid {label} JSON: {exc.msg} at line {exc.lineno} col {exc.colno}",
            input=label,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a supplement_plan.json file.")
    parser.add_argument("path", help="path to supplement_plan.json")
    parser.add_argument(
        "--plan",
        required=True,
        dest="plan_path",
        help="path to plan.json; validates dimension id and name binding",
    )
    args = parser.parse_args()

    data, load_error = load_json(Path(args.path), "supplement plan")
    if load_error:
        print(json.dumps({"ok": False, "errors": [load_error]},
                         ensure_ascii=False, indent=2))
        sys.exit(2)

    plan_data, load_error = load_json(Path(args.plan_path), "plan")
    if load_error:
        print(json.dumps({"ok": False, "errors": [load_error]},
                         ensure_ascii=False, indent=2))
        sys.exit(2)

    errors = validate(
        data,
        plan_data=plan_data,
    )
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(
        json.dumps(
            {"ok": True, "errors": [], "stats": build_stats(data)},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
