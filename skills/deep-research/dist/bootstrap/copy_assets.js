import fs from "node:fs/promises";
import path from "node:path";
const HELPER_SKILLS = [
    "deep-research",
    "_search-common",
    "search-code",
    "search-academic",
    "search-social-cn",
    "search-social-en",
    "report-format-discovery",
    "research-report",
    "generate-image",
];
const WORKSPACE_AGENTS = [
    "scout-agent",
    "plan-agent",
    "research-agent",
    "review-agent",
    "report-agent",
];
async function exists(target) {
    try {
        await fs.access(target);
        return true;
    }
    catch {
        return false;
    }
}
export async function buildAssetPlan(input) {
    const plan = {
        skills: { toCopy: [], toSkip: [] },
        workspaces: { toCopy: [], toSkip: [] },
    };
    for (const skill of HELPER_SKILLS) {
        const sourceDir = path.join(input.pluginRoot, "skills", skill);
        if (!(await exists(sourceDir))) {
            continue;
        }
        const targetDir = path.join(input.openclawHome, "skills", skill);
        const targetExists = await exists(targetDir);
        if (targetExists && !input.force) {
            plan.skills.toSkip.push(skill);
            continue;
        }
        plan.skills.toCopy.push({
            sourceName: skill,
            sourceDir,
            targetDir,
            overwrite: targetExists,
        });
    }
    for (const agentId of WORKSPACE_AGENTS) {
        const sourceFile = path.join(input.pluginRoot, "workspaces", agentId, "AGENTS.md");
        if (!(await exists(sourceFile))) {
            continue;
        }
        const targetFile = path.join(input.openclawHome, `workspace-${agentId}`, "AGENTS.md");
        const targetExists = await exists(targetFile);
        if (targetExists && !input.force) {
            plan.workspaces.toSkip.push(agentId);
            continue;
        }
        plan.workspaces.toCopy.push({
            agentId,
            sourceFile,
            targetFile,
            overwrite: targetExists,
        });
    }
    return plan;
}
//# sourceMappingURL=copy_assets.js.map