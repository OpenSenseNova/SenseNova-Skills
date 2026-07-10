#!/usr/bin/env python3
"""Evidence schema validator.

Validates a {dim}.evidence.json file against the rules documented in
schemas/evidence.schema.md. Stdlib-only, no external dependencies.

Usage:
    python3 validate_evidence.py path/to/d1.evidence.json \
        --source-cache path/to/report/source_cache \
        --plan path/to/report/plan.json \
        --expected-mode initial \
        --require-version 1.2 \
        --upstream-evidence path/to/report/sub_reports/d2.evidence.json

Output (stdout):
    {"ok": true, "stats": {...}}
    {"ok": false, "errors": [{rule, message, ...}, ...]}

Exit code:
    0 — pass
    1 — fail (any V### error)
    2 — file not found / invalid JSON
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from source_snapshot import (
    SnapshotError,
    contains_direct_quote,
    normalize_url,
    parse_snapshot_ref,
    verify_snapshot,
)

SCHEMA_VERSION = "1.2"
SUPPORTED_SCHEMA_VERSIONS = {"1.1", SCHEMA_VERSION}

KIND_VALUES = {"factual", "interpretive", "projective"}
POLARITY_VALUES = {"support", "refute", "neutral"}
QUOTE_TYPE_VALUES = {"direct", "paraphrase", "numeric"}
QUALITY_VALUES = {"primary", "secondary", "tertiary"}
MODE_VALUES = {"initial", "quick", "supplement"}
WRITING_CONTEXT_KIND_VALUES = {
    "source_profile",
    "methodology",
    "scope_boundary",
    "availability_gap",
    "unresolved_gap",
}
NEEDED_FOR_VALUES = {
    "entity_selection",
    "taxonomy_definition",
    "time_window",
    "hypothesis_definition",
    "source_targeting",
}

DIM_ID_RE = re.compile(r"^d\d+$")
CLAIM_ID_RE = re.compile(r"^d\d+\.c\d+$")
SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
TOPIC_TAG_RE = re.compile(r"^[a-z][a-z0-9_]{0,29}$")
KQ_ID_RE = re.compile(r"^kq\d+$")
DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
WRITING_CONTEXT_ID_RE = re.compile(r"^d\d+\.w\d+$")


def err(rule, message, **fields):
    return {"rule": rule, "severity": "error", "message": message, **fields}


def validate(
    data,
    source_cache: Path | None = None,
    plan_data: object | None = None,
    expected_mode: str | None = None,
    required_version: str | None = None,
    upstream_evidence_data: list[object] | None = None,
) -> list:
    errors = []

    # ── Top-level structure ─────────────────────────────────────────────
    if not isinstance(data, dict):
        return [err("STRUCT", "Root must be a JSON object")]

    sv = data.get("schema_version")
    if sv not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(err(
            "V001",
            f"schema_version must be one of {sorted(SUPPORTED_SCHEMA_VERSIONS)}",
            got=sv,
        ))
    if required_version is not None and sv != required_version:
        errors.append(err(
            "V001",
            f"controller requires schema_version {required_version}",
            got=sv,
        ))
    if sv == SCHEMA_VERSION and source_cache is None:
        errors.append(err(
            "V037",
            f"schema_version {SCHEMA_VERSION} requires source_cache verification",
        ))

    dim_id = data.get("dimension_id")
    if not (isinstance(dim_id, str) and DIM_ID_RE.match(dim_id)):
        errors.append(err("V002", "dimension_id must match ^d\\d+$", got=dim_id))
        dim_id = None  # disable downstream id-prefix check

    # mode is optional; quick mode relaxes V040/V041 (tertiary acceptable)
    mode = data.get("mode")
    if mode is not None and mode not in MODE_VALUES:
        errors.append(err("V018", f"mode must be one of {sorted(MODE_VALUES)} if present", got=mode))
    is_quick = (mode == "quick")
    if expected_mode is not None and mode != expected_mode:
        errors.append(err(
            "V009",
            "evidence mode must match the dispatched research mode",
            expected=expected_mode,
            got=mode,
        ))

    upstream_usage = data.get("upstream_usage")
    if sv == SCHEMA_VERSION and not isinstance(upstream_usage, list):
        errors.append(err("V007", "upstream_usage must be an array for schema_version 1.2"))
    elif upstream_usage is not None and not isinstance(upstream_usage, list):
        errors.append(err("V007", "upstream_usage must be an array when present"))
    elif isinstance(upstream_usage, list):
        seen_upstream_ids: set[str] = set()
        for i, usage in enumerate(upstream_usage):
            loc = f"upstream_usage[{i}]"
            if not isinstance(usage, dict):
                errors.append(err("V007", f"{loc} must be an object"))
                continue

            upstream_id = usage.get("dimension_id")
            if not (isinstance(upstream_id, str) and DIM_ID_RE.fullmatch(upstream_id)):
                errors.append(err("V007", f"{loc}.dimension_id must match ^d\\d+$", got=upstream_id))
            elif upstream_id == dim_id:
                errors.append(err("V007", f"{loc}.dimension_id cannot reference the current dimension"))
            elif upstream_id in seen_upstream_ids:
                errors.append(err("V007", f"duplicate upstream usage for {upstream_id!r}"))
            else:
                seen_upstream_ids.add(upstream_id)

            needed_for = usage.get("needed_for")
            if not (isinstance(needed_for, str) and needed_for in NEEDED_FOR_VALUES):
                errors.append(err(
                    "V007",
                    f"{loc}.needed_for must be one of {sorted(NEEDED_FOR_VALUES)}",
                    got=needed_for,
                ))

            consumed_ids = usage.get("consumed_claim_ids")
            if not (isinstance(consumed_ids, list) and consumed_ids):
                errors.append(err("V007", f"{loc}.consumed_claim_ids must be a non-empty array"))
            else:
                for j, claim_id in enumerate(consumed_ids):
                    expected_prefix = f"{upstream_id}." if isinstance(upstream_id, str) else None
                    if not (isinstance(claim_id, str) and CLAIM_ID_RE.fullmatch(claim_id)):
                        errors.append(err(
                            "V007",
                            f"{loc}.consumed_claim_ids[{j}] must match ^d\\d+\\.c\\d+$",
                            got=claim_id,
                        ))
                    elif expected_prefix and not claim_id.startswith(expected_prefix):
                        errors.append(err(
                            "V007",
                            f"{loc}.consumed_claim_ids[{j}] must belong to {upstream_id}",
                            got=claim_id,
                        ))

            for field in ("scope_changes", "skipped_searches"):
                values = usage.get(field)
                if not (isinstance(values, list) and values):
                    errors.append(err("V007", f"{loc}.{field} must be a non-empty array"))
                    continue
                for j, value in enumerate(values):
                    if not (isinstance(value, str) and value.strip()):
                        errors.append(err("V007", f"{loc}.{field}[{j}] must be a non-empty string"))

    if mode == "quick" and isinstance(upstream_usage, list) and upstream_usage:
        errors.append(err("V008", "quick evidence must not consume upstream dimensions"))

    if plan_data is not None:
        if mode == "quick":
            errors.append(err("V009", "planned normal/heavy evidence cannot use mode=quick"))
        if not isinstance(plan_data, dict):
            errors.append(err("V008", "plan root must be an object"))
        else:
            dimensions = plan_data.get("dimensions")
            if not isinstance(dimensions, list):
                errors.append(err("V008", "plan.dimensions must be an array"))
            else:
                planned_dimension = next(
                    (
                        item for item in dimensions
                        if isinstance(item, dict) and item.get("id") == dim_id
                    ),
                    None,
                )
                if planned_dimension is None:
                    errors.append(err("V008", f"dimension {dim_id!r} is not present in plan"))
                else:
                    inputs = planned_dimension.get("dependency_inputs")
                    if not isinstance(inputs, list):
                        errors.append(err("V008", "plan dependency_inputs must be an array"))
                    elif isinstance(upstream_usage, list):
                        expected = {
                            item.get("dimension_id"): item.get("needed_for")
                            for item in inputs
                            if isinstance(item, dict) and isinstance(item.get("dimension_id"), str)
                        }
                        actual = {
                            item.get("dimension_id"): item.get("needed_for")
                            for item in upstream_usage
                            if isinstance(item, dict) and isinstance(item.get("dimension_id"), str)
                        }
                        if actual != expected:
                            errors.append(err(
                                "V008",
                                "upstream_usage must match plan dependency_inputs exactly",
                                expected=expected,
                                got=actual,
                            ))
                        if expected and upstream_evidence_data is None:
                            errors.append(err(
                                "V008",
                                "planned dependencies require --upstream-evidence verification",
                                expected_dimensions=sorted(expected),
                            ))

    if upstream_evidence_data is not None:
        upstream_claim_ids: dict[str, set[str]] = {}
        for index, upstream in enumerate(upstream_evidence_data):
            if not isinstance(upstream, dict):
                errors.append(err("V008", f"upstream evidence[{index}] root must be an object"))
                continue
            upstream_id = upstream.get("dimension_id")
            if not (isinstance(upstream_id, str) and DIM_ID_RE.fullmatch(upstream_id)):
                errors.append(err("V008", f"upstream evidence[{index}].dimension_id is invalid", got=upstream_id))
                continue
            if upstream_id in upstream_claim_ids:
                errors.append(err("V008", f"duplicate upstream evidence for {upstream_id}"))
                continue
            declared_claim_ids = {
                claim.get("id")
                for claim in upstream.get("claims", [])
                if isinstance(claim, dict) and isinstance(claim.get("id"), str)
            }
            finding_claim_ids = {
                claim_id
                for finding in upstream.get("key_findings", [])
                if isinstance(finding, dict)
                for claim_id in finding.get("claim_ids", [])
                if isinstance(claim_id, str)
            }
            upstream_claim_ids[upstream_id] = declared_claim_ids & finding_claim_ids

        for index, usage in enumerate(upstream_usage or []):
            if not isinstance(usage, dict):
                continue
            upstream_id = usage.get("dimension_id")
            allowed_claim_ids = upstream_claim_ids.get(upstream_id)
            if allowed_claim_ids is None:
                errors.append(err(
                    "V008",
                    f"upstream_usage[{index}] has no matching upstream evidence file",
                    dimension_id=upstream_id,
                ))
                continue
            for claim_id in usage.get("consumed_claim_ids", []) or []:
                if isinstance(claim_id, str) and claim_id not in allowed_claim_ids:
                    errors.append(err(
                        "V008",
                        f"upstream_usage[{index}] consumed claim is not referenced by upstream key_findings",
                        claim_id=claim_id,
                        dimension_id=upstream_id,
                    ))

    headline = data.get("headline")
    if not (isinstance(headline, str) and 5 <= len(headline) <= 200):
        errors.append(err("V003", "headline must be a string 5-200 chars",
                          length=(len(headline) if isinstance(headline, str) else None)))

    claims = data.get("claims")
    if not (isinstance(claims, list) and len(claims) >= 1):
        errors.append(err("V004", "claims must be a non-empty array"))
        return errors  # cannot continue meaningfully

    sources = data.get("sources")
    if not (isinstance(sources, list) and len(sources) >= 1):
        errors.append(err("V005", "sources must be a non-empty array"))
        return errors

    # ── Sources ─────────────────────────────────────────────────────────
    source_ids: set[str] = set()
    source_quality_by_id: dict[str, str] = {}
    source_url_by_id: dict[str, str] = {}

    for i, src in enumerate(sources):
        loc = f"sources[{i}]"
        if not isinstance(src, dict):
            errors.append(err("V010", f"{loc} must be an object"))
            continue

        sid = src.get("id")
        if not (isinstance(sid, str) and SOURCE_ID_RE.match(sid)):
            errors.append(err("V011", f"{loc}.id must match ^[a-z][a-z0-9_]*$", got=sid))
        elif sid in source_ids:
            errors.append(err("V012", f"duplicate source id: {sid!r}"))
        else:
            source_ids.add(sid)

        url = src.get("url")
        if not (isinstance(url, str) and url):
            errors.append(err("V013", f"{loc}.url must be a non-empty string"))
        else:
            try:
                normalize_url(url)
                if isinstance(sid, str):
                    source_url_by_id[sid] = url
            except SnapshotError as e:
                errors.append(err("V014", f"{loc}.url is not a valid URL: {e}"))

        title = src.get("title")
        if not (isinstance(title, str) and title.strip()):
            errors.append(err("V015", f"{loc}.title must be a non-empty string"))

        quality = src.get("quality")
        if quality not in QUALITY_VALUES:
            errors.append(err("V016", f"{loc}.quality must be one of {sorted(QUALITY_VALUES)}", got=quality))
        elif isinstance(sid, str):
            source_quality_by_id[sid] = quality

        published_at = src.get("published_at")
        if published_at is not None:
            if not (isinstance(published_at, str) and DATE_RE.match(published_at)):
                errors.append(err("V017", f"{loc}.published_at must be YYYY[-MM[-DD]]", got=published_at))

    # ── Writing context (non-claim boundaries for downstream writers) ────
    writing_context = data.get("writing_context", [])
    seen_context_ids: set[str] = set()
    if not isinstance(writing_context, list):
        errors.append(err("V060", "writing_context must be an array when present"))
    else:
        for i, context in enumerate(writing_context):
            loc = f"writing_context[{i}]"
            if not isinstance(context, dict):
                errors.append(err("V060", f"{loc} must be an object"))
                continue

            context_id = context.get("id")
            if not (isinstance(context_id, str) and WRITING_CONTEXT_ID_RE.fullmatch(context_id)):
                errors.append(err("V061", f"{loc}.id must match ^d\\d+\\.w\\d+$", got=context_id))
            elif dim_id is not None and not context_id.startswith(f"{dim_id}."):
                errors.append(err("V061", f"{loc}.id must belong to {dim_id}", got=context_id))
            elif context_id in seen_context_ids:
                errors.append(err("V061", f"duplicate writing_context id: {context_id}"))
            else:
                seen_context_ids.add(context_id)

            kind = context.get("kind")
            if kind not in WRITING_CONTEXT_KIND_VALUES:
                errors.append(err(
                    "V062",
                    f"{loc}.kind must be one of {sorted(WRITING_CONTEXT_KIND_VALUES)}",
                    got=kind,
                ))
            context_text = context.get("text")
            if not (isinstance(context_text, str) and 10 <= len(context_text) <= 500):
                errors.append(err("V063", f"{loc}.text must be 10-500 chars"))
            use = context.get("use")
            if not (isinstance(use, str) and 10 <= len(use) <= 300):
                errors.append(err("V064", f"{loc}.use must be 10-300 chars"))

            context_sources = context.get("source_ids", [])
            if not isinstance(context_sources, list):
                errors.append(err("V065", f"{loc}.source_ids must be an array"))
            else:
                valid_context_sources = [
                    value for value in context_sources if isinstance(value, str)
                ]
                if len(valid_context_sources) != len(context_sources) or len(set(valid_context_sources)) != len(valid_context_sources):
                    errors.append(err("V065", f"{loc}.source_ids must be unique strings"))
                for j, source_id in enumerate(context_sources):
                    if not isinstance(source_id, str) or source_id not in source_ids:
                        errors.append(err("V065", f"{loc}.source_ids[{j}] must reference sources[]", got=source_id))

            applies_to = context.get("applies_to", [])
            if not isinstance(applies_to, list):
                errors.append(err("V066", f"{loc}.applies_to must be an array"))
            else:
                valid_kqs = [value for value in applies_to if isinstance(value, str)]
                if len(valid_kqs) != len(applies_to) or len(set(valid_kqs)) != len(valid_kqs):
                    errors.append(err("V066", f"{loc}.applies_to must be unique kq ids"))
                for j, key_question_id in enumerate(applies_to):
                    if not (isinstance(key_question_id, str) and KQ_ID_RE.fullmatch(key_question_id)):
                        errors.append(err("V066", f"{loc}.applies_to[{j}] must match ^kq\\d+$", got=key_question_id))

    # ── Claims ──────────────────────────────────────────────────────────
    seen_claim_ids: set[str] = set()
    answered_kqs: set[str] = set()
    snapshot_verifications: dict[tuple[str, str], dict | Exception] = {}

    for i, claim in enumerate(claims):
        loc = f"claims[{i}]"
        if not isinstance(claim, dict):
            errors.append(err("V020", f"{loc} must be an object"))
            continue

        cid = claim.get("id")
        if not (isinstance(cid, str) and CLAIM_ID_RE.match(cid)):
            errors.append(err("V021", f"{loc}.id must match ^d\\d+\\.c\\d+$", got=cid))
        elif cid in seen_claim_ids:
            errors.append(err("V022", f"duplicate claim id: {cid!r}"))
        else:
            seen_claim_ids.add(cid)
            if dim_id and not cid.startswith(f"{dim_id}."):
                errors.append(err("V023",
                                  f"{loc}.id ({cid!r}) must be prefixed by dimension_id ({dim_id!r})"))

        text = claim.get("text")
        if not (isinstance(text, str) and 5 <= len(text) <= 500):
            errors.append(err("V024", f"{loc}.text must be a string 5-500 chars",
                              length=(len(text) if isinstance(text, str) else None)))

        kind = claim.get("kind")
        if kind not in KIND_VALUES:
            errors.append(err("V025", f"{loc}.kind must be one of {sorted(KIND_VALUES)}", got=kind))

        polarity = claim.get("polarity")
        if polarity not in POLARITY_VALUES:
            errors.append(err("V026", f"{loc}.polarity must be one of {sorted(POLARITY_VALUES)}",
                              got=polarity))

        topic_tag = claim.get("topic_tag")
        if not (isinstance(topic_tag, str) and TOPIC_TAG_RE.match(topic_tag)):
            errors.append(err("V027", f"{loc}.topic_tag must match ^[a-z][a-z0-9_]{{0,29}}$",
                              got=topic_tag))

        akq = claim.get("answers_key_question")
        if akq is not None:
            if not (isinstance(akq, str) and KQ_ID_RE.match(akq)):
                errors.append(err("V028",
                                  f"{loc}.answers_key_question must be null or match ^kq\\d+$",
                                  got=akq))
            else:
                answered_kqs.add(akq)

        ev = claim.get("evidence")
        if not (isinstance(ev, list) and len(ev) >= 1):
            errors.append(err("V029", f"{loc}.evidence must be a non-empty array"))
            continue

        # ── Evidence ────────────────────────────────────────────────
        primary_or_secondary_count = 0
        unique_source_ids: set[str] = set()

        for j, e in enumerate(ev):
            eloc = f"{loc}.evidence[{j}]"
            if not isinstance(e, dict):
                errors.append(err("V030", f"{eloc} must be an object"))
                continue

            esid = e.get("source_id")
            if not isinstance(esid, str):
                errors.append(err("V031", f"{eloc}.source_id must be a string", got=esid))
            elif esid not in source_ids:
                errors.append(err("V031", f"{eloc}.source_id ({esid!r}) not found in sources[]"))
            else:
                unique_source_ids.add(esid)
                if source_quality_by_id.get(esid) in {"primary", "secondary"}:
                    primary_or_secondary_count += 1

            snippet = e.get("snippet")
            if not (isinstance(snippet, str) and snippet.strip()):
                errors.append(err("V032", f"{eloc}.snippet must be a non-empty string"))

            qt = e.get("quote_type")
            if qt not in QUOTE_TYPE_VALUES:
                errors.append(err("V033",
                                  f"{eloc}.quote_type must be one of {sorted(QUOTE_TYPE_VALUES)}",
                                  got=qt))

            snapshot_ref = e.get("snapshot_ref")
            snapshot_ref_required = sv == SCHEMA_VERSION
            if snapshot_ref is None:
                if snapshot_ref_required:
                    errors.append(err(
                        "V034",
                        f"{eloc}.snapshot_ref is required by schema_version {SCHEMA_VERSION}",
                    ))
                continue
            try:
                parse_snapshot_ref(snapshot_ref)
            except SnapshotError as exc:
                errors.append(err("V034", f"{eloc}.snapshot_ref is invalid: {exc}",
                                  got=snapshot_ref))
                continue

            source_url = source_url_by_id.get(esid) if isinstance(esid, str) else None
            if source_cache is not None and source_url is not None:
                cache_key = (snapshot_ref, source_url)
                if cache_key not in snapshot_verifications:
                    try:
                        snapshot_verifications[cache_key] = verify_snapshot(
                            source_cache, snapshot_ref, expected_url=source_url
                        )
                    except (OSError, SnapshotError) as exc:
                        snapshot_verifications[cache_key] = exc
                verification = snapshot_verifications[cache_key]
                if isinstance(verification, Exception):
                    errors.append(err(
                        "V035",
                        f"{eloc}.snapshot_ref failed cache verification: {verification}",
                        snapshot_ref=snapshot_ref,
                    ))
                elif qt in {"direct", "numeric"} and isinstance(snippet, str) and snippet.strip():
                    if not contains_direct_quote(verification["text"], snippet):
                        errors.append(err(
                            "V036",
                            f"{eloc}.snippet is not present in the pinned snapshot",
                            snapshot_ref=snapshot_ref,
                        ))

        # ── Kind-specific evidence rules ────────────────────────────
        # quick 模式放宽：tertiary（如百科回引官方数据）即满足来源门槛，
        # 不强制 primary/secondary，避免查证型任务为凑来源门槛去抓付费墙/404 的新闻源。
        if kind == "factual" and primary_or_secondary_count == 0 and not is_quick:
            errors.append(err("V040",
                              f"{loc} (factual) needs ≥1 evidence with "
                              f"source quality 'primary' or 'secondary'"))
        interpretive_min_sources = 1 if is_quick else 2
        if kind == "interpretive" and len(unique_source_ids) < interpretive_min_sources:
            errors.append(err("V041",
                              f"{loc} (interpretive) needs ≥{interpretive_min_sources} evidence item(s) "
                              f"from distinct source{'s' if interpretive_min_sources > 1 else ''}",
                              distinct_sources=len(unique_source_ids)))

    # ── Key findings (synthesis layer for downstream consumers) ─────────
    kf = data.get("key_findings")
    min_findings, max_findings = ((1, 3) if is_quick else (2, 6))
    if not (isinstance(kf, list) and min_findings <= len(kf) <= max_findings):
        errors.append(err("V006", f"key_findings must be an array of {min_findings}-{max_findings} items for mode {mode or 'initial'}",
                          length=(len(kf) if isinstance(kf, list) else None)))
    else:
        for i, finding in enumerate(kf):
            loc = f"key_findings[{i}]"
            if not isinstance(finding, dict):
                errors.append(err("V050", f"{loc} must be an object"))
                continue

            ftext = finding.get("finding")
            if not (isinstance(ftext, str) and 10 <= len(ftext) <= 300):
                errors.append(err("V051", f"{loc}.finding must be a string 10-300 chars",
                                  length=(len(ftext) if isinstance(ftext, str) else None)))

            cids = finding.get("claim_ids")
            if not (isinstance(cids, list) and len(cids) >= 1):
                errors.append(err("V052", f"{loc}.claim_ids must be a non-empty array"))
            else:
                for j, cid in enumerate(cids):
                    if not isinstance(cid, str):
                        errors.append(err("V053", f"{loc}.claim_ids[{j}] must be a string", got=cid))
                    elif cid not in seen_claim_ids:
                        errors.append(err("V053",
                                          f"{loc}.claim_ids[{j}] ({cid!r}) not found in claims[]"))

    return errors


def main():
    ap = argparse.ArgumentParser(
        description="Validate an evidence.json file."
    )
    ap.add_argument("path", help="path to {dim}.evidence.json")
    ap.add_argument(
        "--source-cache",
        help="path to report/source_cache; required for v1.2 and verifies files, hashes, URLs, and exact snippets",
    )
    ap.add_argument(
        "--plan",
        help="path to plan.json; validates upstream_usage against dependency_inputs",
    )
    ap.add_argument(
        "--expected-mode",
        choices=sorted(MODE_VALUES),
        help="dispatched research mode; rejects mode-based validation downgrades",
    )
    ap.add_argument(
        "--require-version",
        choices=sorted(SUPPORTED_SCHEMA_VERSIONS),
        help="reject an otherwise valid evidence file that is not this schema version",
    )
    ap.add_argument(
        "--upstream-evidence",
        nargs="*",
        help="finalized evidence files for every direct upstream dependency",
    )
    args = ap.parse_args()

    p = Path(args.path)
    if not p.exists():
        print(json.dumps({"ok": False, "errors": [
            {"rule": "FILE", "severity": "error", "message": f"File not found: {p}"}
        ]}, ensure_ascii=False))
        sys.exit(2)

    try:
        text = p.read_text(encoding="utf-8")
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "errors": [
            {"rule": "JSON", "severity": "error",
             "message": f"Invalid JSON: {e.msg} at line {e.lineno} col {e.colno}"}
        ]}, ensure_ascii=False))
        sys.exit(2)

    plan_data = None
    if args.plan:
        plan_path = Path(args.plan)
        if not plan_path.exists():
            print(json.dumps({"ok": False, "errors": [
                {"rule": "FILE", "severity": "error", "message": f"File not found: {plan_path}"}
            ]}, ensure_ascii=False))
            sys.exit(2)
        try:
            plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(json.dumps({"ok": False, "errors": [
                {"rule": "JSON", "severity": "error", "message": f"Invalid plan JSON: {exc}"}
            ]}, ensure_ascii=False))
            sys.exit(2)

    upstream_evidence_data = None
    if args.upstream_evidence is not None:
        upstream_evidence_data = []
        for upstream_path_value in args.upstream_evidence:
            upstream_path = Path(upstream_path_value)
            if not upstream_path.exists():
                print(json.dumps({"ok": False, "errors": [
                    {"rule": "FILE", "severity": "error", "message": f"File not found: {upstream_path}"}
                ]}, ensure_ascii=False))
                sys.exit(2)
            try:
                upstream_evidence_data.append(json.loads(upstream_path.read_text(encoding="utf-8")))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                print(json.dumps({"ok": False, "errors": [
                    {"rule": "JSON", "severity": "error", "message": f"Invalid upstream evidence JSON: {exc}"}
                ]}, ensure_ascii=False))
                sys.exit(2)
    errors = validate(
        data,
        Path(args.source_cache) if args.source_cache else None,
        plan_data,
        args.expected_mode,
        args.require_version,
        upstream_evidence_data,
    )

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        sys.exit(1)

    claims = data.get("claims", [])
    sources = data.get("sources", [])
    answered_kqs = sorted({c.get("answers_key_question")
                           for c in claims
                           if isinstance(c, dict) and c.get("answers_key_question")})
    extra_findings = sum(1 for c in claims
                         if isinstance(c, dict) and c.get("answers_key_question") is None)

    stats = {
        "claims": len(claims),
        "sources": len(sources),
        "key_findings": len(data.get("key_findings") or []),
        "snapshot_refs": len({
            evidence.get("snapshot_ref")
            for claim in claims if isinstance(claim, dict)
            for evidence in claim.get("evidence", []) if isinstance(evidence, dict)
            if evidence.get("snapshot_ref")
        }),
        "source_cache_verified": bool(args.source_cache),
        "plan_contract_verified": bool(args.plan),
        "expected_mode_verified": bool(args.expected_mode),
        "upstream_evidence_verified": args.upstream_evidence is not None,
        "key_questions_answered": answered_kqs,
        "extra_findings": extra_findings,
        "kind_distribution": {
            k: sum(1 for c in claims if isinstance(c, dict) and c.get("kind") == k)
            for k in sorted(KIND_VALUES)
        },
        "polarity_distribution": {
            p: sum(1 for c in claims if isinstance(c, dict) and c.get("polarity") == p)
            for p in sorted(POLARITY_VALUES)
        },
    }
    print(json.dumps({"ok": True, "stats": stats}, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
