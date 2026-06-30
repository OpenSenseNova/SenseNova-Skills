#!/usr/bin/env python3
"""Outline schema v1.0 validator.

Validates outline.json (and optionally evidence_subset.json files) against
the rules documented in schemas/outline.schema.md. Stdlib-only.

Usage:
    # validate outline.json only
    python3 validate_outline.py outline.json

    # validate outline + subsets + cross-check with evidence.json files
    python3 validate_outline.py outline.json \\
        --subsets sections/ \\
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

SCHEMA_VERSION = "1.0"

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

# ── Regex ──────────────────────────────────────────────────────────────────
SECTION_ID_RE = re.compile(r"^s\d+$")
CLAIM_ID_RE = re.compile(r"^d\d+\.c\d+$")


# ── Diagnostic helpers ─────────────────────────────────────────────────────
def err(rule, message, **fields):
    return {"rule": rule, "severity": "error", "message": message, **fields}


def warn(rule, message, **fields):
    return {"rule": rule, "severity": "warning", "message": message, **fields}


def char_len(s):
    return len(s) if isinstance(s, str) else None


# ── Outline.json validation ────────────────────────────────────────────────
def validate_outline(data) -> tuple[list, list]:
    """Return (errors, warnings) for the outline.json document."""
    errors: list = []
    warnings: list = []

    if not isinstance(data, dict):
        return ([err("STRUCT", "Root must be a JSON object")], [])

    # ── Top level (O001-O008) ──────────────────────────────────────────────
    sv = data.get("schema_version")
    if sv != SCHEMA_VERSION:
        errors.append(err("O001", f"schema_version must be '{SCHEMA_VERSION}'", got=sv))

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


# ── evidence_subset.json validation (S001-S014) ────────────────────────────
def validate_subset(subset_data, outline_data, evidence_index) -> list:
    """Validate a single evidence_subset.json. evidence_index is a dict
    mapping claim_id → original claim object from the d{N}.evidence.json
    files (used to verify S012). Pass an empty dict to skip S012/S013."""
    errors: list = []

    if not isinstance(subset_data, dict):
        return [err("STRUCT", "Root must be a JSON object")]

    sv = subset_data.get("schema_version")
    if sv != SCHEMA_VERSION:
        errors.append(err("S001", f"schema_version must be '{SCHEMA_VERSION}'", got=sv))

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


def compute_stats(data) -> dict:
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
        description="Validate a v1.0 outline.json (and optional evidence_subset.json files)."
    )
    ap.add_argument("outline", help="path to outline.json")
    ap.add_argument("--subsets", metavar="DIR_OR_GLOB",
                    help="directory containing evidence_subset.json files (e.g. sections/)")
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

    # Subsets check (optional)
    if args.subsets:
        subset_dir = Path(args.subsets)
        if subset_dir.is_dir():
            subset_paths = sorted(subset_dir.glob("*.evidence_subset.json"))
        else:
            subset_paths = [Path(p) for p in [args.subsets] if Path(p).exists()]

        evidence_index = build_evidence_index([Path(e) for e in args.evidence])

        for sp in subset_paths:
            try:
                sub_data = load_json(sp)
            except json.JSONDecodeError as e:
                all_errors.append(err("JSON",
                                      f"Invalid JSON in {sp}: {e.msg} at line {e.lineno} col {e.colno}",
                                      file=str(sp)))
                continue
            sub_errors = validate_subset(sub_data, outline_data, evidence_index)
            for e_obj in sub_errors:
                e_obj["file"] = str(sp)
            all_errors.extend(sub_errors)

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
