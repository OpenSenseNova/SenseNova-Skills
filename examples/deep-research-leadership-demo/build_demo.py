#!/usr/bin/env python3
"""Build the standalone leadership replay from the archived research run."""

import argparse
import base64
import json
import pathlib
import re
import zipfile


RUN_PREFIX = "2026-07-14-china-9-strata-9185/"

EXPECTED_DIMENSIONS = {
    "d1": (18, 12, 4),
    "d2": (14, 10, 6),
    "d3": (18, 11, 5),
    "d4": (17, 9, 5),
    "d5": (10, 15, 5),
    "d6": (13, 8, 5),
    "d7": (18, 8, 6),
}
EXPECTED_TOTALS = {
    "dimensionCount": 7,
    "claimCount": 108,
    "sourceEntryCount": 73,
    "uniqueSourceCount": 70,
    "findingCount": 36,
    "contentUnitCount": 5,
    "citationCount": 58,
}
STAGES = ["需求确认", "研究规划", "多主题研究", "质量核验", "报告组织", "写作审校", "最终交付"]
PROGRESS = [14, 29, 43, 57, 71, 86, 100]
WORK_MODES = ["scope", "plan", "research", "quality", "outline", "review", "delivery"]
HEADLINES = [
    "研究范围与关键口径已经确认",
    "7 个研究维度已经规划完成",
    "多主题研究正在推进",
    "研究材料已经完成质量核验",
    "最终报告结构已经组织完成",
    "报告写作与终审已经完成",
    "最终报告与引用清单已经生成",
]
EXPLANATIONS = [
    "研究问题、范围和关键统计口径已经确认。",
    "研究任务已经拆分为 7 个相互衔接的研究维度。",
    "各研究维度已进入资料研究阶段。",
    "各维度研究材料已经完成核验，关键发现可供查阅。",
    "报告结构已经按照 5 个内容单元组织完成。",
    "报告内容已经写作完成，并通过最终审校。",
    "最终报告与引用清单已经生成，可以交付。",
]
STATEMENTS = [
    ["研究范围已经确认", "关键口径边界已经明确"],
    ["已规划 7 个研究维度"],
    ["7 个研究维度正在同步推进"],
    ["研究材料已完成质量核验", "核验后的关键发现已可查阅"],
    ["5 个报告内容单元已组织完成"],
    ["5 个报告内容单元已完成写作", "最终审校已通过"],
    ["最终报告已生成", "引用清单已生成"],
]
GATES = [
    ("hidden", "hidden", False, False, False, False),
    ("planned", "hidden", False, False, False, False),
    ("researching", "hidden", False, False, False, False),
    ("verified", "hidden", True, True, False, False),
    ("verified", "organized", True, True, False, False),
    ("verified", "written", True, True, True, False),
    ("verified", "delivered", True, True, True, True),
]


def read_text(archive, relative_path):
    return archive.read(RUN_PREFIX + relative_path).decode("utf-8")


def read_json(archive, relative_path):
    return json.loads(read_text(archive, relative_path))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def zip_timestamp_label(archive, relative_path):
    year, month, day, hour, minute, _second = archive.getinfo(
        RUN_PREFIX + relative_path
    ).date_time
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"


def make_snapshots():
    snapshots = []
    for index, gate in enumerate(GATES):
        dimension_state, unit_state, metrics, findings, review, report = gate
        snapshots.append(
            {
                "index": index + 1,
                "stage": STAGES[index],
                "progress": PROGRESS[index],
                "workMode": WORK_MODES[index],
                "headline": HEADLINES[index],
                "explanation": EXPLANATIONS[index],
                "statements": STATEMENTS[index],
                "dimensionState": dimension_state,
                "unitState": unit_state,
                "metricsVisible": metrics,
                "findingsAvailable": findings,
                "reviewPassed": review,
                "reportAvailable": report,
            }
        )
    return snapshots


def validate_payload(payload):
    dimensions = payload.get("dimensions", [])
    dimension_ids = [dimension.get("id") for dimension in dimensions]
    require(dimension_ids == list(EXPECTED_DIMENSIONS), "unexpected dimension IDs")
    require(len(set(dimension_ids)) == 7, "dimension IDs must be unique")

    for dimension in dimensions:
        dimension_id = dimension["id"]
        observed = (
            dimension.get("claimCount"),
            dimension.get("sourceCount"),
            len(dimension.get("findings", [])),
        )
        require(observed == EXPECTED_DIMENSIONS[dimension_id], f"unexpected totals for {dimension_id}")
        require(bool(dimension.get("name")), f"missing name for {dimension_id}")
        require(bool(dimension.get("headline")), f"missing headline for {dimension_id}")
        require(
            dimension.get("sourceCount") == len(dimension.get("sourceIds", [])),
            f"source count mismatch for {dimension_id}",
        )
        require(all(dimension["sourceIds"]), f"empty source ID in {dimension_id}")
        for finding in dimension["findings"]:
            claim_ids = finding.get("claimIds", [])
            require(bool(finding.get("text")), f"empty finding in {dimension_id}")
            require(bool(claim_ids), f"finding lacks claims in {dimension_id}")
            require(
                finding.get("claimCount") == len(claim_ids),
                f"finding claim mismatch in {dimension_id}",
            )

    calculated_totals = {
        "dimensionCount": len(dimensions),
        "claimCount": sum(dimension["claimCount"] for dimension in dimensions),
        "sourceEntryCount": sum(dimension["sourceCount"] for dimension in dimensions),
        "uniqueSourceCount": len(
            {
                source_id
                for dimension in dimensions
                for source_id in dimension["sourceIds"]
            }
        ),
        "findingCount": sum(len(dimension["findings"]) for dimension in dimensions),
        "contentUnitCount": len(payload.get("contentUnits", [])),
        "citationCount": len(payload.get("citations", [])),
    }
    require(calculated_totals == EXPECTED_TOTALS, "archive totals do not match expected sample")
    require(payload.get("totals") == calculated_totals, "payload totals are inconsistent")

    units = payload.get("contentUnits", [])
    require(len({unit.get("id") for unit in units}) == 5, "content unit IDs must be unique")
    require(all(unit.get("title") for unit in units), "content unit title is empty")
    require(payload.get("verdict") == "pass", "final review did not pass")
    require(bool(payload.get("reportMarkdown")), "report markdown is empty")
    require(bool(payload.get("citationsJson")), "citation JSON is empty")

    expected_metadata = {
        "mode": "heavy",
        "runId": "2026-07-14-china-9-strata-9185",
        "reportTitle": "中国九阶层实际收入与财务状况：中产人数、特征与财力",
        "startLabel": "2026-07-14 06:03",
        "completionLabel": "2026-07-14 09:37",
        "runSpanLabel": "真实运行跨度 06:03–09:37",
        "elapsedLabel": "约 3 小时 34 分",
    }
    require(payload.get("metadata") == expected_metadata, "run metadata is unexpected")

    snapshots = payload.get("snapshots", [])
    require(len(snapshots) == 7, "expected seven replay snapshots")
    valid_dimension_states = {"hidden", "planned", "researching", "verified"}
    valid_unit_states = {"hidden", "organized", "written", "delivered"}
    for index, snapshot in enumerate(snapshots):
        require(snapshot.get("index") == index + 1, "snapshot indexes must be sequential")
        require(snapshot.get("stage") == STAGES[index], "snapshot stage mismatch")
        require(snapshot.get("progress") == PROGRESS[index], "snapshot progress mismatch")
        require(snapshot.get("workMode") == WORK_MODES[index], "snapshot mode mismatch")
        require(snapshot.get("headline") == HEADLINES[index], "snapshot headline mismatch")
        require(bool(snapshot.get("explanation")), "snapshot explanation is empty")
        statements = snapshot.get("statements", [])
        require(1 <= len(statements) <= 3, "snapshot statements must contain one to three items")
        require(all(statements), "snapshot statement is empty")
        require(snapshot.get("dimensionState") in valid_dimension_states, "invalid dimension state")
        require(snapshot.get("unitState") in valid_unit_states, "invalid content unit state")
        observed_gate = (
            snapshot["dimensionState"],
            snapshot["unitState"],
            snapshot.get("metricsVisible"),
            snapshot.get("findingsAvailable"),
            snapshot.get("reviewPassed"),
            snapshot.get("reportAvailable"),
        )
        require(observed_gate == GATES[index], "snapshot gate mismatch")


def build_payload(archive):
    roots = {
        info.filename.split("/", 1)[0]
        for info in archive.infolist()
        if info.filename and not info.filename.startswith("__MACOSX/")
    }
    require(len(roots) == 1, "archive must contain one research run")
    run_id = roots.pop()
    require(run_id + "/" == RUN_PREFIX, "archive run ID is unexpected")

    plan = read_json(archive, "plan.json")
    outline = read_json(archive, "outline.json")
    report_markdown = read_text(archive, "report.md")
    citations_data = read_json(archive, "citations.json")
    final_review = read_text(archive, "final_review.md")

    dimensions = []
    for plan_dimension in plan.get("dimensions", []):
        dimension_id = plan_dimension.get("id")
        evidence = read_json(archive, f"sub_reports/{dimension_id}.evidence.json")
        require(evidence.get("dimension_id") == dimension_id, f"evidence ID mismatch for {dimension_id}")
        dimensions.append(
            {
                "id": dimension_id,
                "name": plan_dimension.get("name"),
                "headline": evidence.get("headline"),
                "claimCount": len(evidence.get("claims", [])),
                "sourceCount": len(evidence.get("sources", [])),
                "sourceIds": [source.get("id") for source in evidence.get("sources", [])],
                "findings": [
                    {
                        "text": item.get("finding"),
                        "claimIds": list(item.get("claim_ids", [])),
                        "claimCount": len(item.get("claim_ids", [])),
                    }
                    for item in evidence.get("key_findings", [])
                ],
            }
        )

    content_units = [
        {"id": unit.get("id"), "title": unit.get("title")}
        for unit in outline.get("content_units", [])
    ]
    title_match = re.search(r"(?m)^#\s+(.+?)\s*$", report_markdown)
    require(title_match, "report title is missing")
    report_title = title_match.group(1)

    verdict_match = re.search(r"(?im)^\s*VERDICT:\s*([a-z]+)\s*$", final_review)
    require(verdict_match, "final review verdict is missing")
    verdict = verdict_match.group(1).lower()

    start_label = zip_timestamp_label(archive, "briefing.json")
    completion_label = zip_timestamp_label(archive, "report.md")
    require(start_label == "2026-07-14 06:03", "archive start timestamp is unexpected")
    require(completion_label == "2026-07-14 09:37", "archive completion timestamp is unexpected")

    citations = citations_data.get("citations", [])
    require(citations_data.get("total_citations") == len(citations), "citation total is inconsistent")
    citations_json = json.dumps(citations_data, ensure_ascii=False, indent=2)
    unique_source_ids = {
        source_id for dimension in dimensions for source_id in dimension["sourceIds"]
    }
    totals = {
        "dimensionCount": len(dimensions),
        "claimCount": sum(dimension["claimCount"] for dimension in dimensions),
        "sourceEntryCount": sum(dimension["sourceCount"] for dimension in dimensions),
        "uniqueSourceCount": len(unique_source_ids),
        "findingCount": sum(len(dimension["findings"]) for dimension in dimensions),
        "contentUnitCount": len(content_units),
        "citationCount": len(citations),
    }
    payload = {
        "metadata": {
            "mode": plan.get("mode"),
            "runId": run_id,
            "reportTitle": report_title,
            "startLabel": start_label,
            "completionLabel": completion_label,
            "runSpanLabel": "真实运行跨度 06:03–09:37",
            "elapsedLabel": "约 3 小时 34 分",
        },
        "totals": totals,
        "dimensions": dimensions,
        "contentUnits": content_units,
        "snapshots": make_snapshots(),
        "reportMarkdown": report_markdown,
        "citations": citations,
        "citationsJson": citations_json,
        "verdict": verdict,
    }
    validate_payload(payload)
    return payload


def main():
    script_dir = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path, default=script_dir / "index.html")
    args = parser.parse_args()

    with zipfile.ZipFile(args.archive) as archive:
        payload = build_payload(archive)

    template_path = script_dir / "template.html"
    template = template_path.read_text(encoding="utf-8")
    marker = "__ARCHIVE_DATA_BASE64__"
    require(template.count(marker) == 1, "template must contain one archive data marker")
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    encoded = base64.b64encode(payload_json.encode("utf-8")).decode("ascii")
    output = template.replace(marker, encoded)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
