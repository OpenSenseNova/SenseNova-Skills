#!/usr/bin/env python3
"""Validate Scout's briefing.json against schemas/briefing.schema.md.

The validator checks structure, enums, ids, cross-field references, and
workflow cardinality. It deliberately does not impose character-count limits
on natural-language fields.

Usage:
    python3 validate_briefing.py path/to/briefing.json

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
from urllib.parse import urlsplit


TOP_LEVEL_KEYS = {
    "user_confirmations_needed",
    "task_interpretation",
    "context_entities",
    "terminology",
    "subdomain_partitions",
    "knowledge_topology",
    "information_landscape",
    "critical_unknowns",
    "candidate_lenses",
    "coverage_boundary",
    "hypotheses_to_test",
    "risk_flags",
}
UNCERTAINTY_TYPE_VALUES = {
    "goal",
    "scope",
    "criteria",
    "constraint",
    "audience",
    "time_range",
    "assumption",
}
RESEARCH_TYPE_VALUES = {
    "academic",
    "commercial",
    "financial",
    "medical",
    "legal",
    "trending",
    "tech_evaluation",
    "profile",
}
TIME_FOCUS_VALUES = {"historical", "current", "forward", "full_span"}
ENTITY_TYPE_VALUES = {
    "company",
    "technology",
    "person",
    "product",
    "concept",
    "policy",
    "event",
    "location",
}
CONFIDENCE_VALUES = {"low", "medium", "high"}
PARTITION_BASIS_VALUES = {
    "by_topic",
    "by_value_chain",
    "by_methodology",
    "by_stakeholder",
    "by_timeline",
    "other",
}
BLANK_NATURE_VALUES = {
    "info_scarce",
    "paywall",
    "language_barrier",
    "geo_restricted",
    "too_recent",
    "proprietary",
}
SOURCE_CATEGORY_VALUES = {
    "official",
    "news",
    "academic",
    "data",
    "forum",
    "analyst",
    "review",
}
TIME_SENSITIVITY_VALUES = {"fast_changing", "moderate", "slow"}
ACCESS_BARRIER_VALUES = {
    "paywall",
    "language",
    "geo",
    "login_required",
    "rate_limited",
}
ZOOM_LEVEL_VALUES = {"broad", "domain", "subdomain", "niche"}
RISK_VALUES = {
    "时效性",
    "来源偏见",
    "口径不一致",
    "数据过时",
    "地区差异",
    "法规不确定",
    "营销话术",
    "缺一手证据",
    "幸存者偏差",
    "benchmark不可比",
}
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def err(rule: str, message: str, **fields: object) -> dict:
    return {"rule": rule, "severity": "error", "message": message, **fields}


def is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parts = urlsplit(value)
        return (
            parts.scheme.lower() in {"http", "https"}
            and bool(parts.hostname)
            and parts.username is None
            and parts.password is None
        )
    except ValueError:
        return False


def validate_keys(
    value: object,
    required: set[str],
    *,
    location: str,
    rule: str,
    optional: set[str] | None = None,
) -> tuple[list[dict], dict | None]:
    if not isinstance(value, dict):
        return [err(rule, f"{location} must be an object")], None

    optional = optional or set()
    errors: list[dict] = []
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - optional)
    if missing:
        errors.append(err(rule, f"{location} is missing required fields", missing=missing))
    if unknown:
        errors.append(err(rule, f"{location} contains unknown fields", unknown=unknown))
    return errors, value


def require_string(
    value: object,
    *,
    location: str,
    rule: str,
    allow_empty: bool = False,
) -> list[dict]:
    valid = isinstance(value, str) and (allow_empty or bool(value.strip()))
    return [] if valid else [
        err(
            rule,
            f"{location} must be {'a string' if allow_empty else 'a non-empty string'}",
        )
    ]


def validate_string_array(
    value: object,
    *,
    location: str,
    rule: str,
    min_items: int = 0,
    max_items: int | None = None,
) -> tuple[list[dict], list[str]]:
    if not isinstance(value, list):
        return [err(rule, f"{location} must be an array")], []

    errors: list[dict] = []
    if len(value) < min_items:
        errors.append(
            err(
                rule,
                f"{location} must contain at least {min_items} item(s)",
                count=len(value),
            )
        )
    if max_items is not None and len(value) > max_items:
        errors.append(
            err(
                rule,
                f"{location} must contain at most {max_items} item(s)",
                count=len(value),
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


def validate_confirmation_question(
    item: object,
    *,
    tier: str,
    index: int,
) -> tuple[list[dict], str | None]:
    location = f"user_confirmations_needed.{tier}[{index}]"
    required = {
        "id",
        "question",
        "uncertainty_type",
        "why_it_matters",
        "options",
        "default_if_unanswered",
    }
    if tier in {"blocking", "high_value"}:
        required.add("impact_on_plan")

    errors, question = validate_keys(
        item,
        required,
        optional={"impact_on_plan"} if tier == "optional" else set(),
        location=location,
        rule="B010",
    )
    if question is None:
        return errors, None

    question_id = question.get("id")
    if not (isinstance(question_id, str) and ID_RE.fullmatch(question_id)):
        errors.append(err("B011", f"{location}.id must be a stable identifier",
                          got=question_id))
        question_id = None
    errors.extend(
        require_string(question.get("question"), location=f"{location}.question", rule="B012")
    )
    uncertainty_type = question.get("uncertainty_type")
    if uncertainty_type not in UNCERTAINTY_TYPE_VALUES:
        errors.append(
            err(
                "B013",
                f"{location}.uncertainty_type must be one of "
                f"{sorted(UNCERTAINTY_TYPE_VALUES)}",
                got=uncertainty_type,
            )
        )
    errors.extend(
        require_string(
            question.get("why_it_matters"),
            location=f"{location}.why_it_matters",
            rule="B014",
        )
    )
    if "impact_on_plan" in question:
        errors.extend(
            require_string(
                question.get("impact_on_plan"),
                location=f"{location}.impact_on_plan",
                rule="B014",
            )
        )

    options = question.get("options")
    option_ids: list[str] = []
    if not isinstance(options, list):
        errors.append(err("B015", f"{location}.options must be an array"))
    else:
        if not 2 <= len(options) <= 4:
            errors.append(
                err(
                    "B015",
                    f"{location}.options must contain 2-4 items",
                    count=len(options),
                )
            )
        for option_index, option in enumerate(options):
            option_location = f"{location}.options[{option_index}]"
            option_errors, option_obj = validate_keys(
                option,
                {"id", "label", "planning_implication"},
                location=option_location,
                rule="B016",
            )
            errors.extend(option_errors)
            if option_obj is None:
                continue
            option_id = option_obj.get("id")
            if not (isinstance(option_id, str) and ID_RE.fullmatch(option_id)):
                errors.append(
                    err("B017", f"{option_location}.id must be a stable identifier",
                        got=option_id)
                )
            else:
                option_ids.append(option_id)
            for field in ("label", "planning_implication"):
                errors.extend(
                    require_string(
                        option_obj.get(field),
                        location=f"{option_location}.{field}",
                        rule="B018",
                    )
                )
        duplicate_options = sorted(
            option_id
            for option_id, count in Counter(option_ids).items()
            if count > 1
        )
        if duplicate_options:
            errors.append(
                err(
                    "B019",
                    f"{location}.options ids must be unique",
                    duplicates=duplicate_options,
                )
            )

    default_value = question.get("default_if_unanswered")
    if tier == "blocking":
        if default_value is not None:
            errors.append(
                err("B020", f"{location}.default_if_unanswered must be null")
            )
    else:
        default_required = {"option_id", "rationale"}
        if tier == "high_value":
            default_required.add("confidence")
        default_errors, default_obj = validate_keys(
            default_value,
            default_required,
            location=f"{location}.default_if_unanswered",
            rule="B021",
        )
        errors.extend(default_errors)
        if default_obj is not None:
            default_option_id = default_obj.get("option_id")
            if default_option_id not in option_ids:
                errors.append(
                    err(
                        "B022",
                        f"{location}.default_if_unanswered.option_id must reference "
                        "an options[].id",
                        got=default_option_id,
                    )
                )
            errors.extend(
                require_string(
                    default_obj.get("rationale"),
                    location=f"{location}.default_if_unanswered.rationale",
                    rule="B023",
                )
            )
            if tier == "high_value" and default_obj.get("confidence") not in CONFIDENCE_VALUES:
                errors.append(
                    err(
                        "B024",
                        f"{location}.default_if_unanswered.confidence must be one of "
                        f"{sorted(CONFIDENCE_VALUES)}",
                        got=default_obj.get("confidence"),
                    )
                )
    return errors, question_id


def validate(data: object) -> list[dict]:
    errors: list[dict] = []
    root_errors, root = validate_keys(
        data,
        TOP_LEVEL_KEYS,
        location="root",
        rule="B001",
    )
    errors.extend(root_errors)
    if root is None:
        return errors

    confirmation_errors, confirmations = validate_keys(
        root.get("user_confirmations_needed"),
        {"blocking", "high_value", "optional"},
        location="user_confirmations_needed",
        rule="B002",
    )
    errors.extend(confirmation_errors)
    question_ids: list[str] = []
    if confirmations is not None:
        for tier in ("blocking", "high_value", "optional"):
            items = confirmations.get(tier)
            if not isinstance(items, list):
                errors.append(
                    err("B003", f"user_confirmations_needed.{tier} must be an array")
                )
                continue
            if tier == "blocking" and len(items) > 3:
                errors.append(
                    err(
                        "B003",
                        "user_confirmations_needed.blocking must contain at most 3 items",
                        count=len(items),
                    )
                )
            for index, item in enumerate(items):
                item_errors, question_id = validate_confirmation_question(
                    item,
                    tier=tier,
                    index=index,
                )
                errors.extend(item_errors)
                if question_id is not None:
                    question_ids.append(question_id)
    duplicate_questions = sorted(
        item_id for item_id, count in Counter(question_ids).items() if count > 1
    )
    if duplicate_questions:
        errors.append(
            err("B025", "confirmation question ids must be unique",
                duplicates=duplicate_questions)
        )

    interpretation_errors, interpretation = validate_keys(
        root.get("task_interpretation"),
        {
            "user_goal",
            "requested_output_inferred",
            "research_type_inferred",
            "audience_inferred",
            "time_focus",
            "explicit_constraints",
            "implicit_scope_hints",
        },
        location="task_interpretation",
        rule="B030",
    )
    errors.extend(interpretation_errors)
    if interpretation is not None:
        for field in ("user_goal", "requested_output_inferred", "audience_inferred"):
            errors.extend(
                require_string(
                    interpretation.get(field),
                    location=f"task_interpretation.{field}",
                    rule="B031",
                )
            )
        if interpretation.get("research_type_inferred") not in RESEARCH_TYPE_VALUES:
            errors.append(
                err(
                    "B032",
                    "task_interpretation.research_type_inferred must be a valid enum",
                    got=interpretation.get("research_type_inferred"),
                )
            )
        if interpretation.get("time_focus") not in TIME_FOCUS_VALUES:
            errors.append(
                err(
                    "B033",
                    "task_interpretation.time_focus must be a valid enum",
                    got=interpretation.get("time_focus"),
                )
            )
        for field in ("explicit_constraints", "implicit_scope_hints"):
            field_errors, _ = validate_string_array(
                interpretation.get(field),
                location=f"task_interpretation.{field}",
                rule="B034",
            )
            errors.extend(field_errors)

    entities = root.get("context_entities")
    if not isinstance(entities, list):
        errors.append(err("B040", "context_entities must be an array"))
        entities = []
    elif len(entities) < 5:
        errors.append(
            err("B040", "context_entities must contain at least 5 items",
                count=len(entities))
        )
    entity_names: list[str] = []
    for index, item in enumerate(entities):
        location = f"context_entities[{index}]"
        item_errors, entity = validate_keys(
            item,
            {"name", "type", "explicit_or_inferred", "why_it_matters", "confidence"},
            location=location,
            rule="B041",
        )
        errors.extend(item_errors)
        if entity is None:
            continue
        name = entity.get("name")
        errors.extend(require_string(name, location=f"{location}.name", rule="B042"))
        if is_nonempty_string(name):
            entity_names.append(name)
        if entity.get("type") not in ENTITY_TYPE_VALUES:
            errors.append(err("B043", f"{location}.type must be a valid enum",
                              got=entity.get("type")))
        if entity.get("explicit_or_inferred") not in {"explicit", "inferred"}:
            errors.append(
                err("B044", f"{location}.explicit_or_inferred must be explicit or inferred",
                    got=entity.get("explicit_or_inferred"))
            )
        errors.extend(
            require_string(
                entity.get("why_it_matters"),
                location=f"{location}.why_it_matters",
                rule="B045",
            )
        )
        if entity.get("confidence") not in CONFIDENCE_VALUES:
            errors.append(err("B046", f"{location}.confidence must be a valid enum",
                              got=entity.get("confidence")))
    duplicate_entities = sorted(
        name for name, count in Counter(entity_names).items() if count > 1
    )
    if duplicate_entities:
        errors.append(
            err("B047", "context_entities names must be unique",
                duplicates=duplicate_entities)
        )

    terminology = root.get("terminology")
    if not isinstance(terminology, list):
        errors.append(err("B050", "terminology must be an array"))
        terminology = []
    terms: list[str] = []
    for index, item in enumerate(terminology):
        location = f"terminology[{index}]"
        item_errors, term_obj = validate_keys(
            item,
            {"term", "aliases", "note"},
            location=location,
            rule="B051",
        )
        errors.extend(item_errors)
        if term_obj is None:
            continue
        term = term_obj.get("term")
        errors.extend(require_string(term, location=f"{location}.term", rule="B052"))
        if is_nonempty_string(term):
            terms.append(term)
        alias_errors, _ = validate_string_array(
            term_obj.get("aliases"),
            location=f"{location}.aliases",
            rule="B053",
        )
        errors.extend(alias_errors)
        errors.extend(
            require_string(term_obj.get("note"), location=f"{location}.note", rule="B054")
        )
    duplicate_terms = sorted(term for term, count in Counter(terms).items() if count > 1)
    if duplicate_terms:
        errors.append(err("B055", "terminology terms must be unique",
                          duplicates=duplicate_terms))

    partition_errors, partitions = validate_keys(
        root.get("subdomain_partitions"),
        {"partition_basis", "subdomains"},
        location="subdomain_partitions",
        rule="B060",
    )
    errors.extend(partition_errors)
    if partitions is not None:
        if partitions.get("partition_basis") not in PARTITION_BASIS_VALUES:
            errors.append(
                err("B061", "subdomain_partitions.partition_basis must be a valid enum",
                    got=partitions.get("partition_basis"))
            )
        subdomains = partitions.get("subdomains")
        if not isinstance(subdomains, list):
            errors.append(err("B062", "subdomain_partitions.subdomains must be an array"))
        else:
            if len(subdomains) < 3:
                errors.append(
                    err(
                        "B062",
                        "subdomain_partitions.subdomains must contain at least 3 items",
                        count=len(subdomains),
                    )
                )
            names: list[str] = []
            for index, item in enumerate(subdomains):
                location = f"subdomain_partitions.subdomains[{index}]"
                item_errors, subdomain = validate_keys(
                    item,
                    {"name", "scope_hint"},
                    location=location,
                    rule="B063",
                )
                errors.extend(item_errors)
                if subdomain is None:
                    continue
                for field in ("name", "scope_hint"):
                    errors.extend(
                        require_string(
                            subdomain.get(field),
                            location=f"{location}.{field}",
                            rule="B064",
                        )
                    )
                if is_nonempty_string(subdomain.get("name")):
                    names.append(subdomain["name"])
            duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
            if duplicates:
                errors.append(
                    err("B065", "subdomain names must be unique", duplicates=duplicates)
                )

    topology_errors, topology = validate_keys(
        root.get("knowledge_topology"),
        {"consensus", "disputes", "blanks"},
        location="knowledge_topology",
        rule="B070",
    )
    errors.extend(topology_errors)
    if topology is not None:
        consensus = topology.get("consensus")
        if not isinstance(consensus, list):
            errors.append(err("B071", "knowledge_topology.consensus must be an array"))
        else:
            if len(consensus) < 2:
                errors.append(
                    err("B071", "knowledge_topology.consensus must contain at least 2 items",
                        count=len(consensus))
                )
            for index, item in enumerate(consensus):
                location = f"knowledge_topology.consensus[{index}]"
                item_errors, consensus_item = validate_keys(
                    item,
                    {"fact", "source_hint"},
                    location=location,
                    rule="B072",
                )
                errors.extend(item_errors)
                if consensus_item is not None:
                    for field in ("fact", "source_hint"):
                        errors.extend(
                            require_string(
                                consensus_item.get(field),
                                location=f"{location}.{field}",
                                rule="B073",
                            )
                        )

        disputes = topology.get("disputes")
        if not isinstance(disputes, list):
            errors.append(err("B074", "knowledge_topology.disputes must be an array"))
        elif not disputes:
            errors.append(
                err(
                    "B074",
                    "knowledge_topology.disputes must record at least one dispute "
                    "or an explicit no-dispute finding",
                )
            )
        else:
            for index, item in enumerate(disputes):
                location = f"knowledge_topology.disputes[{index}]"
                item_errors, dispute = validate_keys(
                    item,
                    {"issue", "positions_exist", "representative_sources"},
                    location=location,
                    rule="B075",
                )
                errors.extend(item_errors)
                if dispute is None:
                    continue
                errors.extend(
                    require_string(dispute.get("issue"), location=f"{location}.issue",
                                   rule="B076")
                )
                for field in ("positions_exist", "representative_sources"):
                    array_errors, _ = validate_string_array(
                        dispute.get(field),
                        location=f"{location}.{field}",
                        rule="B077",
                    )
                    errors.extend(array_errors)

        blanks = topology.get("blanks")
        if not isinstance(blanks, list):
            errors.append(err("B078", "knowledge_topology.blanks must be an array"))
        else:
            for index, item in enumerate(blanks):
                location = f"knowledge_topology.blanks[{index}]"
                item_errors, blank = validate_keys(
                    item,
                    {"blank", "blank_nature"},
                    location=location,
                    rule="B079",
                )
                errors.extend(item_errors)
                if blank is None:
                    continue
                errors.extend(
                    require_string(blank.get("blank"), location=f"{location}.blank",
                                   rule="B080")
                )
                if blank.get("blank_nature") not in BLANK_NATURE_VALUES:
                    errors.append(
                        err("B081", f"{location}.blank_nature must be a valid enum",
                            got=blank.get("blank_nature"))
                    )

    landscape_errors, landscape = validate_keys(
        root.get("information_landscape"),
        {
            "primary_source_categories",
            "secondary_source_categories",
            "data_source_categories",
            "expert_or_industry_sources",
            "weak_or_risky_sources",
            "high_value_urls",
            "search_terms",
            "time_sensitivity",
            "access_barriers",
        },
        location="information_landscape",
        rule="B090",
    )
    errors.extend(landscape_errors)
    if landscape is not None:
        for field in (
            "primary_source_categories",
            "secondary_source_categories",
            "data_source_categories",
            "expert_or_industry_sources",
            "weak_or_risky_sources",
        ):
            field_errors, _ = validate_string_array(
                landscape.get(field),
                location=f"information_landscape.{field}",
                rule="B091",
            )
            errors.extend(field_errors)

        high_value_urls = landscape.get("high_value_urls")
        categories: list[str] = []
        if not isinstance(high_value_urls, list):
            errors.append(err("B092", "information_landscape.high_value_urls must be an array"))
        else:
            for index, item in enumerate(high_value_urls):
                location = f"information_landscape.high_value_urls[{index}]"
                item_errors, url_item = validate_keys(
                    item,
                    {"url", "category", "why"},
                    location=location,
                    rule="B093",
                )
                errors.extend(item_errors)
                if url_item is None:
                    continue
                if not is_http_url(url_item.get("url")):
                    errors.append(err("B094", f"{location}.url must be an HTTP(S) URL",
                                      got=url_item.get("url")))
                category = url_item.get("category")
                if category not in SOURCE_CATEGORY_VALUES:
                    errors.append(err("B095", f"{location}.category must be a valid enum",
                                      got=category))
                else:
                    categories.append(category)
                errors.extend(
                    require_string(url_item.get("why"), location=f"{location}.why",
                                   rule="B096")
                )
            if len(set(categories)) < 3:
                errors.append(
                    err(
                        "B097",
                        "information_landscape.high_value_urls must cover at least "
                        "3 distinct categories",
                        categories=sorted(set(categories)),
                    )
                )

        search_terms = landscape.get("search_terms")
        if not isinstance(search_terms, list):
            errors.append(err("B098", "information_landscape.search_terms must be an array"))
        else:
            for index, item in enumerate(search_terms):
                location = f"information_landscape.search_terms[{index}]"
                item_errors, term = validate_keys(
                    item,
                    {"term", "language", "use_case"},
                    location=location,
                    rule="B099",
                )
                errors.extend(item_errors)
                if term is not None:
                    for field in ("term", "language", "use_case"):
                        errors.extend(
                            require_string(
                                term.get(field),
                                location=f"{location}.{field}",
                                rule="B100",
                            )
                        )

        time_errors, time_sensitivity = validate_keys(
            landscape.get("time_sensitivity"),
            {"rate", "recommended_window", "reason"},
            location="information_landscape.time_sensitivity",
            rule="B101",
        )
        errors.extend(time_errors)
        if time_sensitivity is not None:
            if time_sensitivity.get("rate") not in TIME_SENSITIVITY_VALUES:
                errors.append(
                    err(
                        "B102",
                        "information_landscape.time_sensitivity.rate must be a valid enum",
                        got=time_sensitivity.get("rate"),
                    )
                )
            for field in ("recommended_window", "reason"):
                errors.extend(
                    require_string(
                        time_sensitivity.get(field),
                        location=f"information_landscape.time_sensitivity.{field}",
                        rule="B103",
                    )
                )

        barriers = landscape.get("access_barriers")
        if not isinstance(barriers, list):
            errors.append(err("B104", "information_landscape.access_barriers must be an array"))
        else:
            for index, item in enumerate(barriers):
                location = f"information_landscape.access_barriers[{index}]"
                item_errors, barrier = validate_keys(
                    item,
                    {"barrier", "affected_sources", "workaround_hint"},
                    location=location,
                    rule="B105",
                )
                errors.extend(item_errors)
                if barrier is None:
                    continue
                if barrier.get("barrier") not in ACCESS_BARRIER_VALUES:
                    errors.append(err("B106", f"{location}.barrier must be a valid enum",
                                      got=barrier.get("barrier")))
                for field in ("affected_sources", "workaround_hint"):
                    errors.extend(
                        require_string(
                            barrier.get(field),
                            location=f"{location}.{field}",
                            rule="B107",
                        )
                    )

    unknowns = root.get("critical_unknowns")
    if not isinstance(unknowns, list):
        errors.append(err("B110", "critical_unknowns must be an array"))
        unknowns = []
    for index, item in enumerate(unknowns):
        location = f"critical_unknowns[{index}]"
        item_errors, unknown = validate_keys(
            item,
            {
                "unknown",
                "why_it_matters",
                "evidence_needed",
                "can_be_resolved_by_research",
                "importance",
            },
            location=location,
            rule="B111",
        )
        errors.extend(item_errors)
        if unknown is None:
            continue
        for field in ("unknown", "why_it_matters", "evidence_needed"):
            errors.extend(
                require_string(
                    unknown.get(field),
                    location=f"{location}.{field}",
                    rule="B112",
                )
            )
        if unknown.get("can_be_resolved_by_research") is not True:
            errors.append(
                err("B113", f"{location}.can_be_resolved_by_research must be true")
            )
        if unknown.get("importance") not in CONFIDENCE_VALUES:
            errors.append(err("B114", f"{location}.importance must be a valid enum",
                              got=unknown.get("importance")))

    lenses = root.get("candidate_lenses")
    if not isinstance(lenses, list):
        errors.append(err("B120", "candidate_lenses must be an array"))
        lenses = []
    elif len(lenses) < 3:
        errors.append(
            err("B120", "candidate_lenses must contain at least 3 items",
                count=len(lenses))
        )
    lens_names: list[str] = []
    for index, item in enumerate(lenses):
        location = f"candidate_lenses[{index}]"
        item_errors, lens = validate_keys(
            item,
            {"lens", "useful_for", "may_miss", "binding_strength"},
            location=location,
            rule="B121",
        )
        errors.extend(item_errors)
        if lens is None:
            continue
        for field in ("lens", "useful_for", "may_miss"):
            errors.extend(
                require_string(lens.get(field), location=f"{location}.{field}",
                               rule="B122")
            )
        if is_nonempty_string(lens.get("lens")):
            lens_names.append(lens["lens"])
        if lens.get("binding_strength") != "suggestive":
            errors.append(
                err("B123", f"{location}.binding_strength must equal suggestive",
                    got=lens.get("binding_strength"))
            )
    duplicate_lenses = sorted(
        lens for lens, count in Counter(lens_names).items() if count > 1
    )
    if duplicate_lenses:
        errors.append(err("B124", "candidate_lenses names must be unique",
                          duplicates=duplicate_lenses))

    boundary_errors, boundary = validate_keys(
        root.get("coverage_boundary"),
        {
            "adjacent_fields_not_explored",
            "opposing_perspectives_not_searched",
            "second_order_effects_not_explored",
            "alternative_paths_not_explored",
            "scan_scope",
            "lists_known_partial",
        },
        location="coverage_boundary",
        rule="B130",
    )
    errors.extend(boundary_errors)
    if boundary is not None:
        for field in (
            "adjacent_fields_not_explored",
            "opposing_perspectives_not_searched",
            "second_order_effects_not_explored",
            "alternative_paths_not_explored",
        ):
            field_errors, _ = validate_string_array(
                boundary.get(field),
                location=f"coverage_boundary.{field}",
                rule="B131",
            )
            errors.extend(field_errors)

        scan_errors, scan_scope = validate_keys(
            boundary.get("scan_scope"),
            {"zoom_level", "scanned_angles", "unscanned_angles"},
            location="coverage_boundary.scan_scope",
            rule="B132",
        )
        errors.extend(scan_errors)
        if scan_scope is not None:
            if scan_scope.get("zoom_level") not in ZOOM_LEVEL_VALUES:
                errors.append(
                    err("B133", "coverage_boundary.scan_scope.zoom_level must be a valid enum",
                        got=scan_scope.get("zoom_level"))
                )
            for field in ("scanned_angles", "unscanned_angles"):
                field_errors, _ = validate_string_array(
                    scan_scope.get(field),
                    location=f"coverage_boundary.scan_scope.{field}",
                    rule="B134",
                    min_items=1,
                )
                errors.extend(field_errors)

        partial_errors, partial = validate_keys(
            boundary.get("lists_known_partial"),
            {"entities", "subdomains", "terminology", "unknowns", "disputes", "risks"},
            location="coverage_boundary.lists_known_partial",
            rule="B135",
        )
        errors.extend(partial_errors)
        if partial is not None:
            array_specs = {
                "entities": ("more_likely_in",),
                "subdomains": ("alternative_partitions_exist",),
                "terminology": ("jargon_pockets_not_covered",),
                "disputes": ("more_likely_in",),
                "risks": ("more_likely_in",),
            }
            for section, keys in array_specs.items():
                section_errors, section_obj = validate_keys(
                    partial.get(section),
                    set(keys),
                    location=f"coverage_boundary.lists_known_partial.{section}",
                    rule="B136",
                )
                errors.extend(section_errors)
                if section_obj is not None:
                    field = keys[0]
                    field_errors, _ = validate_string_array(
                        section_obj.get(field),
                        location=(
                            f"coverage_boundary.lists_known_partial.{section}.{field}"
                        ),
                        rule="B137",
                    )
                    errors.extend(field_errors)
            unknown_errors, unknown_obj = validate_keys(
                partial.get("unknowns"),
                {"research_will_surface_more"},
                location="coverage_boundary.lists_known_partial.unknowns",
                rule="B138",
            )
            errors.extend(unknown_errors)
            if (
                unknown_obj is not None
                and not isinstance(unknown_obj.get("research_will_surface_more"), bool)
            ):
                errors.append(
                    err(
                        "B139",
                        "coverage_boundary.lists_known_partial.unknowns."
                        "research_will_surface_more must be a boolean",
                    )
                )

    hypotheses = root.get("hypotheses_to_test")
    if not isinstance(hypotheses, list):
        errors.append(err("B140", "hypotheses_to_test must be an array"))
        hypotheses = []
    elif len(hypotheses) > 3:
        errors.append(
            err("B140", "hypotheses_to_test must contain at most 3 items",
                count=len(hypotheses))
        )
    for index, item in enumerate(hypotheses):
        location = f"hypotheses_to_test[{index}]"
        item_errors, hypothesis = validate_keys(
            item,
            {"claim", "basis", "confidence", "disconfirming_evidence"},
            location=location,
            rule="B141",
        )
        errors.extend(item_errors)
        if hypothesis is None:
            continue
        for field in ("claim", "basis", "disconfirming_evidence"):
            errors.extend(
                require_string(hypothesis.get(field), location=f"{location}.{field}",
                               rule="B142")
            )
        if hypothesis.get("confidence") not in CONFIDENCE_VALUES:
            errors.append(err("B143", f"{location}.confidence must be a valid enum",
                              got=hypothesis.get("confidence")))

    risk_flags = root.get("risk_flags")
    if not isinstance(risk_flags, list):
        errors.append(err("B150", "risk_flags must be an array"))
        risk_flags = []
    seen_risks: list[str] = []
    for index, item in enumerate(risk_flags):
        location = f"risk_flags[{index}]"
        item_errors, risk = validate_keys(
            item,
            {"risk", "why_it_matters", "mitigation", "severity"},
            location=location,
            rule="B151",
        )
        errors.extend(item_errors)
        if risk is None:
            continue
        risk_name = risk.get("risk")
        if risk_name not in RISK_VALUES:
            errors.append(err("B152", f"{location}.risk must be a valid enum",
                              got=risk_name))
        else:
            seen_risks.append(risk_name)
        for field in ("why_it_matters", "mitigation"):
            errors.extend(
                require_string(risk.get(field), location=f"{location}.{field}",
                               rule="B153")
            )
        if risk.get("severity") not in CONFIDENCE_VALUES:
            errors.append(err("B154", f"{location}.severity must be a valid enum",
                              got=risk.get("severity")))
    duplicate_risks = sorted(
        risk for risk, count in Counter(seen_risks).items() if count > 1
    )
    if duplicate_risks:
        errors.append(err("B155", "risk_flags must not repeat risk types",
                          duplicates=duplicate_risks))
    missing_risks = sorted(RISK_VALUES - set(seen_risks))
    if missing_risks:
        errors.append(
            err(
                "B156",
                "risk_flags must record all 10 scanned risk types",
                missing=missing_risks,
            )
        )

    return errors


def build_stats(data: dict) -> dict:
    confirmations = data.get("user_confirmations_needed", {})
    return {
        "blocking_confirmations": len(confirmations.get("blocking", [])),
        "high_value_confirmations": len(confirmations.get("high_value", [])),
        "optional_confirmations": len(confirmations.get("optional", [])),
        "context_entities": len(data.get("context_entities", [])),
        "subdomains": len(data.get("subdomain_partitions", {}).get("subdomains", [])),
        "candidate_lenses": len(data.get("candidate_lenses", [])),
        "risk_flags": len(data.get("risk_flags", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a briefing.json file.")
    parser.add_argument("path", help="path to briefing.json")
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

    print(
        json.dumps(
            {"ok": True, "errors": [], "stats": build_stats(data)},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
