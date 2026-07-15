#!/usr/bin/env python3
"""Outline schema validator for v1.0 sections and v2.0 content units.

Validates outline.json (and optionally evidence_subset.json files) against
the rules documented in schemas/outline.schema.md. Stdlib-only.

Usage:
    # validate outline.json only
    python3 validate_outline.py outline.json

    # validate outline + subsets + cross-check with evidence.json files
    python3 validate_outline.py outline.json \\
        --format format.json \\
        --language zh-Hans \\
        --subsets content_units/ \\
        --evidence sub_reports/d1.evidence.json sub_reports/d2.evidence.json

Output (stdout):
    {"ok": true,  "errors": [], "warnings": [...], "stats": {...}}
    {"ok": false, "errors": [...], "warnings": [...]}

Exit code:
    0 — pass (no errors; warnings allowed)
    1 — fail (any O### / S### error)
    2 — file not found / invalid JSON
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

LEGACY_SCHEMA_VERSION = "1.0"
CONTENT_UNIT_SCHEMA_VERSION = "2.0"
SUPPORTED_SCHEMA_VERSIONS = {LEGACY_SCHEMA_VERSION, CONTENT_UNIT_SCHEMA_VERSION}

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
SECTION_ROLE_VALUES = {
    "context", "exposition", "comparison", "argument",
    "counter", "synthesis", "outlook", "action",
}
NARRATIVE_ROLE_VALUES = {
    "primary_support", "supporting_context",
    "quantifier", "counter", "reference_only",
}
VISUAL_FORM_VALUES = {
    "bar-chart", "distribution-chart", "comparison-table", "metric-strip",
    "timeline", "flowchart", "quadrant-chart",
    "key-fact-callout", "evidence-conflict-callout", "evidence-gap-callout",
    "entity-profile-card", "concept-illustration", "source-image",
}
VISUAL_POSITION_VALUES = {"after_lead", "mid", "before_close"}
VISUAL_RENDER_VALUES = {
    "mermaid-code", "markdown-table", "markdown-callout",
    "ai-generated-image", "existing-image",
}
VISUAL_INFORMATION_TYPE_VALUES = {
    "numeric-ranking", "part-to-whole-distribution",
    "multi-entity-comparison", "multi-metric-summary",
    "timeline-events", "process-or-causal-flow", "system-structure",
    "two-axis-positioning", "key-fact-highlight",
    "evidence-conflict", "evidence-gap", "entity-profile",
    "concept-or-scene-illustration", "source-or-screenshot-image",
}
FORM_TO_RENDER = {
    "bar-chart": "mermaid-code",
    "distribution-chart": "mermaid-code",
    "comparison-table": "markdown-table",
    "metric-strip": "markdown-table",
    "timeline": "mermaid-code",
    "flowchart": "mermaid-code",
    "quadrant-chart": "mermaid-code",
    "key-fact-callout": "markdown-callout",
    "evidence-conflict-callout": "markdown-callout",
    "evidence-gap-callout": "markdown-callout",
    "entity-profile-card": "markdown-callout",
    "concept-illustration": "ai-generated-image",
    "source-image": "existing-image",
}
FORM_TO_INFORMATION_TYPES = {
    "bar-chart": {"numeric-ranking"},
    "distribution-chart": {"part-to-whole-distribution"},
    "comparison-table": {"multi-entity-comparison"},
    "metric-strip": {"multi-metric-summary"},
    "timeline": {"timeline-events"},
    "flowchart": {"process-or-causal-flow", "system-structure"},
    "quadrant-chart": {"two-axis-positioning"},
    "key-fact-callout": {"key-fact-highlight"},
    "evidence-conflict-callout": {"evidence-conflict"},
    "evidence-gap-callout": {"evidence-gap"},
    "entity-profile-card": {"entity-profile"},
    "concept-illustration": {"concept-or-scene-illustration"},
    "source-image": {"source-or-screenshot-image"},
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
PREFERENCE_STRENGTH_VALUES = {"required", "preferred", "auto"}
PREFERENCE_RESOLUTION_VALUES = {
    "required_honored", "preferred_honored", "preferred_adapted",
    "auto_selected",
}
OPENING_SUMMARY_VALUES = {"none", "findings", "recommendation"}

# ── Regex ──────────────────────────────────────────────────────────────────
SECTION_ID_RE = re.compile(r"^s\d+$")
CONTENT_UNIT_ID_RE = re.compile(r"^u\d+$")
ELEMENT_ID_RE = re.compile(r"^e\d+$")
CLAIM_ID_RE = re.compile(r"^d\d+\.c\d+$")
WRITING_CONTEXT_ID_RE = re.compile(r"^d\d+\.w\d+$")
NUMBERED_TITLE_RE = re.compile(r"^(?:\d+[.、)]|[一二三四五六七八九十]+、)\s*\S")


# ── Diagnostic helpers ─────────────────────────────────────────────────────
def err(rule, message, **fields):
    return {"rule": rule, "severity": "error", "message": message, **fields}


def warn(rule, message, **fields):
    return {"rule": rule, "severity": "warning", "message": message, **fields}


def char_len(s):
    return len(s) if isinstance(s, str) else None


# ── Outline.json validation ────────────────────────────────────────────────
def validate_outline_v1(data) -> tuple[list, list]:
    """Return (errors, warnings) for a legacy v1.0 outline document."""
    errors: list = []
    warnings: list = []

    if not isinstance(data, dict):
        return ([err("STRUCT", "Root must be a JSON object")], [])

    # ── Top level (O001-O008) ──────────────────────────────────────────────
    sv = data.get("schema_version")
    if sv != LEGACY_SCHEMA_VERSION:
        errors.append(err("O001", f"schema_version must be '{LEGACY_SCHEMA_VERSION}'", got=sv))

    paradigm = data.get("paradigm")
    paradigm_main = paradigm_secondary = None
    if not isinstance(paradigm, dict):
        errors.append(err("O002", "paradigm must be an object"))
    else:
        paradigm_main = paradigm.get("main")
        paradigm_secondary = paradigm.get("secondary")
        if paradigm_main not in PARADIGM_VALUES:
            errors.append(err("O002", f"paradigm.main must be one of {sorted(PARADIGM_VALUES)}",
                              got=paradigm_main))
        if paradigm_secondary is not None and paradigm_secondary not in PARADIGM_VALUES:
            errors.append(err("O003",
                              f"paradigm.secondary must be null or one of {sorted(PARADIGM_VALUES)}",
                              got=paradigm_secondary))
        if (paradigm_main is not None
                and paradigm_secondary is not None
                and paradigm_main == paradigm_secondary):
            errors.append(err("O004",
                              "paradigm.main and paradigm.secondary must differ",
                              main=paradigm_main, secondary=paradigm_secondary))

    depth = data.get("depth_level")
    if depth not in DEPTH_VALUES:
        errors.append(err("O005", f"depth_level must be one of {sorted(DEPTH_VALUES)}", got=depth))

    arc = data.get("global_arc")
    if not (isinstance(arc, str) and 40 <= len(arc) <= 120):
        errors.append(err("O006", "global_arc must be a string 40-120 chars",
                          length=char_len(arc)))

    sections = data.get("sections")
    if not (isinstance(sections, list) and len(sections) >= 3):
        errors.append(err("O007", "sections must be an array of length ≥ 3"))
        sections = []

    section_ids: list[str] = []
    for s in sections:
        if isinstance(s, dict):
            sid = s.get("id")
            if isinstance(sid, str):
                section_ids.append(sid)
    duplicate_sids = [sid for sid, n in Counter(section_ids).items() if n > 1]
    if duplicate_sids:
        errors.append(err("O008", f"duplicate section ids: {duplicate_sids}"))

    section_id_set = set(section_ids)
    abstract_visual_refs: set[str] = set()

    # ── L0_draft (O010-O013) ───────────────────────────────────────────────
    L0 = data.get("L0_draft")
    if not isinstance(L0, dict):
        errors.append(err("O010", "L0_draft must be an object"))
    else:
        headline = L0.get("headline")
        if not (isinstance(headline, str) and 8 <= len(headline) <= 30):
            errors.append(err("O010", "L0_draft.headline must be a string 8-30 chars",
                              length=char_len(headline)))

        kfs = L0.get("key_findings")
        if not (isinstance(kfs, list) and 3 <= len(kfs) <= 5):
            errors.append(err("O011", "L0_draft.key_findings must have length 3-5",
                              length=(len(kfs) if isinstance(kfs, list) else None)))
        else:
            for i, kf in enumerate(kfs):
                if not (isinstance(kf, str) and 20 <= len(kf) <= 60):
                    errors.append(err("O012",
                                      f"L0_draft.key_findings[{i}] must be a string 20-60 chars",
                                      length=char_len(kf)))

        av = L0.get("abstract_visual")
        if av is not None:
            if not isinstance(av, dict):
                errors.append(err("O013", "L0_draft.abstract_visual must be an object or null"))
            else:
                form = av.get("form")
                if form not in VISUAL_FORM_VALUES:
                    errors.append(err("O013",
                                      f"L0_draft.abstract_visual.form must be one of "
                                      f"{sorted(VISUAL_FORM_VALUES)}", got=form))
                data_refs = av.get("data_refs")
                min_refs = 0 if form in FORMS_ALLOWING_EMPTY_DATA_REFS else 1
                if not (isinstance(data_refs, list) and len(data_refs) >= min_refs):
                    if min_refs == 0:
                        errors.append(err("O014", "L0_draft.abstract_visual.data_refs must be an array"))
                    else:
                        errors.append(err("O014", "L0_draft.abstract_visual.data_refs must be a non-empty array"))
                else:
                    for i, ref in enumerate(data_refs):
                        if not (isinstance(ref, str) and CLAIM_ID_RE.match(ref)):
                            errors.append(err("O014",
                                              f"L0_draft.abstract_visual.data_refs[{i}] must match ^d\\d+\\.c\\d+$",
                                              got=ref))
                        else:
                            abstract_visual_refs.add(ref)

    # ── Style contract (O020-O023) ─────────────────────────────────────────
    style = data.get("style_contract")
    if not isinstance(style, dict):
        errors.append(err("O020", "style_contract must be an object"))
    else:
        if style.get("register") not in REGISTER_VALUES:
            errors.append(err("O020", f"style_contract.register must be one of {sorted(REGISTER_VALUES)}",
                              got=style.get("register")))
        if style.get("voice") not in VOICE_VALUES:
            errors.append(err("O021", f"style_contract.voice must be one of {sorted(VOICE_VALUES)}",
                              got=style.get("voice")))
        if style.get("citation_style") not in CITATION_STYLE_VALUES:
            errors.append(err("O022",
                              f"style_contract.citation_style must be one of {sorted(CITATION_STYLE_VALUES)}",
                              got=style.get("citation_style")))
        term = style.get("terminology")
        if not isinstance(term, dict):
            errors.append(err("O023", "style_contract.terminology must be an object"))
        else:
            preferred = term.get("preferred")
            if not isinstance(preferred, dict):
                errors.append(err("O023", "style_contract.terminology.preferred must be an object"))
            else:
                for k, v in preferred.items():
                    if not (isinstance(k, str) and k.strip()):
                        errors.append(err("O023",
                                          f"style_contract.terminology.preferred has empty key",
                                          key=repr(k)))
                    if not (isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v)):
                        errors.append(err("O023",
                                          f"style_contract.terminology.preferred[{k!r}] must be a list of non-empty strings"))

    # ── Sections (O030-O063), Blocks (O040-O044), Visuals (O050-O055) ───
    section_evidence_subset_by_id: dict[str, set[str]] = {}
    section_claim_usage_by_id: dict[str, set[str]] = {}
    section_visuals_flat: list[tuple[str, str]] = []
    visual_forms_used: set[str] = set()
    narrative_roles_used: set[str] = set()
    n_sections = len(sections)

    for idx, sec in enumerate(sections):
        loc = f"sections[{idx}]"
        if not isinstance(sec, dict):
            errors.append(err("O030", f"{loc} must be an object"))
            continue

        sid = sec.get("id")
        if not (isinstance(sid, str) and SECTION_ID_RE.match(sid)):
            errors.append(err("O030", f"{loc}.id must match ^s\\d+$", got=sid))
            continue

        title = sec.get("title")
        if not (isinstance(title, str) and 4 <= len(title) <= 30):
            errors.append(err("O031", f"{loc}.title must be a string 4-30 chars",
                              length=char_len(title)))

        rq = sec.get("reader_question")
        if not (isinstance(rq, str) and 10 <= len(rq) <= 80):
            errors.append(err("O032", f"{loc}.reader_question must be a string 10-80 chars",
                              length=char_len(rq)))
        elif not rq.rstrip().endswith(("?", "？")):
            errors.append(err("O032", f"{loc}.reader_question must be phrased as a question ending with ? or ？",
                              got=rq))

        srole = sec.get("section_role")
        if srole not in SECTION_ROLE_VALUES:
            errors.append(err("O033", f"{loc}.section_role must be one of {sorted(SECTION_ROLE_VALUES)}",
                              got=srole))

        wb = sec.get("word_budget")
        if not (isinstance(wb, int) and not isinstance(wb, bool) and 200 <= wb <= 3000):
            errors.append(err("O034", f"{loc}.word_budget must be an int 200-3000", got=wb))

        lead = sec.get("lead")
        if not (isinstance(lead, str) and 30 <= len(lead) <= 150):
            errors.append(err("O035", f"{loc}.lead must be a string 30-150 chars",
                              length=char_len(lead)))

        # Blocks (O036, O040-O044)
        blocks = sec.get("blocks")
        if not (isinstance(blocks, list) and 1 <= len(blocks) <= 10):
            errors.append(err("O036", f"{loc}.blocks must have length 1-10"))
            blocks = []

        # Build evidence_subset set first (needed by O044, O055)
        ev_subset = sec.get("evidence_subset")
        ev_subset_set: set[str] = set()
        if not (isinstance(ev_subset, list) and len(ev_subset) >= 1):
            errors.append(err("O038", f"{loc}.evidence_subset must be a non-empty array"))
        else:
            for ec in ev_subset:
                if not (isinstance(ec, str) and CLAIM_ID_RE.match(ec)):
                    errors.append(err("O038",
                                      f"{loc}.evidence_subset has invalid claim_id",
                                      got=ec))
                else:
                    if ec in ev_subset_set:
                        errors.append(err("O039",
                                          f"{loc}.evidence_subset has duplicate claim_id",
                                          got=ec))
                    ev_subset_set.add(ec)

        section_evidence_subset_by_id[sid] = ev_subset_set
        section_contract_refs: set[str] = set()
        seen_block_ids: set[str] = set()

        for bi, block in enumerate(blocks):
            bloc = f"{loc}.blocks[{bi}]"
            if not isinstance(block, dict):
                errors.append(err("O040", f"{bloc} must be an object"))
                continue

            bid = block.get("id")
            if not (isinstance(bid, str) and re.match(r"^b\d+$", bid)):
                errors.append(err("O040", f"{bloc}.id must match ^b\\d+$", got=bid))
            elif bid in seen_block_ids:
                errors.append(err("O040", f"{bloc}.id duplicates another block id", got=bid))
            else:
                seen_block_ids.add(bid)

            level = block.get("level")
            if not (isinstance(level, int) and not isinstance(level, bool) and 3 <= level <= 4):
                errors.append(err("O040", f"{bloc}.level must be integer 3 or 4", got=level))

            heading = block.get("heading")
            if not (isinstance(heading, str) and 4 <= len(heading) <= 80):
                errors.append(err("O040", f"{bloc}.heading must be 4-80 chars",
                                  length=char_len(heading)))

            thesis = block.get("thesis")
            if not (isinstance(thesis, str) and 10 <= len(thesis) <= 160):
                errors.append(err("O040", f"{bloc}.thesis must be 10-160 chars",
                                  length=char_len(thesis)))

            erefs = block.get("evidence_refs")
            if not (isinstance(erefs, list) and 1 <= len(erefs) <= 10):
                errors.append(err("O041", f"{bloc}.evidence_refs must have length 1-10"))
                continue
            for ei, eref in enumerate(erefs):
                erloc = f"{bloc}.evidence_refs[{ei}]"
                if not isinstance(eref, dict):
                    errors.append(err("O042", f"{erloc} must be an object"))
                    continue
                cid = eref.get("claim_id")
                if not (isinstance(cid, str) and CLAIM_ID_RE.match(cid)):
                    errors.append(err("O042", f"{erloc}.claim_id must match ^d\\d+\\.c\\d+$",
                                      got=cid))
                else:
                    section_contract_refs.add(cid)
                role = eref.get("role")
                if role not in NARRATIVE_ROLE_VALUES:
                    errors.append(err("O043",
                                      f"{erloc}.role must be one of {sorted(NARRATIVE_ROLE_VALUES)}",
                                      got=role))
                else:
                    narrative_roles_used.add(role)
                # O044 — claim_id must be in section.evidence_subset
                if isinstance(cid, str) and cid not in ev_subset_set:
                    errors.append(err("O044",
                                      f"{erloc}.claim_id ({cid!r}) not in {loc}.evidence_subset"))

            wc_refs = block.get("writing_context_refs", [])
            if wc_refs is not None and not (isinstance(wc_refs, list)
                                            and all(isinstance(x, str) and re.match(r"^d\d+\.w\d+$", x) for x in wc_refs)):
                errors.append(err("O044", f"{bloc}.writing_context_refs must be an array of dN.wM ids", got=wc_refs))

        # Visuals (O050-O057, O037)
        visuals = sec.get("visuals")
        if not (isinstance(visuals, list) and 0 <= len(visuals) <= 3):
            errors.append(err("O037", f"{loc}.visuals must have length 0-3"))
            visuals = []

        for vi, vis in enumerate(visuals):
            vloc = f"{loc}.visuals[{vi}]"
            if not isinstance(vis, dict):
                errors.append(err("O050", f"{vloc} must be an object"))
                continue
            pos = vis.get("position")
            if pos not in VISUAL_POSITION_VALUES:
                errors.append(err("O050",
                                  f"{vloc}.position must be one of {sorted(VISUAL_POSITION_VALUES)}",
                                  got=pos))
            form = vis.get("form")
            if form not in VISUAL_FORM_VALUES:
                errors.append(err("O051",
                                  f"{vloc}.form must be one of {sorted(VISUAL_FORM_VALUES)}",
                                  got=form))
            render = vis.get("render")
            if render not in VISUAL_RENDER_VALUES:
                errors.append(err("O056",
                                  f"{vloc}.render must be one of {sorted(VISUAL_RENDER_VALUES)}",
                                  got=render))
            elif form in FORM_TO_RENDER and render != FORM_TO_RENDER[form]:
                errors.append(err("O056",
                                  f"{vloc}.render must be {FORM_TO_RENDER[form]!r} for form {form!r}",
                                  got=render))
            information_type = vis.get("information_type")
            if information_type not in VISUAL_INFORMATION_TYPE_VALUES:
                errors.append(err("O057",
                                  f"{vloc}.information_type must be one of {sorted(VISUAL_INFORMATION_TYPE_VALUES)}",
                                  got=information_type))
            elif form in FORM_TO_INFORMATION_TYPES and information_type not in FORM_TO_INFORMATION_TYPES[form]:
                errors.append(err("O057",
                                  f"{vloc}.information_type is not compatible with form {form!r}",
                                  got=information_type,
                                  allowed=sorted(FORM_TO_INFORMATION_TYPES[form])))
            data_refs = vis.get("data_refs")
            min_refs = 0 if form in FORMS_ALLOWING_EMPTY_DATA_REFS else 1
            if not (isinstance(data_refs, list) and len(data_refs) >= min_refs):
                if min_refs == 0:
                    errors.append(err("O052", f"{vloc}.data_refs must be an array"))
                else:
                    errors.append(err("O052", f"{vloc}.data_refs must be a non-empty array"))
                data_refs = []
            for di, dr in enumerate(data_refs):
                if not (isinstance(dr, str) and CLAIM_ID_RE.match(dr)):
                    errors.append(err("O052",
                                      f"{vloc}.data_refs[{di}] must match ^d\\d+\\.c\\d+$",
                                      got=dr))
                else:
                    section_contract_refs.add(dr)
                    # O055 — data_ref claim must be in section.evidence_subset
                    if dr not in ev_subset_set:
                        errors.append(err("O055",
                                          f"{vloc}.data_refs[{di}] ({dr!r}) not in {loc}.evidence_subset"))
            caption = vis.get("caption")
            if not (isinstance(caption, str) and 5 <= len(caption) <= 50):
                errors.append(err("O053", f"{vloc}.caption must be 5-50 chars",
                                  length=char_len(caption)))
            rw = vis.get("replaces_words")
            if not (isinstance(rw, int) and not isinstance(rw, bool) and rw >= 0):
                errors.append(err("O054", f"{vloc}.replaces_words must be a non-negative int",
                                  got=rw))
            purpose = vis.get("purpose")
            if not (isinstance(purpose, str) and 5 <= len(purpose) <= 100):
                errors.append(err("O057",
                                  f"{vloc}.purpose must be 5-100 chars",
                                  length=char_len(purpose)))
            prompt_hint = vis.get("prompt_hint")
            if prompt_hint is not None and not (isinstance(prompt_hint, str) and 5 <= len(prompt_hint) <= 200):
                errors.append(err("O057",
                                  f"{vloc}.prompt_hint must be null or 5-200 chars",
                                  length=char_len(prompt_hint)))
            image_ref = vis.get("image_ref")
            if image_ref is not None and not (isinstance(image_ref, str) and image_ref.strip()):
                errors.append(err("O057",
                                  f"{vloc}.image_ref must be null or a non-empty string",
                                  got=image_ref))
            if form == "source-image" and not (isinstance(image_ref, str) and image_ref.strip()):
                errors.append(err("O057",
                                  f"{vloc}.image_ref is required for source-image"))
            # collect for visual_inventory cross-check
            if isinstance(form, str):
                section_visuals_flat.append((sid, form))
                visual_forms_used.add(form)

        # O045 — evidence_subset must be exactly the claims promised by
        # blocks[].evidence_refs and visuals[].data_refs. Extra "just in
        # case" claims make the writer boundary leaky; missing claims make the
        # outline impossible to execute.
        if ev_subset_set != section_contract_refs:
            errors.append(err("O045",
                              f"{loc}.evidence_subset must exactly equal blocks evidence_refs ∪ visuals data_refs",
                              extra_in_evidence_subset=sorted(ev_subset_set - section_contract_refs),
                              missing_from_evidence_subset=sorted(section_contract_refs - ev_subset_set)))
        section_claim_usage_by_id[sid] = section_contract_refs

        # Transitions are optional legacy hints. New outlines should omit
        # them; stitcher handles seams after all sections are written.
        trans = sec.get("transitions")
        if trans is None:
            trans = {}
        if not isinstance(trans, dict):
            errors.append(err("O060", f"{loc}.transitions must be an object"))
        else:
            from_prev = trans.get("from_prev")
            to_next = trans.get("to_next")
            if not (from_prev is None or (isinstance(from_prev, str) and 15 <= len(from_prev) <= 80)):
                errors.append(err("O060",
                                  f"{loc}.transitions.from_prev must be null or 15-80 chars",
                                  length=char_len(from_prev)))
            if not (to_next is None or (isinstance(to_next, str) and 15 <= len(to_next) <= 80)):
                errors.append(err("O061",
                                  f"{loc}.transitions.to_next must be null or 15-80 chars",
                                  length=char_len(to_next)))

    # ── Visual inventory (O070-O073) ───────────────────────────────────────
    vinv = data.get("visual_inventory")
    if not isinstance(vinv, list):
        errors.append(err("O070", "visual_inventory must be an array"))
    else:
        inv_flat: list[tuple[str, str]] = []
        for ii, item in enumerate(vinv):
            iloc = f"visual_inventory[{ii}]"
            if not isinstance(item, dict):
                errors.append(err("O070", f"{iloc} must be an object"))
                continue
            isid = item.get("section")
            if isid not in section_id_set:
                errors.append(err("O070",
                                  f"{iloc}.section ({isid!r}) not found in sections"))
            iform = item.get("form")
            if iform not in VISUAL_FORM_VALUES:
                errors.append(err("O071",
                                  f"{iloc}.form must be one of {sorted(VISUAL_FORM_VALUES)}",
                                  got=iform))
            ipurp = item.get("purpose")
            if not (isinstance(ipurp, str) and 5 <= len(ipurp) <= 30):
                errors.append(err("O072",
                                  f"{iloc}.purpose must be 5-30 chars",
                                  length=char_len(ipurp)))
            if isinstance(isid, str) and isinstance(iform, str):
                inv_flat.append((isid, iform))

        # O073 — visual_inventory and sections[].visuals must be consistent
        if Counter(inv_flat) != Counter(section_visuals_flat):
            inv_only = Counter(inv_flat) - Counter(section_visuals_flat)
            sec_only = Counter(section_visuals_flat) - Counter(inv_flat)
            errors.append(err("O073",
                              "visual_inventory does not match sections[].visuals (flat)",
                              in_inventory_only=list(inv_only.elements()),
                              in_sections_only=list(sec_only.elements())))

    # ── Claim routing table (O080-O094) ────────────────────────────────────
    routing = data.get("claim_routing_table")
    routing_keys: set[str] = set()
    if not isinstance(routing, dict):
        errors.append(err("O080", "claim_routing_table must be an object"))
    else:
        primary_count: Counter = Counter()
        for cid, entry in routing.items():
            if not (isinstance(cid, str) and CLAIM_ID_RE.match(cid)):
                errors.append(err("O080", f"routing key invalid claim_id", got=cid))
                continue
            routing_keys.add(cid)

            if not isinstance(entry, dict):
                errors.append(err("O080", f"claim_routing_table[{cid!r}] must be an object"))
                continue

            primary = entry.get("primary")
            if primary not in section_id_set:
                errors.append(err("O081",
                                  f"claim_routing_table[{cid!r}].primary not found in sections",
                                  got=primary))
            else:
                primary_count[cid] += 1

            secondary = entry.get("secondary")
            if not isinstance(secondary, list):
                errors.append(err("O082",
                                  f"claim_routing_table[{cid!r}].secondary must be an array"))
                continue
            seen_secondary_sections: set[str] = set()
            for si, sec_entry in enumerate(secondary):
                if not isinstance(sec_entry, dict):
                    errors.append(err("O082",
                                      f"claim_routing_table[{cid!r}].secondary[{si}] must be an object"))
                    continue
                ssec = sec_entry.get("section")
                if ssec not in section_id_set:
                    errors.append(err("O082",
                                      f"claim_routing_table[{cid!r}].secondary[{si}].section not found",
                                      got=ssec))
                else:
                    if ssec == primary:
                        errors.append(err("O086",
                                          f"claim_routing_table[{cid!r}].secondary[{si}].section duplicates primary section",
                                          section=ssec))
                    if ssec in seen_secondary_sections:
                        errors.append(err("O086",
                                          f"claim_routing_table[{cid!r}] has duplicate secondary section",
                                          section=ssec))
                    seen_secondary_sections.add(ssec)
                srole = sec_entry.get("role")
                if srole not in NARRATIVE_ROLE_VALUES:
                    errors.append(err("O083",
                                      f"claim_routing_table[{cid!r}].secondary[{si}].role must be in "
                                      f"{sorted(NARRATIVE_ROLE_VALUES)}",
                                      got=srole))
                elif srole not in {"supporting_context", "reference_only"}:
                    errors.append(err("O085",
                                      f"claim_routing_table[{cid!r}].secondary[{si}].role must be supporting_context or reference_only",
                                      got=srole))
        # O084 — at most 1 primary per claim. The dict structure already enforces
        # at-most-one entry per claim; this is a structural guarantee. Check
        # that each entry has exactly one primary field (covered by O081 on
        # missing/wrong values).

    # ── Cross-structure (O090-O094) ────────────────────────────────────────
    # Collect all claim_ids referenced by sections
    all_evidence_subset_claims: set[str] = set()
    for ev_set in section_evidence_subset_by_id.values():
        all_evidence_subset_claims |= ev_set

    # O090 — every claim referenced in sections must appear in routing table
    missing_in_routing = all_evidence_subset_claims - routing_keys
    if missing_in_routing:
        errors.append(err("O090",
                          "claims referenced in sections.evidence_subset but missing in claim_routing_table",
                          claim_ids=sorted(missing_in_routing)))

    # O091 — for each routing entry: primary section must contain the claim in evidence_subset
    # O092 — for each secondary entry: the section must contain the claim in evidence_subset
    if isinstance(routing, dict):
        for cid, entry in routing.items():
            if not (isinstance(cid, str) and isinstance(entry, dict)):
                continue
            primary = entry.get("primary")
            if isinstance(primary, str) and primary in section_evidence_subset_by_id:
                if cid not in section_evidence_subset_by_id[primary]:
                    errors.append(err("O091",
                                      f"claim {cid!r} routed primary→{primary} but not in that section's evidence_subset"))
                if cid not in section_claim_usage_by_id.get(primary, set()):
                    errors.append(err("O093",
                                      f"claim {cid!r} routed primary→{primary} but not used in that section's blocks or visuals"))
            secondary = entry.get("secondary") or []
            if isinstance(secondary, list):
                for sec_entry in secondary:
                    if not isinstance(sec_entry, dict):
                        continue
                    ssec = sec_entry.get("section")
                    if isinstance(ssec, str) and ssec in section_evidence_subset_by_id:
                        if cid not in section_evidence_subset_by_id[ssec]:
                            errors.append(err("O092",
                                              f"claim {cid!r} routed secondary→{ssec} but not in that section's evidence_subset"))
                        if cid not in section_claim_usage_by_id.get(ssec, set()):
                            errors.append(err("O093",
                                              f"claim {cid!r} routed secondary→{ssec} but not used in that section's blocks or visuals"))

    # O095 — L0 abstract visual data_refs must be routed through sections
    missing_abstract_refs = abstract_visual_refs - all_evidence_subset_claims
    if missing_abstract_refs:
        errors.append(err("O095",
                          "L0_draft.abstract_visual.data_refs must appear in section evidence_subset routing",
                          claim_ids=sorted(missing_abstract_refs)))

    # O094 — visual density soft constraint (warning, not error)
    total_word_budget = 0
    total_visuals = len(section_visuals_flat)
    for sec in sections:
        if isinstance(sec, dict):
            wb = sec.get("word_budget")
            if isinstance(wb, int) and not isinstance(wb, bool):
                total_word_budget += wb
    expected_visuals_floor = max(1, total_word_budget // 1000)
    if total_visuals + 1 < expected_visuals_floor:
        warnings.append(warn("O094",
                             f"visual density below threshold: {total_visuals} visuals "
                             f"for {total_word_budget} words "
                             f"(expected ≥{expected_visuals_floor - 1})",
                             total_visuals=total_visuals,
                             total_word_budget=total_word_budget))

    # ── Scan summary (O100-O104) ───────────────────────────────────────────
    scan = data.get("scan_summary")
    if not isinstance(scan, dict):
        errors.append(err("O100", "scan_summary must be an object"))
    else:
        totals = scan.get("totals")
        if not isinstance(totals, dict):
            errors.append(err("O100", "scan_summary.totals must be an object"))
        else:
            tcl = totals.get("claims")
            if not (isinstance(tcl, int) and not isinstance(tcl, bool) and tcl >= 0):
                errors.append(err("O100", "scan_summary.totals.claims must be a non-negative int",
                                  got=tcl))
            pr = totals.get("primary_ratio")
            if not (isinstance(pr, (int, float)) and not isinstance(pr, bool) and 0 <= pr <= 1):
                errors.append(err("O101",
                                  "scan_summary.totals.primary_ratio must be in [0, 1]",
                                  got=pr))

        clusters = scan.get("topic_clusters") or []
        if isinstance(clusters, list):
            for ci, cl in enumerate(clusters):
                if not isinstance(cl, dict):
                    continue
                pmix = cl.get("polarity_mix")
                count = cl.get("claim_count")
                if isinstance(pmix, dict) and isinstance(count, int):
                    pmix_sum = sum(v for v in pmix.values()
                                   if isinstance(v, int) and not isinstance(v, bool))
                    if pmix_sum != count:
                        errors.append(err("O102",
                                          f"scan_summary.topic_clusters[{ci}].polarity_mix sum "
                                          f"({pmix_sum}) != claim_count ({count})"))

        conflicts = scan.get("conflicts") or []
        if isinstance(conflicts, list):
            for ci, cf in enumerate(conflicts):
                if isinstance(cf, dict):
                    sev = cf.get("severity")
                    if sev not in SEVERITY_VALUES:
                        errors.append(err("O103",
                                          f"scan_summary.conflicts[{ci}].severity must be in "
                                          f"{sorted(SEVERITY_VALUES)}",
                                          got=sev))
            if conflicts and not ({"counter"} & narrative_roles_used or "evidence-conflict-callout" in visual_forms_used):
                warnings.append(warn("W_ARTICLE_001",
                                     "scan_summary.conflicts is non-empty, but no counter role or evidence-conflict-callout is routed"))

        gaps = scan.get("gaps") or []
        if isinstance(gaps, list) and gaps and "evidence-gap-callout" not in visual_forms_used:
            warnings.append(warn("W_ARTICLE_002",
                                 "scan_summary.gaps is non-empty, but no evidence-gap-callout is routed"))

        rts = scan.get("reader_task_signal")
        if isinstance(rts, dict):
            total = 0.0
            for k, v in rts.items():
                if not (isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1):
                    errors.append(err("O104",
                                      f"scan_summary.reader_task_signal[{k!r}] must be in [0, 1]",
                                      got=v))
                else:
                    total += v
            if abs(total - 1.0) > 0.05:
                errors.append(err("O104",
                                  f"scan_summary.reader_task_signal values must sum to ~1.0 (±0.05)",
                                  sum=total))

    return (errors, warnings)


# ── v2.0 content-unit outline validation (U001-U104) ─────────────────────
def validate_outline_v2(data) -> tuple[list, list]:
    """Return (errors, warnings) for a v2.0 content-unit outline."""
    errors: list = []
    warnings: list = []

    if not isinstance(data, dict):
        return ([err("STRUCT", "Root must be a JSON object")], [])

    if data.get("schema_version") != CONTENT_UNIT_SCHEMA_VERSION:
        errors.append(err(
            "U001",
            f"schema_version must be '{CONTENT_UNIT_SCHEMA_VERSION}'",
            got=data.get("schema_version"),
        ))
    if "sections" in data:
        errors.append(err("U008", "v2 outline must not contain legacy sections"))

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
    if not (isinstance(arc, str) and 40 <= len(arc) <= 120):
        errors.append(err("U006", "global_arc must be a string 40-120 chars", length=char_len(arc)))

    # Organization decision is intentionally separate from paradigm. Nothing
    # here maps one enum to the other.
    organization = data.get("organization_decision")
    primary_unit_type = None
    declared_supporting_types: set[str] = set()
    opening_summary = None
    numbered_headings = False
    if not isinstance(organization, dict):
        errors.append(err("U010", "organization_decision must be an object"))
    else:
        reader_task = organization.get("reader_task")
        if not (isinstance(reader_task, str) and 10 <= len(reader_task) <= 200):
            errors.append(err("U010", "organization_decision.reader_task must be 10-200 chars", length=char_len(reader_task)))

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
        if isinstance(organization.get("numbered_headings"), bool):
            numbered_headings = organization["numbered_headings"]

        evidence_fit = organization.get("evidence_fit")
        if not (isinstance(evidence_fit, str) and 20 <= len(evidence_fit) <= 300):
            errors.append(err("U015", "organization_decision.evidence_fit must be 20-300 chars", length=char_len(evidence_fit)))

        preference = organization.get("preference")
        if not isinstance(preference, dict):
            errors.append(err("U016", "organization_decision.preference must be an object"))
        else:
            requested = preference.get("requested_type")
            custom_type = preference.get("custom_type")
            strength = preference.get("strength")
            resolution = preference.get("resolution")
            adaptation_reason = preference.get("adaptation_reason")

            if strength not in PREFERENCE_STRENGTH_VALUES:
                errors.append(err("U016", f"preference.strength must be one of {sorted(PREFERENCE_STRENGTH_VALUES)}", got=strength))
            if resolution not in PREFERENCE_RESOLUTION_VALUES:
                errors.append(err("U017", f"preference.resolution must be one of {sorted(PREFERENCE_RESOLUTION_VALUES)}", got=resolution))

            if strength == "auto":
                if requested is not None or custom_type is not None:
                    errors.append(err("U018", "auto preference requires requested_type and custom_type to be null", requested_type=requested, custom_type=custom_type))
                if resolution != "auto_selected":
                    errors.append(err("U017", "auto preference requires resolution='auto_selected'", got=resolution))
                if adaptation_reason is not None:
                    errors.append(err("U019", "auto preference requires adaptation_reason=null", got=adaptation_reason))
            elif strength in {"required", "preferred"}:
                if requested not in CONTENT_UNIT_TYPE_VALUES:
                    errors.append(err("U018", f"{strength} preference requires a valid requested_type", got=requested))
                if requested == "custom":
                    if not (isinstance(custom_type, str) and custom_type.strip()):
                        errors.append(err("U018", "requested_type='custom' requires non-empty custom_type"))
                elif custom_type is not None:
                    errors.append(err("U018", "custom_type must be null unless requested_type='custom'", got=custom_type))

                if strength == "required":
                    if resolution != "required_honored":
                        errors.append(err("U017", "required preference requires resolution='required_honored'", got=resolution))
                    if requested is not None and primary_unit_type != requested:
                        errors.append(err("U018", "required preference must equal primary_unit_type", requested_type=requested, primary_unit_type=primary_unit_type))
                    if adaptation_reason is not None:
                        errors.append(err("U019", "required preference requires adaptation_reason=null", got=adaptation_reason))
                else:
                    if primary_unit_type == requested:
                        if resolution != "preferred_honored":
                            errors.append(err("U017", "honored preferred preference requires resolution='preferred_honored'", got=resolution))
                        if adaptation_reason is not None:
                            errors.append(err("U019", "preferred_honored requires adaptation_reason=null", got=adaptation_reason))
                    else:
                        if resolution != "preferred_adapted":
                            errors.append(err("U017", "adapted preferred preference requires resolution='preferred_adapted'", got=resolution))
                        if not (isinstance(adaptation_reason, str) and 20 <= len(adaptation_reason) <= 300):
                            errors.append(err("U019", "preferred_adapted requires adaptation_reason of 20-300 chars", length=char_len(adaptation_reason)))

    # L0 is optional in v2 and its presence is controlled explicitly.
    abstract_visual_refs: set[str] = set()
    l0 = data.get("L0_draft")
    if opening_summary == "none":
        if l0 is not None:
            errors.append(err("U020", "L0_draft must be null when opening_summary='none'"))
    elif opening_summary in {"findings", "recommendation"}:
        if not isinstance(l0, dict):
            errors.append(err("U020", "L0_draft must be an object when an opening summary is requested"))
        else:
            headline = l0.get("headline")
            if not (isinstance(headline, str) and 8 <= len(headline) <= 30):
                errors.append(err("U020", "L0_draft.headline must be 8-30 chars", length=char_len(headline)))
            findings = l0.get("key_findings")
            if not (isinstance(findings, list) and 3 <= len(findings) <= 5):
                errors.append(err("U021", "L0_draft.key_findings must have length 3-5"))
            else:
                for i, finding in enumerate(findings):
                    if not (isinstance(finding, str) and 20 <= len(finding) <= 60):
                        errors.append(err("U022", f"L0_draft.key_findings[{i}] must be 20-60 chars", length=char_len(finding)))
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
                            else:
                                abstract_visual_refs.add(claim_id)

    style = data.get("style_contract")
    if not isinstance(style, dict):
        errors.append(err("U030", "style_contract must be an object"))
    else:
        language = style.get("language")
        if not (isinstance(language, str) and language.strip()):
            errors.append(err("U034", "style_contract.language must be a non-empty BCP 47 label", got=language))
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
    evidence_subset_by_unit: dict[str, set[str]] = {}
    claim_roles_by_unit: dict[str, dict[str, set[str]]] = {}
    actual_supporting_types: set[str] = set()
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
        elif role == "supporting" and unit_type in CONTENT_UNIT_TYPE_VALUES:
            actual_supporting_types.add(unit_type)

        title = unit.get("title")
        if not (isinstance(title, str) and 2 <= len(title) <= 80):
            errors.append(err("U044", f"{loc}.title must be 2-80 chars", length=char_len(title)))
        reader_task = unit.get("reader_task")
        if not (isinstance(reader_task, str) and 10 <= len(reader_task) <= 160):
            errors.append(err("U045", f"{loc}.reader_task must be 10-160 chars", length=char_len(reader_task)))
        word_budget = unit.get("word_budget")
        if not (isinstance(word_budget, int) and not isinstance(word_budget, bool) and 50 <= word_budget <= 3000):
            errors.append(err("U046", f"{loc}.word_budget must be an int 50-3000", got=word_budget))
        else:
            total_word_budget += word_budget
        lead = unit.get("lead")
        if lead is not None and not (isinstance(lead, str) and 20 <= len(lead) <= 180):
            errors.append(err("U047", f"{loc}.lead must be null or 20-180 chars", length=char_len(lead)))

        render_contract = unit.get("render_contract")
        if not isinstance(render_contract, dict):
            errors.append(err("U050", f"{loc}.render_contract must be an object"))
        else:
            mode = render_contract.get("mode")
            if mode not in CONTENT_UNIT_RENDER_MODE_VALUES:
                errors.append(err("U050", f"{loc}.render_contract.mode must be one of {sorted(CONTENT_UNIT_RENDER_MODE_VALUES)}", got=mode))
            if not isinstance(render_contract.get("show_heading"), bool):
                errors.append(err("U051", f"{loc}.render_contract.show_heading must be boolean", got=render_contract.get("show_heading")))
            elif numbered_headings and render_contract.get("show_heading"):
                if not (isinstance(title, str) and NUMBERED_TITLE_RE.match(title)):
                    errors.append(err(
                        "U075",
                        f"{loc}.title must carry a stable number when numbered_headings=true",
                        got=title,
                    ))
            render_schema = render_contract.get("schema")
            if not (isinstance(render_schema, list) and len(render_schema) <= 20):
                errors.append(err("U052", f"{loc}.render_contract.schema must have length 0-20"))
            else:
                valid_fields = [field for field in render_schema if isinstance(field, str) and 1 <= len(field) <= 80]
                if len(valid_fields) != len(render_schema):
                    errors.append(err("U052", f"{loc}.render_contract.schema entries must be strings 1-80 chars"))
                if len(set(valid_fields)) != len(valid_fields):
                    errors.append(err("U052", f"{loc}.render_contract.schema entries must be unique"))
            instructions = render_contract.get("instructions")
            if not (isinstance(instructions, str) and 10 <= len(instructions) <= 500):
                errors.append(err("U053", f"{loc}.render_contract.instructions must be 10-500 chars", length=char_len(instructions)))

        elements = unit.get("elements")
        if not (isinstance(elements, list) and 1 <= len(elements) <= 20):
            errors.append(err("U060", f"{loc}.elements must have length 1-20"))
            elements = []
        seen_element_ids: set[str] = set()
        contract_claims: set[str] = set()
        contract_contexts: set[str] = set()
        roles_for_claim: dict[str, set[str]] = {}

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
            if not (isinstance(label, str) and 2 <= len(label) <= 100):
                errors.append(err("U062", f"{eloc}.label must be 2-100 chars", length=char_len(label)))
            purpose = element.get("purpose")
            if not (isinstance(purpose, str) and 10 <= len(purpose) <= 240):
                errors.append(err("U063", f"{eloc}.purpose must be 10-240 chars", length=char_len(purpose)))

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
                elif isinstance(claim_id, str) and CLAIM_ID_RE.match(claim_id):
                    roles_for_claim.setdefault(claim_id, set()).add(evidence_role)

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
        if subset_set != contract_claims:
            errors.append(err(
                "U071",
                f"{loc}.evidence_subset must exactly equal elements evidence_refs",
                extra_in_evidence_subset=sorted(subset_set - contract_claims),
                missing_from_evidence_subset=sorted(contract_claims - subset_set),
            ))
        if not subset_set and not contract_contexts:
            errors.append(err("U070", f"{loc} must route at least one claim or writing context"))
        evidence_subset_by_unit[unit_id] = subset_set
        claim_roles_by_unit[unit_id] = roles_for_claim

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
    if declared_supporting_types != actual_supporting_types:
        errors.append(err("U073", "organization_decision.supporting_unit_types must exactly match supporting content units", declared=sorted(declared_supporting_types), actual=sorted(actual_supporting_types)))

    routing = data.get("claim_routing_table")
    all_claims: set[str] = set().union(*evidence_subset_by_unit.values()) if evidence_subset_by_unit else set()
    routing_keys: set[str] = set()
    if not isinstance(routing, dict):
        errors.append(err("U080", "claim_routing_table must be an object"))
        routing = {}
    else:
        for claim_id, entry in routing.items():
            if not (isinstance(claim_id, str) and CLAIM_ID_RE.match(claim_id)):
                errors.append(err("U080", "claim_routing_table key is invalid", got=claim_id))
                continue
            routing_keys.add(claim_id)
            if not isinstance(entry, dict):
                errors.append(err("U081", f"claim_routing_table[{claim_id!r}] must be an object"))
                continue
            primary = entry.get("primary")
            if primary not in unit_id_set:
                errors.append(err("U081", f"claim_routing_table[{claim_id!r}].primary is not a content unit", got=primary))
            elif claim_id not in evidence_subset_by_unit.get(primary, set()):
                errors.append(err("U082", f"claim {claim_id!r} is routed primary to {primary!r} but is not used there"))

            secondary = entry.get("secondary")
            if not isinstance(secondary, list):
                errors.append(err("U083", f"claim_routing_table[{claim_id!r}].secondary must be an array"))
                secondary = []
            seen_secondary: set[str] = set()
            routed_units = {primary} if primary in unit_id_set else set()
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
                    routed_units.add(secondary_unit)
                    if claim_id not in evidence_subset_by_unit.get(secondary_unit, set()):
                        errors.append(err("U085", f"claim {claim_id!r} is routed secondary to {secondary_unit!r} but is not used there"))
                if secondary_role not in {"supporting_context", "reference_only"}:
                    errors.append(err("U086", f"{sloc}.role must be supporting_context or reference_only", got=secondary_role))
                elif secondary_unit in claim_roles_by_unit and secondary_role not in claim_roles_by_unit[secondary_unit].get(claim_id, set()):
                    errors.append(err("U086", f"{sloc}.role does not match the unit evidence_ref role", got=secondary_role))

            actual_usage_units = {
                unit_id for unit_id, claims in evidence_subset_by_unit.items()
                if claim_id in claims
            }
            if routed_units != actual_usage_units:
                errors.append(err("U087", f"claim {claim_id!r} routing must exactly cover units that use it", routed=sorted(routed_units), actual=sorted(actual_usage_units)))

    if routing_keys != all_claims:
        errors.append(err(
            "U088",
            "claim_routing_table keys must exactly cover content unit evidence subsets",
            missing_in_routing=sorted(all_claims - routing_keys),
            unused_routing_keys=sorted(routing_keys - all_claims),
        ))
    missing_abstract_refs = abstract_visual_refs - all_claims
    if missing_abstract_refs:
        errors.append(err("U089", "L0 abstract visual refs must be routed through content units", claim_ids=sorted(missing_abstract_refs)))

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
                    continue
                polarity_mix = cluster.get("polarity_mix")
                claim_count = cluster.get("claim_count")
                if isinstance(polarity_mix, dict) and isinstance(claim_count, int):
                    polarity_total = sum(value for value in polarity_mix.values() if isinstance(value, int) and not isinstance(value, bool))
                    if polarity_total != claim_count:
                        errors.append(err("U102", f"scan_summary.topic_clusters[{cluster_index}].polarity_mix sum must equal claim_count"))

        conflicts = scan.get("conflicts", [])
        if not isinstance(conflicts, list):
            errors.append(err("U103", "scan_summary.conflicts must be an array"))
        else:
            for conflict_index, conflict in enumerate(conflicts):
                if isinstance(conflict, dict) and conflict.get("severity") not in SEVERITY_VALUES:
                    errors.append(err("U103", f"scan_summary.conflicts[{conflict_index}].severity must be one of {sorted(SEVERITY_VALUES)}", got=conflict.get("severity")))

        for field in ("key_entities", "timeline_density", "gaps"):
            if not isinstance(scan.get(field, []), list):
                errors.append(err("U103", f"scan_summary.{field} must be an array"))

        signal = scan.get("reader_task_signal")
        if not isinstance(signal, dict):
            errors.append(err("U104", "scan_summary.reader_task_signal must be an object"))
        else:
            if set(signal) != PARADIGM_VALUES:
                errors.append(err("U104", "reader_task_signal must contain exactly the six paradigm keys", missing=sorted(PARADIGM_VALUES - set(signal)), extra=sorted(set(signal) - PARADIGM_VALUES)))
            signal_total = 0.0
            for key, value in signal.items():
                if not (isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1):
                    errors.append(err("U104", f"reader_task_signal[{key!r}] must be in [0, 1]", got=value))
                else:
                    signal_total += value
            if abs(signal_total - 1.0) > 0.05:
                errors.append(err("U104", "reader_task_signal values must sum to ~1.0 (±0.05)", sum=signal_total))

    return errors, warnings


def validate_format_contract(outline_data, format_data) -> list:
    """Cross-check a v2 outline against the user-confirmed format contract."""
    if not isinstance(outline_data, dict) or outline_data.get("schema_version") != CONTENT_UNIT_SCHEMA_VERSION:
        return []

    errors: list = []
    if not isinstance(format_data, dict):
        return [err("U110", "format root must be a JSON object")]
    if format_data.get("confirmed_by_user") is not True:
        errors.append(err("U110", "format.confirmed_by_user must be true", got=format_data.get("confirmed_by_user")))

    format_preference = format_data.get("structure_preference")
    organization = outline_data.get("organization_decision")
    outline_preference = organization.get("preference") if isinstance(organization, dict) else None
    if not isinstance(format_preference, dict):
        errors.append(err("U111", "format.structure_preference must be an object"))
        return errors
    if not isinstance(outline_preference, dict):
        # U016 already reports the malformed outline. Keep the cross-file error
        # explicit so a caller knows the confirmed preference was not copied.
        errors.append(err("U112", "organization_decision.preference must copy format.structure_preference"))
        return errors

    format_requested = format_preference.get("requested_type")
    format_custom = format_preference.get("custom_type")
    format_strength = format_preference.get("strength")
    if format_strength not in PREFERENCE_STRENGTH_VALUES:
        errors.append(err("U111", f"format.structure_preference.strength must be one of {sorted(PREFERENCE_STRENGTH_VALUES)}", got=format_strength))
    if format_strength == "auto":
        if format_requested is not None or format_custom is not None:
            errors.append(err("U111", "auto format preference requires requested_type and custom_type to be null", requested_type=format_requested, custom_type=format_custom))
    elif format_strength in {"required", "preferred"}:
        if format_requested not in CONTENT_UNIT_TYPE_VALUES:
            errors.append(err("U111", f"{format_strength} format preference requires a valid requested_type", got=format_requested))
        if format_requested == "custom":
            if not (isinstance(format_custom, str) and format_custom.strip()):
                errors.append(err("U111", "format requested_type='custom' requires non-empty custom_type"))
        elif format_custom is not None:
            errors.append(err("U111", "format custom_type must be null unless requested_type='custom'", got=format_custom))

    for field in ("requested_type", "custom_type", "strength"):
        if outline_preference.get(field) != format_preference.get(field):
            errors.append(err(
                "U112",
                f"organization_decision.preference.{field} must equal format.structure_preference.{field}",
                outline_value=outline_preference.get(field),
                format_value=format_preference.get(field),
            ))

    primary_unit_type = organization.get("primary_unit_type") if isinstance(organization, dict) else None
    if format_strength == "required" and primary_unit_type != format_requested:
        errors.append(err(
            "U113",
            "required format structure must equal organization_decision.primary_unit_type",
            required_type=format_requested,
            primary_unit_type=primary_unit_type,
        ))
    return errors


def validate_language_contract(outline_data, language) -> list:
    """Cross-check a v2 outline against the request-scoped language parameter."""
    if not isinstance(outline_data, dict) or outline_data.get("schema_version") != CONTENT_UNIT_SCHEMA_VERSION:
        return []

    errors: list = []
    if not (isinstance(language, str) and language.strip()):
        return [err("U114", "language must be a non-empty BCP 47 label", got=language)]

    style = outline_data.get("style_contract")
    outline_language = style.get("language") if isinstance(style, dict) else None
    if outline_language != language:
        errors.append(err(
            "U115",
            "style_contract.language must equal request language",
            outline_value=outline_language,
            language_value=language,
        ))
    return errors


def validate_outline(data) -> tuple[list, list]:
    """Dispatch outline validation by schema_version."""
    if not isinstance(data, dict):
        return ([err("STRUCT", "Root must be a JSON object")], [])
    schema_version = data.get("schema_version")
    if schema_version == LEGACY_SCHEMA_VERSION:
        return validate_outline_v1(data)
    if schema_version == CONTENT_UNIT_SCHEMA_VERSION:
        return validate_outline_v2(data)
    return ([err(
        "O001",
        f"schema_version must be one of {sorted(SUPPORTED_SCHEMA_VERSIONS)}",
        got=schema_version,
    )], [])


# ── evidence_subset.json validation (S001-S014 / U201-U214) ───────────────
def validate_subset_v1(subset_data, outline_data, evidence_index) -> list:
    """Validate a single evidence_subset.json. evidence_index is a dict
    mapping claim_id → original claim object from the d{N}.evidence.json
    files (used to verify S012). Pass an empty dict to skip S012/S013."""
    errors: list = []

    if not isinstance(subset_data, dict):
        return [err("STRUCT", "Root must be a JSON object")]

    sv = subset_data.get("schema_version")
    if sv != LEGACY_SCHEMA_VERSION:
        errors.append(err("S001", f"schema_version must be '{LEGACY_SCHEMA_VERSION}'", got=sv))

    section_id = subset_data.get("section_id")
    if not (isinstance(section_id, str) and SECTION_ID_RE.match(section_id)):
        errors.append(err("S002", "section_id must match ^s\\d+$", got=section_id))
        return errors

    # Find the matching outline section
    outline_sections = []
    if isinstance(outline_data, dict):
        outline_sections = outline_data.get("sections") or []
    matching_section = None
    for s in outline_sections:
        if isinstance(s, dict) and s.get("id") == section_id:
            matching_section = s
            break
    if matching_section is None:
        errors.append(err("S003", f"section_id ({section_id!r}) not found in outline.sections"))
        return errors

    outline_subset = set(matching_section.get("evidence_subset") or [])

    claims = subset_data.get("claims")
    if not (isinstance(claims, list) and len(claims) >= 1):
        errors.append(err("S010", "claims must be a non-empty array"))
        return errors

    subset_claim_ids = {c.get("id") for c in claims if isinstance(c, dict)}
    # S010 — outline.evidence_subset == subset.claims[].id
    if subset_claim_ids != outline_subset:
        in_subset_only = subset_claim_ids - outline_subset
        in_outline_only = outline_subset - subset_claim_ids
        errors.append(err("S010",
                          "subset.claims[].id != outline.section.evidence_subset",
                          in_subset_only=sorted(x for x in in_subset_only if x),
                          in_outline_only=sorted(in_outline_only)))

    # Build set of source_ids referenced by subset claims
    referenced_source_ids: set[str] = set()
    routing = (outline_data.get("claim_routing_table") if isinstance(outline_data, dict) else None) or {}

    for ci, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        cid = claim.get("id")
        cloc = f"claims[{ci}]"

        # S013 — narrative_role enum
        nrole = claim.get("narrative_role")
        if nrole not in NARRATIVE_ROLE_VALUES:
            errors.append(err("S013",
                              f"{cloc}.narrative_role must be one of {sorted(NARRATIVE_ROLE_VALUES)}",
                              got=nrole))

        # S014 — narrative_role must match outline.claim_routing_table
        if isinstance(cid, str) and cid in routing:
            entry = routing[cid]
            if isinstance(entry, dict):
                allowed_roles: set[str] = set()
                if entry.get("primary") == section_id:
                    # primary section — narrative_role must be primary_support OR
                    # whatever role makes sense; per schema, primary entry doesn't
                    # carry a role field, so we accept primary_support / quantifier
                    # / counter / supporting_context (but reject reference_only).
                    # The conservative rule: in the primary section, narrative_role
                    # SHOULD be primary_support. Other roles in primary section
                    # are a soft signal of mis-routing.
                    allowed_roles = NARRATIVE_ROLE_VALUES - {"reference_only"}
                else:
                    secondary = entry.get("secondary") or []
                    for sec_entry in secondary:
                        if isinstance(sec_entry, dict) and sec_entry.get("section") == section_id:
                            r = sec_entry.get("role")
                            if isinstance(r, str):
                                allowed_roles.add(r)
                if allowed_roles and nrole not in allowed_roles:
                    errors.append(err("S014",
                                      f"{cloc}.narrative_role ({nrole!r}) doesn't match "
                                      f"claim_routing_table for section {section_id}",
                                      allowed=sorted(allowed_roles)))

        # S012 — text/kind/polarity/topic_tag/evidence must match evidence.json
        if isinstance(cid, str) and cid in evidence_index:
            ref = evidence_index[cid]
            for field in ("text", "kind", "polarity", "topic_tag"):
                if claim.get(field) != ref.get(field):
                    errors.append(err("S012",
                                      f"{cloc}.{field} differs from evidence.json source",
                                      claim_id=cid,
                                      subset_value=claim.get(field),
                                      evidence_value=ref.get(field)))
            # Compare evidence list (snippet, source_id, quote_type)
            sub_ev = claim.get("evidence") or []
            ref_ev = ref.get("evidence") or []
            if len(sub_ev) != len(ref_ev):
                errors.append(err("S012",
                                  f"{cloc}.evidence length differs from evidence.json",
                                  claim_id=cid,
                                  subset_count=len(sub_ev),
                                  evidence_count=len(ref_ev)))
            else:
                for ei, (s_e, r_e) in enumerate(zip(sub_ev, ref_ev)):
                    if not (isinstance(s_e, dict) and isinstance(r_e, dict)):
                        continue
                    for field in ("source_id", "snippet", "quote_type"):
                        if s_e.get(field) != r_e.get(field):
                            errors.append(err("S012",
                                              f"{cloc}.evidence[{ei}].{field} differs from evidence.json",
                                              claim_id=cid,
                                              subset_value=s_e.get(field),
                                              evidence_value=r_e.get(field)))

        # collect source_ids
        for e in (claim.get("evidence") or []):
            if isinstance(e, dict):
                esid = e.get("source_id")
                if isinstance(esid, str):
                    referenced_source_ids.add(esid)

    # S011 — sources cover all referenced source_ids
    sources = subset_data.get("sources") or []
    declared_source_ids = {s.get("id") for s in sources if isinstance(s, dict)}
    missing = referenced_source_ids - declared_source_ids
    if missing:
        errors.append(err("S011",
                          "sources[] does not cover all referenced source_ids",
                          missing=sorted(missing)))

    return errors


def validate_subset_v2(
    subset_data,
    outline_data,
    evidence_index=None,
    writing_context_index=None,
) -> list:
    """Validate one v2.0 content-unit evidence subset."""
    errors: list = []
    strict_claims = evidence_index is not None
    strict_contexts = writing_context_index is not None
    evidence_index = evidence_index or {}
    writing_context_index = writing_context_index or {}
    if not isinstance(subset_data, dict):
        return [err("STRUCT", "Root must be a JSON object")]

    if subset_data.get("schema_version") != CONTENT_UNIT_SCHEMA_VERSION:
        errors.append(err("U201", f"schema_version must be '{CONTENT_UNIT_SCHEMA_VERSION}'", got=subset_data.get("schema_version")))

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

    outline_subset = set(matching_unit.get("evidence_subset") or [])
    claims = subset_data.get("claims")
    if not (isinstance(claims, list) and len(claims) <= 30):
        errors.append(err("U210", "claims must have length 0-30"))
        return errors

    subset_claim_ids = {claim.get("id") for claim in claims if isinstance(claim, dict)}
    if subset_claim_ids != outline_subset:
        errors.append(err(
            "U210",
            "subset.claims[].id != outline content unit evidence_subset",
            in_subset_only=sorted(value for value in subset_claim_ids - outline_subset if value),
            in_outline_only=sorted(outline_subset - subset_claim_ids),
        ))
    if len(subset_claim_ids) != len(claims):
        errors.append(err("U210", "subset claims must be objects with unique ids"))

    allowed_roles_by_claim: dict[str, set[str]] = {}
    routed_writing_context_ids: set[str] = set()
    for element in matching_unit.get("elements", []) if isinstance(matching_unit, dict) else []:
        if not isinstance(element, dict):
            continue
        for evidence_ref in element.get("evidence_refs", []) or []:
            if not isinstance(evidence_ref, dict):
                continue
            claim_id = evidence_ref.get("claim_id")
            role = evidence_ref.get("role")
            if isinstance(claim_id, str) and isinstance(role, str):
                allowed_roles_by_claim.setdefault(claim_id, set()).add(role)
        for context_id in element.get("writing_context_refs", []) or []:
            if isinstance(context_id, str):
                routed_writing_context_ids.add(context_id)

    routing = outline_data.get("claim_routing_table", {}) if isinstance(outline_data, dict) else {}
    referenced_source_ids: set[str] = set()
    for claim_index, claim in enumerate(claims):
        cloc = f"claims[{claim_index}]"
        if not isinstance(claim, dict):
            errors.append(err("U210", f"{cloc} must be an object"))
            continue
        claim_id = claim.get("id")
        narrative_role = claim.get("narrative_role")
        if narrative_role not in NARRATIVE_ROLE_VALUES:
            errors.append(err("U213", f"{cloc}.narrative_role must be one of {sorted(NARRATIVE_ROLE_VALUES)}", got=narrative_role))
        elif narrative_role not in allowed_roles_by_claim.get(claim_id, set()):
            errors.append(err("U214", f"{cloc}.narrative_role does not match this unit's evidence_refs", claim_id=claim_id, got=narrative_role, allowed=sorted(allowed_roles_by_claim.get(claim_id, set()))))

        route = routing.get(claim_id) if isinstance(routing, dict) else None
        if isinstance(route, dict) and route.get("primary") != unit_id:
            secondary_role = None
            for secondary in route.get("secondary", []) or []:
                if isinstance(secondary, dict) and secondary.get("unit") == unit_id:
                    secondary_role = secondary.get("role")
                    break
            if secondary_role is not None and narrative_role != secondary_role:
                errors.append(err("U214", f"{cloc}.narrative_role does not match secondary routing", claim_id=claim_id, got=narrative_role, expected=secondary_role))

        if strict_claims and claim_id not in evidence_index:
            errors.append(err("U212", f"{cloc}.id does not exist in supplied evidence files", claim_id=claim_id))
        elif isinstance(claim_id, str) and claim_id in evidence_index:
            reference_claim = evidence_index[claim_id]
            for field in ("text", "kind", "polarity", "topic_tag"):
                if claim.get(field) != reference_claim.get(field):
                    errors.append(err(
                        "U212",
                        f"{cloc}.{field} differs from evidence.json source",
                        claim_id=claim_id,
                        subset_value=claim.get(field),
                        evidence_value=reference_claim.get(field),
                    ))
            subset_evidence = claim.get("evidence")
            reference_evidence = reference_claim.get("evidence")
            if not isinstance(subset_evidence, list):
                errors.append(err("U212", f"{cloc}.evidence must be an array copied from evidence.json", claim_id=claim_id))
            elif not isinstance(reference_evidence, list):
                errors.append(err("U212", f"source evidence for {claim_id!r} is not an array", claim_id=claim_id))
            elif len(subset_evidence) != len(reference_evidence):
                errors.append(err("U212", f"{cloc}.evidence length differs from evidence.json", claim_id=claim_id, subset_count=len(subset_evidence), evidence_count=len(reference_evidence)))
            else:
                for evidence_index_number, (subset_item, reference_item) in enumerate(zip(subset_evidence, reference_evidence)):
                    if not isinstance(subset_item, dict):
                        errors.append(err(
                            "U212",
                            f"{cloc}.evidence[{evidence_index_number}] must be an object copied from evidence.json",
                            claim_id=claim_id,
                        ))
                        continue
                    if not isinstance(reference_item, dict):
                        errors.append(err(
                            "U212",
                            f"source evidence {claim_id!r}[{evidence_index_number}] is not an object",
                            claim_id=claim_id,
                        ))
                        continue
                    for field in ("source_id", "snippet", "quote_type", "snapshot_ref"):
                        if subset_item.get(field) != reference_item.get(field):
                            errors.append(err(
                                "U212",
                                f"{cloc}.evidence[{evidence_index_number}].{field} differs from evidence.json",
                                claim_id=claim_id,
                                subset_value=subset_item.get(field),
                                evidence_value=reference_item.get(field),
                            ))
            copied_claim = dict(claim)
            copied_claim.pop("narrative_role", None)
            if copied_claim != reference_claim:
                errors.append(err(
                    "U212",
                    f"{cloc} must be an exact copy of evidence.json plus narrative_role",
                    claim_id=claim_id,
                ))

        for evidence_item in claim.get("evidence", []) or []:
            if isinstance(evidence_item, dict) and isinstance(evidence_item.get("source_id"), str):
                referenced_source_ids.add(evidence_item["source_id"])

    # writing_context is an exact, routed boundary: the subset contains exactly
    # the contexts named by this unit's elements, copied unchanged from evidence.
    writing_context = subset_data.get("writing_context", [])
    if not isinstance(writing_context, list):
        errors.append(err("U215", "writing_context must be an array"))
        writing_context = []
    else:
        context_ids = [
            context.get("id")
            for context in writing_context
            if isinstance(context, dict) and isinstance(context.get("id"), str)
        ]
        if len(context_ids) != len(writing_context) or len(set(context_ids)) != len(context_ids):
            errors.append(err("U215", "writing_context entries must be objects with unique ids"))
        context_id_set = set(context_ids)
        if context_id_set != routed_writing_context_ids:
            errors.append(err(
                "U215",
                "subset writing_context ids must exactly equal elements writing_context_refs",
                extra_in_subset=sorted(context_id_set - routed_writing_context_ids),
                missing_from_subset=sorted(routed_writing_context_ids - context_id_set),
            ))

        for context_index, context in enumerate(writing_context):
            if not isinstance(context, dict):
                continue
            context_id = context.get("id")
            if strict_contexts and context_id not in writing_context_index:
                errors.append(err("U216", f"writing_context[{context_index}].id does not exist in supplied evidence files", context_id=context_id))
            elif isinstance(context_id, str) and context_id in writing_context_index:
                reference_context = writing_context_index[context_id]
                if context != reference_context:
                    errors.append(err(
                        "U216",
                        f"writing_context[{context_index}] differs from evidence.json source",
                        context_id=context_id,
                    ))
            if isinstance(context.get("source_id"), str):
                referenced_source_ids.add(context["source_id"])
            for source_id in context.get("source_ids", []) or []:
                if isinstance(source_id, str):
                    referenced_source_ids.add(source_id)
            for evidence_item in context.get("evidence", []) or []:
                if isinstance(evidence_item, dict) and isinstance(evidence_item.get("source_id"), str):
                    referenced_source_ids.add(evidence_item["source_id"])

    sources = subset_data.get("sources")
    if not isinstance(sources, list):
        errors.append(err("U211", "sources must be an array"))
        sources = []
    declared_source_ids = {source.get("id") for source in sources if isinstance(source, dict)}
    missing_source_ids = referenced_source_ids - declared_source_ids
    if missing_source_ids:
        errors.append(err("U211", "sources[] does not cover all referenced source_ids", missing=sorted(missing_source_ids)))

    return errors


def validate_subset(
    subset_data,
    outline_data,
    evidence_index=None,
    writing_context_index=None,
) -> list:
    """Dispatch evidence subset validation using the outline schema version."""
    if not isinstance(outline_data, dict):
        return [err("STRUCT", "Outline root must be a JSON object")]
    schema_version = outline_data.get("schema_version")
    if schema_version == LEGACY_SCHEMA_VERSION:
        return validate_subset_v1(subset_data, outline_data, evidence_index or {})
    if schema_version == CONTENT_UNIT_SCHEMA_VERSION:
        return validate_subset_v2(
            subset_data,
            outline_data,
            evidence_index,
            writing_context_index,
        )
    return [err("S001", f"Unsupported outline schema_version: {schema_version!r}")]


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
    if data.get("schema_version") == CONTENT_UNIT_SCHEMA_VERSION:
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
            "schema_version": CONTENT_UNIT_SCHEMA_VERSION,
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

    sections = data.get("sections") or []
    visual_inventory = data.get("visual_inventory") or []
    routing = data.get("claim_routing_table") or {}
    L0 = data.get("L0_draft") or {}
    paradigm = data.get("paradigm") or {}

    total_word_budget = sum(
        s.get("word_budget", 0)
        for s in sections
        if isinstance(s, dict) and isinstance(s.get("word_budget"), int)
        and not isinstance(s.get("word_budget"), bool)
    )
    total_visuals = sum(
        len(s.get("visuals") or [])
        for s in sections
        if isinstance(s, dict)
    )

    return {
        "schema_version": LEGACY_SCHEMA_VERSION,
        "paradigm": paradigm,
        "depth_level": data.get("depth_level"),
        "headline": L0.get("headline"),
        "sections_count": len(sections),
        "total_word_budget": total_word_budget,
        "total_visuals": total_visuals,
        "visual_density_per_kw": (total_visuals / (total_word_budget / 1000)) if total_word_budget else None,
        "routing_table_size": len(routing),
        "visual_inventory_size": len(visual_inventory),
    }


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Validate a v1.0 or v2.0 outline.json (and optional evidence_subset.json files)."
    )
    ap.add_argument("outline", help="path to outline.json")
    ap.add_argument(
        "--require-version",
        choices=sorted(SUPPORTED_SCHEMA_VERSIONS),
        help="reject an otherwise valid outline that is not this schema version",
    )
    ap.add_argument("--format", dest="format_path",
                    help="confirmed format.json used to cross-check the v2 organization preference")
    ap.add_argument("--language", dest="language",
                    help="request language (BCP 47) used to cross-check the v2 style language")
    ap.add_argument("--subsets", metavar="DIR_OR_GLOB",
                    help="directory containing evidence_subset.json files (e.g. content_units/ or sections/)")
    ap.add_argument("--evidence", nargs="*", default=[],
                    help="paths to d{N}.evidence.json files (for S012 cross-check)")
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

    if args.require_version and outline_data.get("schema_version") != args.require_version:
        all_errors.append(err(
            "O002",
            f"controller requires outline schema_version {args.require_version}",
            got=outline_data.get("schema_version"),
        ))

    if args.format_path:
        format_path = Path(args.format_path)
        if not format_path.exists():
            all_errors.append(err("FILE", f"Format file not found: {format_path}"))
        else:
            try:
                format_data = load_json(format_path)
            except json.JSONDecodeError as e:
                all_errors.append(err(
                    "JSON",
                    f"Invalid JSON in {format_path}: {e.msg} at line {e.lineno} col {e.colno}",
                    file=str(format_path),
                ))
            else:
                all_errors.extend(validate_format_contract(outline_data, format_data))

    if args.language:
        all_errors.extend(validate_language_contract(outline_data, args.language))

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

        if outline_data.get("schema_version") == CONTENT_UNIT_SCHEMA_VERSION:
            expected_unit_ids = {
                unit.get("id")
                for unit in outline_data.get("content_units", []) or []
                if isinstance(unit, dict) and isinstance(unit.get("id"), str)
            }
            missing_unit_ids = sorted(expected_unit_ids - set(subset_files_by_unit))
            duplicate_unit_ids = {
                unit_id: files
                for unit_id, files in subset_files_by_unit.items()
                if unit_id in expected_unit_ids and len(files) != 1
            }
            unexpected_unit_ids = sorted(set(subset_files_by_unit) - expected_unit_ids)
            if missing_unit_ids or duplicate_unit_ids or unexpected_unit_ids:
                all_errors.append(err(
                    "U200",
                    "each content unit must have exactly one evidence subset file",
                    missing_content_units=missing_unit_ids,
                    duplicate_content_units=duplicate_unit_ids,
                    unexpected_content_units=unexpected_unit_ids,
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
