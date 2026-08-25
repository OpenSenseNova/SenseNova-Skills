#!/usr/bin/env python3
"""Evidence schema validator.

Validates a {dim}.evidence.json file against the rules documented in
schemas/evidence.schema.md. Stdlib-only, no external dependencies.

Usage:
    python3 validate_evidence.py path/to/d1.evidence.json \
        --plan path/to/report/plan.json \
        --expected-mode initial

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
from urllib.parse import urlsplit

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
DIM_ID_RE = re.compile(r"^d\d+$")
CLAIM_ID_RE = re.compile(r"^d\d+\.c\d+$")
SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
TOPIC_TAG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
KQ_ID_RE = re.compile(r"^kq\d+$")
DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
WRITING_CONTEXT_ID_RE = re.compile(r"^d\d+\.w\d+$")


def err(rule, message, **fields):
    return {"rule": rule, "severity": "error", "message": message, **fields}


def is_http_url(value: str) -> bool:
    try:
        parts = urlsplit(value)
        return (
            parts.scheme.lower() in {"http", "https"}
            and bool(parts.hostname)
            and parts.username is None
            and parts.password is None
        )
    except (TypeError, ValueError):
        return False


def validate(
    data,
    plan_data: object | None = None,
    expected_mode: str | None = None,
) -> list:
    errors = []

    # ── Top-level structure ─────────────────────────────────────────────
    if not isinstance(data, dict):
        return [err("STRUCT", "Root must be a JSON object")]

    dim_id = data.get("dimension_id")
    if not (isinstance(dim_id, str) and DIM_ID_RE.match(dim_id)):
        errors.append(err("V002", "dimension_id must match ^d\\d+$", got=dim_id))
        dim_id = None  # disable downstream id-prefix check

    # mode records orchestration only; evidence quality rules are mode-independent.
    mode = data.get("mode")
    if mode is not None and mode not in MODE_VALUES:
        errors.append(err("V018", f"mode must be one of {sorted(MODE_VALUES)} if present", got=mode))
    if expected_mode is not None and mode != expected_mode:
        errors.append(err(
            "V009",
            "evidence mode must match the dispatched research mode",
            expected=expected_mode,
            got=mode,
        ))

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

    headline = data.get("headline")
    if not (isinstance(headline, str) and headline.strip()):
        errors.append(err("V003", "headline must be a non-empty string"))

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
        elif not is_http_url(url):
            errors.append(err("V014", f"{loc}.url must be a valid HTTP(S) URL"))

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
            if not (isinstance(context_text, str) and context_text.strip()):
                errors.append(err("V063", f"{loc}.text must be a non-empty string"))
            use = context.get("use")
            if not (isinstance(use, str) and use.strip()):
                errors.append(err("V064", f"{loc}.use must be a non-empty string"))

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
        if not (isinstance(text, str) and text.strip()):
            errors.append(err("V024", f"{loc}.text must be a non-empty string"))

        kind = claim.get("kind")
        if kind not in KIND_VALUES:
            errors.append(err("V025", f"{loc}.kind must be one of {sorted(KIND_VALUES)}", got=kind))

        polarity = claim.get("polarity")
        if polarity not in POLARITY_VALUES:
            errors.append(err("V026", f"{loc}.polarity must be one of {sorted(POLARITY_VALUES)}",
                              got=polarity))

        topic_tag = claim.get("topic_tag")
        if not (isinstance(topic_tag, str) and TOPIC_TAG_RE.match(topic_tag)):
            errors.append(err("V027", f"{loc}.topic_tag must match ^[a-z][a-z0-9_]*$",
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

        # ── Kind-specific evidence rules ────────────────────────────
        if kind == "factual" and primary_or_secondary_count == 0:
            errors.append(err("V040",
                              f"{loc} (factual) needs ≥1 evidence with "
                              f"source quality 'primary' or 'secondary'"))
        interpretive_min_sources = 2
        if kind == "interpretive" and len(unique_source_ids) < interpretive_min_sources:
            errors.append(err("V041",
                              f"{loc} (interpretive) needs ≥{interpretive_min_sources} evidence item(s) "
                              f"from distinct source{'s' if interpretive_min_sources > 1 else ''}",
                              distinct_sources=len(unique_source_ids)))

    # ── Key findings (synthesis layer for downstream consumers) ─────────
    kf = data.get("key_findings")
    if not (isinstance(kf, list) and kf):
        errors.append(err("V006", "key_findings must be a non-empty array",
                          length=(len(kf) if isinstance(kf, list) else None)))
    else:
        for i, finding in enumerate(kf):
            loc = f"key_findings[{i}]"
            if not isinstance(finding, dict):
                errors.append(err("V050", f"{loc} must be an object"))
                continue

            ftext = finding.get("finding")
            if not (isinstance(ftext, str) and ftext.strip()):
                errors.append(err("V051", f"{loc}.finding must be a non-empty string"))

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
        "--plan",
        help="path to plan.json; validates that dimension_id exists in the plan",
    )
    ap.add_argument(
        "--expected-mode",
        choices=sorted(MODE_VALUES),
        help="dispatched research mode; rejects mode-based validation downgrades",
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

    errors = validate(
        data,
        plan_data,
        args.expected_mode,
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
        "plan_contract_verified": bool(args.plan),
        "expected_mode_verified": bool(args.expected_mode),
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
