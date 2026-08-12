#!/usr/bin/env python3
"""Validate the current content-unit outline contract.

Validates required fields and resolvable references in outline.json and
optional evidence_subset.json files. Stdlib-only.

Usage:
    # validate outline.json only
    python3 validate_outline.py outline.json

    # validate outline + subsets + cross-check with evidence.json files
    python3 validate_outline.py outline.json \\
        --subsets content_units/ \\
        --evidence sub_reports/d1.evidence.json sub_reports/d2.evidence.json

Output (stdout):
    {"ok": true,  "errors": [], "warnings": [...], "stats": {...}}
    {"ok": false, "errors": [...], "warnings": [...]}

Exit code:
    0 — pass (no errors; warnings allowed)
    1 — fail (any U### error)
    2 — file not found / invalid JSON
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# ── Enums ──────────────────────────────────────────────────────────────────
PARADIGM_VALUES = {
    "panorama", "comparison", "investigation",
    "timeline", "evaluation", "forecast",
}
DEPTH_VALUES = {"overview", "deep_analysis", "expert_level"}
REGISTER_VALUES = {
    "research_brief", "academic", "executive_memo",
    "industry_report", "policy_analysis",
}
VOICE_VALUES = {
    "neutral_analytical", "hedged_scholarly",
    "declarative_executive", "opinionated_supported",
}
CITATION_STYLE_VALUES = {"footnote", "inline"}
NARRATIVE_ROLE_VALUES = {
    "primary_support", "supporting_context",
    "quantifier", "counter", "reference_only",
}
CLAIM_KIND_VALUES = {"factual", "interpretive", "projective"}
POLARITY_VALUES = {"support", "refute", "neutral"}
QUOTE_TYPE_VALUES = {"direct", "paraphrase", "numeric"}
SOURCE_QUALITY_VALUES = {"primary", "secondary", "tertiary"}
WRITING_CONTEXT_KIND_VALUES = {
    "source_profile", "methodology", "scope_boundary",
    "availability_gap", "unresolved_gap",
}
VISUAL_FORM_VALUES = {
    "bar-chart", "distribution-chart", "comparison-table", "metric-strip",
    "timeline", "flowchart", "quadrant-chart",
    "key-fact-callout", "evidence-conflict-callout", "evidence-gap-callout",
    "entity-profile-card", "concept-illustration", "source-image",
}
FORMS_ALLOWING_EMPTY_DATA_REFS = {"concept-illustration"}
SEVERITY_VALUES = {"low", "medium", "high"}
CONTENT_UNIT_TYPE_VALUES = {
    "narrative", "matrix", "timeline", "checklist", "scorecard",
    "qa", "callout", "diagram", "custom",
}
CONTENT_UNIT_ROLE_VALUES = {"primary", "supporting"}
CONTENT_UNIT_RENDER_MODE_VALUES = {
    "prose", "markdown_table", "ordered_list", "checklist", "qa",
    "callout", "mermaid", "mixed", "custom",
}
OPENING_SUMMARY_VALUES = {"none", "findings", "recommendation"}

# ── Regex ──────────────────────────────────────────────────────────────────
CONTENT_UNIT_ID_RE = re.compile(r"^u\d+$")
ELEMENT_ID_RE = re.compile(r"^e\d+$")
CLAIM_ID_RE = re.compile(r"^d\d+\.c\d+$")
WRITING_CONTEXT_ID_RE = re.compile(r"^d\d+\.w\d+$")
SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
TOPIC_TAG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
KQ_ID_RE = re.compile(r"^kq\d+$")


# ── Diagnostic helpers ─────────────────────────────────────────────────────
def err(rule, message, **fields):
    return {"rule": rule, "severity": "error", "message": message, **fields}


def warn(rule, message, **fields):
    return {"rule": rule, "severity": "warning", "message": message, **fields}


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


# ── Outline.json validation ────────────────────────────────────────────────
def validate_outline(data) -> tuple[list, list]:
    """Return (errors, warnings) for the content-unit outline."""
    errors: list = []
    warnings: list = []

    if not isinstance(data, dict):
        return ([err("STRUCT", "Root must be a JSON object")], [])

    if "sections" in data:
        errors.append(err("U008", "outline must not contain sections"))

    paradigm = data.get("paradigm")
    if not isinstance(paradigm, dict):
        errors.append(err("U002", "paradigm must be an object"))
    else:
        main = paradigm.get("main")
        secondary = paradigm.get("secondary")
        if main not in PARADIGM_VALUES:
            errors.append(err("U002", f"paradigm.main must be one of {sorted(PARADIGM_VALUES)}", got=main))
        if secondary is not None and secondary not in PARADIGM_VALUES:
            errors.append(err("U003", f"paradigm.secondary must be null or one of {sorted(PARADIGM_VALUES)}", got=secondary))
        if main is not None and main == secondary:
            errors.append(err("U004", "paradigm.main and paradigm.secondary must differ", main=main))

    depth = data.get("depth_level")
    if depth not in DEPTH_VALUES:
        errors.append(err("U005", f"depth_level must be one of {sorted(DEPTH_VALUES)}", got=depth))
    arc = data.get("global_arc")
    if not nonempty_string(arc):
        errors.append(err("U006", "global_arc must be a non-empty string"))

    # Organization decision is intentionally separate from paradigm. Nothing
    # here maps one enum to the other.
    organization = data.get("organization_decision")
    primary_unit_type = None
    declared_supporting_types: set[str] = set()
    opening_summary = None
    if not isinstance(organization, dict):
        errors.append(err("U010", "organization_decision must be an object"))
    else:
        reader_task = organization.get("reader_task")
        if not nonempty_string(reader_task):
            errors.append(err("U010", "organization_decision.reader_task must be a non-empty string"))

        primary_unit_type = organization.get("primary_unit_type")
        if primary_unit_type not in CONTENT_UNIT_TYPE_VALUES:
            errors.append(err("U011", f"organization_decision.primary_unit_type must be one of {sorted(CONTENT_UNIT_TYPE_VALUES)}", got=primary_unit_type))

        supporting_types = organization.get("supporting_unit_types")
        if not isinstance(supporting_types, list):
            errors.append(err("U012", "organization_decision.supporting_unit_types must be an array"))
        else:
            for i, unit_type in enumerate(supporting_types):
                if unit_type not in CONTENT_UNIT_TYPE_VALUES:
                    errors.append(err("U012", f"organization_decision.supporting_unit_types[{i}] is invalid", got=unit_type))
                elif unit_type in declared_supporting_types:
                    errors.append(err("U012", "organization_decision.supporting_unit_types must be unique", got=unit_type))
                else:
                    declared_supporting_types.add(unit_type)

        opening_summary = organization.get("opening_summary")
        if opening_summary not in OPENING_SUMMARY_VALUES:
            errors.append(err("U013", f"organization_decision.opening_summary must be one of {sorted(OPENING_SUMMARY_VALUES)}", got=opening_summary))
        for field in ("toc", "numbered_headings"):
            if not isinstance(organization.get(field), bool):
                errors.append(err("U014", f"organization_decision.{field} must be boolean", got=organization.get(field)))

        evidence_fit = organization.get("evidence_fit")
        if not nonempty_string(evidence_fit):
            errors.append(err("U015", "organization_decision.evidence_fit must be a non-empty string"))

    # L0 is optional and its presence is controlled explicitly.
    l0 = data.get("L0_draft")
    if opening_summary == "none":
        if l0 is not None:
            errors.append(err("U020", "L0_draft must be null when opening_summary='none'"))
    elif opening_summary in {"findings", "recommendation"}:
        if not isinstance(l0, dict):
            errors.append(err("U020", "L0_draft must be an object when an opening summary is requested"))
        else:
            headline = l0.get("headline")
            if not nonempty_string(headline):
                errors.append(err("U020", "L0_draft.headline must be a non-empty string"))
            findings = l0.get("key_findings")
            if not isinstance(findings, list):
                errors.append(err("U021", "L0_draft.key_findings must be an array"))
            else:
                for i, finding in enumerate(findings):
                    if not nonempty_string(finding):
                        errors.append(err("U022", f"L0_draft.key_findings[{i}] must be a non-empty string"))
            abstract_visual = l0.get("abstract_visual")
            if abstract_visual is not None:
                if not isinstance(abstract_visual, dict):
                    errors.append(err("U023", "L0_draft.abstract_visual must be an object or null"))
                else:
                    form = abstract_visual.get("form")
                    if form not in VISUAL_FORM_VALUES:
                        errors.append(err("U023", f"L0_draft.abstract_visual.form must be one of {sorted(VISUAL_FORM_VALUES)}", got=form))
                    refs = abstract_visual.get("data_refs")
                    min_refs = 0 if form in FORMS_ALLOWING_EMPTY_DATA_REFS else 1
                    if not (isinstance(refs, list) and min_refs <= len(refs) <= 30):
                        errors.append(err("U024", "L0_draft.abstract_visual.data_refs must contain 1-30 claim ids for factual visuals" if min_refs else "L0_draft.abstract_visual.data_refs must contain 0-30 claim ids"))
                    else:
                        for i, claim_id in enumerate(refs):
                            if not (isinstance(claim_id, str) and CLAIM_ID_RE.match(claim_id)):
                                errors.append(err("U024", f"L0_draft.abstract_visual.data_refs[{i}] is invalid", got=claim_id))

    style = data.get("style_contract")
    if not isinstance(style, dict):
        errors.append(err("U030", "style_contract must be an object"))
    else:
        if style.get("register") not in REGISTER_VALUES:
            errors.append(err("U030", f"style_contract.register must be one of {sorted(REGISTER_VALUES)}", got=style.get("register")))
        if style.get("voice") not in VOICE_VALUES:
            errors.append(err("U031", f"style_contract.voice must be one of {sorted(VOICE_VALUES)}", got=style.get("voice")))
        if style.get("citation_style") not in CITATION_STYLE_VALUES:
            errors.append(err("U032", f"style_contract.citation_style must be one of {sorted(CITATION_STYLE_VALUES)}", got=style.get("citation_style")))
        terminology = style.get("terminology")
        preferred = terminology.get("preferred") if isinstance(terminology, dict) else None
        if not isinstance(preferred, dict):
            errors.append(err("U033", "style_contract.terminology.preferred must be an object"))
        else:
            for term, variants in preferred.items():
                if not (isinstance(term, str) and term.strip()):
                    errors.append(err("U033", "preferred terminology keys must be non-empty strings", got=term))
                if not (isinstance(variants, list) and all(isinstance(v, str) and v.strip() for v in variants)):
                    errors.append(err("U033", f"preferred terminology variants for {term!r} must be non-empty strings"))

    content_units = data.get("content_units")
    if not (isinstance(content_units, list) and 1 <= len(content_units) <= 20):
        errors.append(err("U040", "content_units must have length 1-20"))
        content_units = []

    unit_ids = [u.get("id") for u in content_units if isinstance(u, dict) and isinstance(u.get("id"), str)]
    duplicate_unit_ids = [unit_id for unit_id, count in Counter(unit_ids).items() if count > 1]
    if duplicate_unit_ids:
        errors.append(err("U041", "content unit ids must be unique", unit_ids=duplicate_unit_ids))
    unit_id_set = set(unit_ids)
    primary_types: set[str] = set()
    total_word_budget = 0

    for unit_index, unit in enumerate(content_units):
        loc = f"content_units[{unit_index}]"
        if not isinstance(unit, dict):
            errors.append(err("U040", f"{loc} must be an object"))
            continue

        unit_id = unit.get("id")
        if not (isinstance(unit_id, str) and CONTENT_UNIT_ID_RE.match(unit_id)):
            errors.append(err("U041", f"{loc}.id must match ^u\\d+$", got=unit_id))
            continue

        unit_type = unit.get("type")
        if unit_type not in CONTENT_UNIT_TYPE_VALUES:
            errors.append(err("U042", f"{loc}.type must be one of {sorted(CONTENT_UNIT_TYPE_VALUES)}", got=unit_type))
        role = unit.get("role")
        if role not in CONTENT_UNIT_ROLE_VALUES:
            errors.append(err("U043", f"{loc}.role must be one of {sorted(CONTENT_UNIT_ROLE_VALUES)}", got=role))
        elif role == "primary" and unit_type in CONTENT_UNIT_TYPE_VALUES:
            primary_types.add(unit_type)

        title = unit.get("title")
        if not nonempty_string(title):
            errors.append(err("U044", f"{loc}.title must be a non-empty string"))
        reader_task = unit.get("reader_task")
        if not nonempty_string(reader_task):
            errors.append(err("U045", f"{loc}.reader_task must be a non-empty string"))
        word_budget = unit.get("word_budget")
        if not (isinstance(word_budget, int) and not isinstance(word_budget, bool) and word_budget > 0):
            errors.append(err("U046", f"{loc}.word_budget must be a positive int", got=word_budget))
        else:
            total_word_budget += word_budget
        lead = unit.get("lead")
        if lead is not None and not nonempty_string(lead):
            errors.append(err("U047", f"{loc}.lead must be null or a non-empty string"))

        render_contract = unit.get("render_contract")
        if not isinstance(render_contract, dict):
            errors.append(err("U050", f"{loc}.render_contract must be an object"))
        else:
            mode = render_contract.get("mode")
            if mode not in CONTENT_UNIT_RENDER_MODE_VALUES:
                errors.append(err("U050", f"{loc}.render_contract.mode must be one of {sorted(CONTENT_UNIT_RENDER_MODE_VALUES)}", got=mode))
            if not isinstance(render_contract.get("show_heading"), bool):
                errors.append(err("U051", f"{loc}.render_contract.show_heading must be boolean", got=render_contract.get("show_heading")))
            render_schema = render_contract.get("schema")
            if not (isinstance(render_schema, list) and len(render_schema) <= 20):
                errors.append(err("U052", f"{loc}.render_contract.schema must have length 0-20"))
            else:
                valid_fields = [field for field in render_schema if nonempty_string(field)]
                if len(valid_fields) != len(render_schema):
                    errors.append(err("U052", f"{loc}.render_contract.schema entries must be non-empty strings"))
                if len(set(valid_fields)) != len(valid_fields):
                    errors.append(err("U052", f"{loc}.render_contract.schema entries must be unique"))
            instructions = render_contract.get("instructions")
            if not nonempty_string(instructions):
                errors.append(err("U053", f"{loc}.render_contract.instructions must be a non-empty string"))

        elements = unit.get("elements")
        if not (isinstance(elements, list) and 1 <= len(elements) <= 20):
            errors.append(err("U060", f"{loc}.elements must have length 1-20"))
            elements = []
        seen_element_ids: set[str] = set()
        contract_claims: set[str] = set()
        contract_contexts: set[str] = set()

        for element_index, element in enumerate(elements):
            eloc = f"{loc}.elements[{element_index}]"
            if not isinstance(element, dict):
                errors.append(err("U060", f"{eloc} must be an object"))
                continue
            element_id = element.get("id")
            if not (isinstance(element_id, str) and ELEMENT_ID_RE.match(element_id)):
                errors.append(err("U061", f"{eloc}.id must match ^e\\d+$", got=element_id))
            elif element_id in seen_element_ids:
                errors.append(err("U061", f"{eloc}.id duplicates another element", got=element_id))
            else:
                seen_element_ids.add(element_id)
            label = element.get("label")
            if not nonempty_string(label):
                errors.append(err("U062", f"{eloc}.label must be a non-empty string"))
            purpose = element.get("purpose")
            if not nonempty_string(purpose):
                errors.append(err("U063", f"{eloc}.purpose must be a non-empty string"))

            refs = element.get("evidence_refs")
            if not (isinstance(refs, list) and len(refs) <= 10):
                errors.append(err("U064", f"{eloc}.evidence_refs must have length 0-10"))
                refs = []
            seen_element_claims: set[str] = set()
            for ref_index, ref in enumerate(refs):
                rloc = f"{eloc}.evidence_refs[{ref_index}]"
                if not isinstance(ref, dict):
                    errors.append(err("U064", f"{rloc} must be an object"))
                    continue
                claim_id = ref.get("claim_id")
                if not (isinstance(claim_id, str) and CLAIM_ID_RE.match(claim_id)):
                    errors.append(err("U065", f"{rloc}.claim_id is invalid", got=claim_id))
                else:
                    if claim_id in seen_element_claims:
                        errors.append(err("U065", f"{eloc}.evidence_refs must not duplicate a claim", got=claim_id))
                    seen_element_claims.add(claim_id)
                    contract_claims.add(claim_id)
                evidence_role = ref.get("role")
                if evidence_role not in NARRATIVE_ROLE_VALUES:
                    errors.append(err("U066", f"{rloc}.role must be one of {sorted(NARRATIVE_ROLE_VALUES)}", got=evidence_role))

            writing_refs = element.get("writing_context_refs", [])
            if not (isinstance(writing_refs, list) and len(writing_refs) <= 20):
                errors.append(err("U067", f"{eloc}.writing_context_refs must have length 0-20"))
            else:
                if not all(isinstance(ref, str) and WRITING_CONTEXT_ID_RE.match(ref) for ref in writing_refs):
                    errors.append(err("U067", f"{eloc}.writing_context_refs entries must match ^d\\d+\\.w\\d+$", got=writing_refs))
                if len(set(writing_refs)) != len(writing_refs):
                    errors.append(err("U067", f"{eloc}.writing_context_refs must be unique"))
                contract_contexts.update(
                    ref for ref in writing_refs
                    if isinstance(ref, str) and WRITING_CONTEXT_ID_RE.match(ref)
                )
            if not refs and not writing_refs:
                errors.append(err(
                    "U068",
                    f"{eloc} must route at least one claim or writing context",
                ))

        evidence_subset = unit.get("evidence_subset")
        subset_set: set[str] = set()
        if not (isinstance(evidence_subset, list) and len(evidence_subset) <= 30):
            errors.append(err("U070", f"{loc}.evidence_subset must have length 0-30"))
        else:
            for claim_id in evidence_subset:
                if not (isinstance(claim_id, str) and CLAIM_ID_RE.match(claim_id)):
                    errors.append(err("U070", f"{loc}.evidence_subset contains invalid claim id", got=claim_id))
                elif claim_id in subset_set:
                    errors.append(err("U070", f"{loc}.evidence_subset must be unique", got=claim_id))
                else:
                    subset_set.add(claim_id)
        if not contract_claims and not contract_contexts:
            errors.append(err("U070", f"{loc} must route at least one claim or writing context"))

    if primary_unit_type in CONTENT_UNIT_TYPE_VALUES and primary_unit_type not in primary_types:
        errors.append(err("U072", "at least one primary content unit must match organization_decision.primary_unit_type", primary_unit_type=primary_unit_type, actual_primary_types=sorted(primary_types)))
    unexpected_primary_types = primary_types - {primary_unit_type}
    if unexpected_primary_types:
        errors.append(err(
            "U074",
            "all primary content units must match organization_decision.primary_unit_type",
            primary_unit_type=primary_unit_type,
            unexpected_primary_types=sorted(unexpected_primary_types),
        ))

    routing = data.get("claim_routing_table")
    if not isinstance(routing, dict):
        errors.append(err("U080", "claim_routing_table must be an object"))
        routing = {}
    else:
        for claim_id, entry in routing.items():
            if not (isinstance(claim_id, str) and CLAIM_ID_RE.match(claim_id)):
                errors.append(err("U080", "claim_routing_table key is invalid", got=claim_id))
                continue
            if not isinstance(entry, dict):
                errors.append(err("U081", f"claim_routing_table[{claim_id!r}] must be an object"))
                continue
            primary = entry.get("primary")
            if primary not in unit_id_set:
                errors.append(err("U081", f"claim_routing_table[{claim_id!r}].primary is not a content unit", got=primary))

            secondary = entry.get("secondary")
            if not isinstance(secondary, list):
                errors.append(err("U083", f"claim_routing_table[{claim_id!r}].secondary must be an array"))
                secondary = []
            seen_secondary: set[str] = set()
            for secondary_index, secondary_entry in enumerate(secondary):
                sloc = f"claim_routing_table[{claim_id!r}].secondary[{secondary_index}]"
                if not isinstance(secondary_entry, dict):
                    errors.append(err("U083", f"{sloc} must be an object"))
                    continue
                secondary_unit = secondary_entry.get("unit")
                secondary_role = secondary_entry.get("role")
                if secondary_unit not in unit_id_set:
                    errors.append(err("U083", f"{sloc}.unit is not a content unit", got=secondary_unit))
                else:
                    if secondary_unit == primary or secondary_unit in seen_secondary:
                        errors.append(err("U084", f"{sloc}.unit duplicates a routed unit", got=secondary_unit))
                    seen_secondary.add(secondary_unit)
                if secondary_role not in {"supporting_context", "reference_only"}:
                    errors.append(err("U086", f"{sloc}.role must be supporting_context or reference_only", got=secondary_role))

    scan = data.get("scan_summary")
    if not isinstance(scan, dict):
        errors.append(err("U100", "scan_summary must be an object"))
    else:
        totals = scan.get("totals")
        if not isinstance(totals, dict):
            errors.append(err("U100", "scan_summary.totals must be an object"))
        else:
            for field in ("claims", "sources"):
                value = totals.get(field)
                if not (isinstance(value, int) and not isinstance(value, bool) and value >= 0):
                    errors.append(err("U100", f"scan_summary.totals.{field} must be a non-negative int", got=value))
            ratio = totals.get("primary_ratio")
            if not (isinstance(ratio, (int, float)) and not isinstance(ratio, bool) and 0 <= ratio <= 1):
                errors.append(err("U101", "scan_summary.totals.primary_ratio must be in [0, 1]", got=ratio))

        clusters = scan.get("topic_clusters", [])
        if not isinstance(clusters, list):
            errors.append(err("U102", "scan_summary.topic_clusters must be an array"))
        else:
            for cluster_index, cluster in enumerate(clusters):
                if not isinstance(cluster, dict):
                    errors.append(err("U102", f"scan_summary.topic_clusters[{cluster_index}] must be an object"))

        conflicts = scan.get("conflicts", [])
        if not isinstance(conflicts, list):
            errors.append(err("U103", "scan_summary.conflicts must be an array"))
        else:
            for conflict_index, conflict in enumerate(conflicts):
                if not isinstance(conflict, dict):
                    errors.append(err("U103", f"scan_summary.conflicts[{conflict_index}] must be an object"))
                elif conflict.get("severity") not in SEVERITY_VALUES:
                    errors.append(err("U103", f"scan_summary.conflicts[{conflict_index}].severity must be one of {sorted(SEVERITY_VALUES)}", got=conflict.get("severity")))

        for field in ("key_entities", "timeline_density", "gaps"):
            if not isinstance(scan.get(field, []), list):
                errors.append(err("U103", f"scan_summary.{field} must be an array"))

        signal = scan.get("reader_task_signal")
        if not isinstance(signal, dict):
            errors.append(err("U104", "scan_summary.reader_task_signal must be an object"))
        else:
            for key, value in signal.items():
                if key not in PARADIGM_VALUES:
                    errors.append(err("U104", "reader_task_signal contains an unknown paradigm", got=key))
                if not (isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1):
                    errors.append(err("U104", f"reader_task_signal[{key!r}] must be in [0, 1]", got=value))

    return errors, warnings


# ── evidence_subset.json validation ───────────────────────────────────────
def validate_subset(
    subset_data,
    outline_data,
    evidence_index=None,
    writing_context_index=None,
) -> list:
    """Validate subset fields and make sure routed ids can be resolved.

    The planner is not required to reproduce evidence objects byte-for-byte.
    Original evidence files remain the source of truth; this gate only checks
    that the subset has usable fields and references known ids.
    """
    errors: list = []
    strict_claims = evidence_index is not None
    strict_contexts = writing_context_index is not None
    evidence_index = evidence_index or {}
    writing_context_index = writing_context_index or {}
    if not isinstance(subset_data, dict):
        return [err("STRUCT", "Root must be a JSON object")]

    unit_id = subset_data.get("content_unit_id")
    if not (isinstance(unit_id, str) and CONTENT_UNIT_ID_RE.match(unit_id)):
        errors.append(err("U202", "content_unit_id must match ^u\\d+$", got=unit_id))
        return errors

    matching_unit = None
    for unit in outline_data.get("content_units", []) if isinstance(outline_data, dict) else []:
        if isinstance(unit, dict) and unit.get("id") == unit_id:
            matching_unit = unit
            break
    if matching_unit is None:
        errors.append(err("U203", f"content_unit_id ({unit_id!r}) not found in outline.content_units"))
        return errors

    required_claim_ids: set[str] = set()
    required_context_ids: set[str] = set()
    for element in matching_unit.get("elements", []) if isinstance(matching_unit, dict) else []:
        if not isinstance(element, dict):
            continue
        for evidence_ref in element.get("evidence_refs", []) or []:
            if isinstance(evidence_ref, dict) and isinstance(evidence_ref.get("claim_id"), str):
                required_claim_ids.add(evidence_ref["claim_id"])
        for context_id in element.get("writing_context_refs", []) or []:
            if isinstance(context_id, str):
                required_context_ids.add(context_id)

    claims = subset_data.get("claims")
    if not (isinstance(claims, list) and len(claims) <= 30):
        errors.append(err("U210", "claims must have length 0-30"))
        return errors

    subset_claim_ids: set[str] = set()
    referenced_source_ids: set[str] = set()
    for claim_index, claim in enumerate(claims):
        cloc = f"claims[{claim_index}]"
        if not isinstance(claim, dict):
            errors.append(err("U210", f"{cloc} must be an object"))
            continue

        claim_id = claim.get("id")
        if not (isinstance(claim_id, str) and CLAIM_ID_RE.fullmatch(claim_id)):
            errors.append(err("U210", f"{cloc}.id must match ^d\\d+\\.c\\d+$", got=claim_id))
        elif claim_id in subset_claim_ids:
            errors.append(err("U210", f"{cloc}.id duplicates another claim", got=claim_id))
        else:
            subset_claim_ids.add(claim_id)

        if not nonempty_string(claim.get("text")):
            errors.append(err("U212", f"{cloc}.text must be a non-empty string", claim_id=claim_id))
        if claim.get("kind") not in CLAIM_KIND_VALUES:
            errors.append(err("U212", f"{cloc}.kind must be one of {sorted(CLAIM_KIND_VALUES)}", claim_id=claim_id, got=claim.get("kind")))
        if claim.get("polarity") not in POLARITY_VALUES:
            errors.append(err("U212", f"{cloc}.polarity must be one of {sorted(POLARITY_VALUES)}", claim_id=claim_id, got=claim.get("polarity")))
        topic_tag = claim.get("topic_tag")
        if not (isinstance(topic_tag, str) and TOPIC_TAG_RE.fullmatch(topic_tag)):
            errors.append(err("U212", f"{cloc}.topic_tag is invalid", claim_id=claim_id, got=topic_tag))

        narrative_role = claim.get("narrative_role")
        if narrative_role not in NARRATIVE_ROLE_VALUES:
            errors.append(err("U213", f"{cloc}.narrative_role must be one of {sorted(NARRATIVE_ROLE_VALUES)}", got=narrative_role))

        if (
            strict_claims
            and isinstance(claim_id, str)
            and CLAIM_ID_RE.fullmatch(claim_id)
            and claim_id not in evidence_index
        ):
            errors.append(err("U212", f"{cloc}.id does not exist in supplied evidence files", claim_id=claim_id))

        claim_evidence = claim.get("evidence")
        if not isinstance(claim_evidence, list) or not claim_evidence:
            errors.append(err("U212", f"{cloc}.evidence must be a non-empty array", claim_id=claim_id))
            claim_evidence = []
        for evidence_index_number, evidence_item in enumerate(claim_evidence):
            eloc = f"{cloc}.evidence[{evidence_index_number}]"
            if not isinstance(evidence_item, dict):
                errors.append(err("U212", f"{eloc} must be an object", claim_id=claim_id))
                continue
            source_id = evidence_item.get("source_id")
            if not nonempty_string(source_id):
                errors.append(err("U212", f"{eloc}.source_id must be a non-empty string", claim_id=claim_id))
            else:
                referenced_source_ids.add(source_id)
            if not nonempty_string(evidence_item.get("snippet")):
                errors.append(err("U212", f"{eloc}.snippet must be a non-empty string", claim_id=claim_id))
            if evidence_item.get("quote_type") not in QUOTE_TYPE_VALUES:
                errors.append(err("U212", f"{eloc}.quote_type must be one of {sorted(QUOTE_TYPE_VALUES)}", claim_id=claim_id, got=evidence_item.get("quote_type")))
    missing_claim_ids = required_claim_ids - subset_claim_ids
    if missing_claim_ids:
        errors.append(err(
            "U210",
            "subset is missing claims referenced by this content unit",
            missing_claim_ids=sorted(missing_claim_ids),
        ))

    writing_context = subset_data.get("writing_context", [])
    if not isinstance(writing_context, list):
        errors.append(err("U215", "writing_context must be an array"))
        writing_context = []
    else:
        context_id_set: set[str] = set()
        for context_index, context in enumerate(writing_context):
            cloc = f"writing_context[{context_index}]"
            if not isinstance(context, dict):
                errors.append(err("U215", f"{cloc} must be an object"))
                continue
            context_id = context.get("id")
            if not (isinstance(context_id, str) and WRITING_CONTEXT_ID_RE.fullmatch(context_id)):
                errors.append(err("U215", f"{cloc}.id must match ^d\\d+\\.w\\d+$", got=context_id))
            elif context_id in context_id_set:
                errors.append(err("U215", f"{cloc}.id duplicates another writing context", got=context_id))
            else:
                context_id_set.add(context_id)
            if (
                strict_contexts
                and isinstance(context_id, str)
                and WRITING_CONTEXT_ID_RE.fullmatch(context_id)
                and context_id not in writing_context_index
            ):
                errors.append(err("U216", f"{cloc}.id does not exist in supplied evidence files", context_id=context_id))
            if context.get("kind") not in WRITING_CONTEXT_KIND_VALUES:
                errors.append(err("U216", f"{cloc}.kind must be one of {sorted(WRITING_CONTEXT_KIND_VALUES)}", context_id=context_id, got=context.get("kind")))
            if not nonempty_string(context.get("text")):
                errors.append(err("U216", f"{cloc}.text must be a non-empty string", context_id=context_id))
            if not nonempty_string(context.get("use")):
                errors.append(err("U216", f"{cloc}.use must be a non-empty string", context_id=context_id))

            context_sources = context.get("source_ids", [])
            if not isinstance(context_sources, list) or not all(nonempty_string(value) for value in context_sources):
                errors.append(err("U216", f"{cloc}.source_ids must be an array of strings", context_id=context_id))
            else:
                referenced_source_ids.update(context_sources)
            applies_to = context.get("applies_to", [])
            if not isinstance(applies_to, list) or not all(isinstance(value, str) and KQ_ID_RE.fullmatch(value) for value in applies_to):
                errors.append(err("U216", f"{cloc}.applies_to must be an array of kq ids", context_id=context_id))

        missing_context_ids = required_context_ids - context_id_set
        if missing_context_ids:
            errors.append(err(
                "U215",
                "subset is missing writing contexts referenced by this content unit",
                missing_context_ids=sorted(missing_context_ids),
            ))

    sources = subset_data.get("sources")
    if not isinstance(sources, list):
        errors.append(err("U211", "sources must be an array"))
        sources = []
    declared_source_ids: set[str] = set()
    for source_index, source in enumerate(sources):
        sloc = f"sources[{source_index}]"
        if not isinstance(source, dict):
            errors.append(err("U211", f"{sloc} must be an object"))
            continue
        source_id = source.get("id")
        if not (isinstance(source_id, str) and SOURCE_ID_RE.fullmatch(source_id)):
            errors.append(err("U211", f"{sloc}.id is invalid", got=source_id))
        elif source_id in declared_source_ids:
            errors.append(err("U211", f"{sloc}.id duplicates another source", got=source_id))
        else:
            declared_source_ids.add(source_id)
        if not nonempty_string(source.get("url")):
            errors.append(err("U211", f"{sloc}.url must be a non-empty string", source_id=source_id))
        if not nonempty_string(source.get("title")):
            errors.append(err("U211", f"{sloc}.title must be a non-empty string", source_id=source_id))
        if source.get("quality") not in SOURCE_QUALITY_VALUES:
            errors.append(err("U211", f"{sloc}.quality must be one of {sorted(SOURCE_QUALITY_VALUES)}", source_id=source_id, got=source.get("quality")))
        published_at = source.get("published_at")
        if published_at is not None and not nonempty_string(published_at):
            errors.append(err("U211", f"{sloc}.published_at must be a non-empty string when present", source_id=source_id))

    missing_source_ids = referenced_source_ids - declared_source_ids
    if missing_source_ids:
        errors.append(err("U211", "sources[] does not cover all referenced source_ids", missing=sorted(missing_source_ids)))

    return errors


# ── Helpers ────────────────────────────────────────────────────────────────
def load_json(path: Path):
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def build_evidence_index(evidence_paths: list[Path]) -> dict:
    """Return claim_id → claim dict from a list of evidence.json files."""
    index: dict = {}
    for p in evidence_paths:
        try:
            data = load_json(p)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for c in data.get("claims") or []:
            if isinstance(c, dict):
                cid = c.get("id")
                if isinstance(cid, str):
                    index[cid] = c
    return index


def build_writing_context_index(evidence_paths: list[Path]) -> dict:
    """Return writing_context id -> context object from evidence.json files."""
    index: dict = {}
    for p in evidence_paths:
        try:
            data = load_json(p)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for context in data.get("writing_context") or []:
            if isinstance(context, dict):
                context_id = context.get("id")
                if isinstance(context_id, str):
                    index[context_id] = context
    return index


def compute_stats(data) -> dict:
    content_units = data.get("content_units") or []
    routing = data.get("claim_routing_table") or {}
    l0 = data.get("L0_draft") or {}
    organization = data.get("organization_decision") or {}
    total_word_budget = sum(
        unit.get("word_budget", 0)
        for unit in content_units
        if isinstance(unit, dict) and isinstance(unit.get("word_budget"), int)
        and not isinstance(unit.get("word_budget"), bool)
    )
    return {
        "paradigm": data.get("paradigm") or {},
        "depth_level": data.get("depth_level"),
        "headline": l0.get("headline"),
        "primary_unit_type": organization.get("primary_unit_type"),
        "content_units_count": len(content_units),
        "primary_units_count": sum(
            1 for unit in content_units
            if isinstance(unit, dict) and unit.get("role") == "primary"
        ),
        "total_word_budget": total_word_budget,
        "routing_table_size": len(routing),
    }


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Validate outline.json and optional evidence_subset.json files."
    )
    ap.add_argument("outline", help="path to outline.json")
    ap.add_argument("--subsets", metavar="DIR_OR_GLOB",
                    help="directory containing content-unit evidence_subset.json files")
    ap.add_argument("--evidence", nargs="*", default=[],
                    help="paths to d{N}.evidence.json files for referenced-id checks")
    args = ap.parse_args()

    p = Path(args.outline)
    if not p.exists():
        print(json.dumps({"ok": False, "errors": [
            {"rule": "FILE", "severity": "error", "message": f"File not found: {p}"}
        ]}, ensure_ascii=False))
        sys.exit(2)

    try:
        outline_data = load_json(p)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "errors": [
            {"rule": "JSON", "severity": "error",
             "message": f"Invalid JSON in {p}: {e.msg} at line {e.lineno} col {e.colno}"}
        ]}, ensure_ascii=False))
        sys.exit(2)

    all_errors, all_warnings = validate_outline(outline_data)

    # Subsets check (optional)
    if args.subsets:
        subset_dir = Path(args.subsets)
        if subset_dir.is_dir():
            subset_paths = sorted(subset_dir.glob("*.evidence_subset.json"))
        else:
            subset_paths = [Path(p) for p in [args.subsets] if Path(p).exists()]

        evidence_paths = [Path(e) for e in args.evidence]
        evidence_index = build_evidence_index(evidence_paths) if args.evidence else None
        writing_context_index = build_writing_context_index(evidence_paths) if args.evidence else None
        subset_files_by_unit: dict[str, list[str]] = {}
        expected_unit_ids = {
            unit.get("id")
            for unit in outline_data.get("content_units", []) or []
            if isinstance(unit, dict) and isinstance(unit.get("id"), str)
        }

        for sp in subset_paths:
            try:
                sub_data = load_json(sp)
            except json.JSONDecodeError as e:
                all_errors.append(err("JSON",
                                      f"Invalid JSON in {sp}: {e.msg} at line {e.lineno} col {e.colno}",
                                      file=str(sp)))
                continue
            if isinstance(sub_data, dict) and isinstance(sub_data.get("content_unit_id"), str):
                declared_unit_id = sub_data["content_unit_id"]
                if declared_unit_id not in expected_unit_ids:
                    all_warnings.append(warn(
                        "U200",
                        "ignoring a stale evidence subset not referenced by the current outline",
                        file=str(sp),
                        content_unit_id=declared_unit_id,
                    ))
                    continue
                subset_files_by_unit.setdefault(declared_unit_id, []).append(str(sp))
                expected_name = f"{declared_unit_id}.evidence_subset.json"
                if sp.name != expected_name:
                    all_errors.append(err(
                        "U200",
                        "content-unit subset filename must match content_unit_id",
                        file=str(sp),
                        expected_name=expected_name,
                    ))
            sub_errors = validate_subset(
                sub_data,
                outline_data,
                evidence_index,
                writing_context_index,
            )
            for e_obj in sub_errors:
                e_obj["file"] = str(sp)
            all_errors.extend(sub_errors)

        missing_unit_ids = sorted(expected_unit_ids - set(subset_files_by_unit))
        duplicate_unit_ids = {
            unit_id: files
            for unit_id, files in subset_files_by_unit.items()
            if unit_id in expected_unit_ids and len(files) != 1
        }
        if missing_unit_ids or duplicate_unit_ids:
            all_errors.append(err(
                "U200",
                "each content unit must have exactly one evidence subset file",
                missing_content_units=missing_unit_ids,
                duplicate_content_units=duplicate_unit_ids,
            ))

    output: dict = {"ok": len(all_errors) == 0}
    if all_errors:
        output["errors"] = all_errors
    if all_warnings:
        output["warnings"] = all_warnings
    if output["ok"]:
        output["stats"] = compute_stats(outline_data)

    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(0 if output["ok"] else 1)


if __name__ == "__main__":
    main()
