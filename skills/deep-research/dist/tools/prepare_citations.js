// prepare_report_citations 工具：端口自 sensenova_claw/capabilities/tools/citation_tool.py
// 用法见 skills/deep-research/SKILL.md 的「引用预处理」段
import * as fs from "node:fs/promises";
import * as path from "node:path";
import { CitationManager } from "../lib/citation_manager.js";
function resolveAbs(raw) {
    const expanded = raw.replace(/^~(?=$|\/|\\)/, process.env.HOME ?? process.env.USERPROFILE ?? "~");
    return path.resolve(expanded);
}
function stripGeneratedBibliography(text) {
    return text.replace(/\n## 参考文献\s*[\s\S]*$/u, "").trimEnd();
}
async function runPrepareCitations(input) {
    const reportPath = resolveAbs(input.report_path);
    const subReportPaths = (input.sub_report_paths ?? []).map(resolveAbs);
    try {
        await fs.access(reportPath);
    }
    catch {
        return { success: false, error: `终稿不存在: ${reportPath}` };
    }
    const cm = new CitationManager();
    const scanned = [];
    const failed = [];
    for (const sr of subReportPaths) {
        try {
            const text = await fs.readFile(sr, "utf-8");
            cm.collectDefinitions(text, { kind: "sub", order: scanned.length });
            scanned.push(sr);
        }
        catch (err) {
            // 子报告缺失不阻塞终稿处理，但要把失败路径返回出去给调用方排查
            failed.push({ path: sr, error: err instanceof Error ? err.message : String(err) });
        }
    }
    const reportText = await fs.readFile(reportPath, "utf-8");
    cm.collectDefinitions(reportText, { kind: "final", order: subReportPaths.length });
    const cleanReportText = stripGeneratedBibliography(reportText);
    const { processed, references } = cm.processReport(cleanReportText);
    const finalText = `${processed}\n\n## 参考文献\n\n${references}\n`;
    await fs.writeFile(reportPath, finalText, "utf-8");
    const citationsPath = path.join(path.dirname(reportPath), "citations.json");
    const data = cm.exportJson();
    await fs.writeFile(citationsPath, JSON.stringify(data, null, 2), "utf-8");
    return {
        success: true,
        report_path: reportPath,
        citations_path: citationsPath,
        total_citations: data.total_citations,
        sub_reports_scanned: scanned,
        sub_reports_failed: failed,
    };
}
// OpenClaw AgentTool 描述符（参考 tlon bundled plugin 形状）
export function prepareReportCitationsTool() {
    return {
        name: "prepare_report_citations",
        label: "Deep Research: prepare citations",
        description: "处理终稿引用：收集终稿与子报告中的全部 [^key] 脚注定义，去重并统一重排为 [N] 数字引用，重写终稿参考文献列表，并生成 citations.json。所有路径必须是绝对路径。仅在终稿撰写完成且通过审查后调用。",
        parameters: {
            type: "object",
            additionalProperties: false,
            required: ["report_path", "sub_report_paths"],
            properties: {
                report_path: {
                    type: "string",
                    description: "终稿的绝对路径，例如 C:/Users/me/.openclaw/workspace/reports/2026-04-20-ai-chip-a3f2/report.md",
                },
                sub_report_paths: {
                    type: "array",
                    items: { type: "string" },
                    description: "所有子报告的绝对路径列表",
                },
            },
        },
        async execute(_toolCallId, params) {
            try {
                const result = await runPrepareCitations(params);
                return {
                    content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
                    details: result,
                };
            }
            catch (err) {
                const message = err instanceof Error ? err.message : String(err);
                return {
                    content: [{ type: "text", text: `Error: ${message}` }],
                    details: { error: true, message },
                };
            }
        },
    };
}
//# sourceMappingURL=prepare_citations.js.map