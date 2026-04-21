import fs from "node:fs/promises";
import path from "node:path";

const HELPER_SKILLS = [
  "_search-common",
  "search-code",
  "search-academic",
  "search-social-cn",
  "search-social-en",
  "report-format-discovery",
  "research-report",
  "generate-image",
] as const;

const WORKSPACE_AGENTS = [
  "scout-agent",
  "plan-agent",
  "research-agent",
  "review-agent",
  "report-agent",
] as const;

type AssetPlanInput = {
  pluginRoot: string;
  openclawHome: string;
  force: boolean;
};

type SkillCopyPlan = {
  sourceName: string;
  sourceDir: string;
  targetDir: string;
  overwrite: boolean;
};

type WorkspaceCopyPlan = {
  agentId: string;
  sourceFile: string;
  targetFile: string;
  overwrite: boolean;
};

export type AssetPlan = {
  skills: {
    toCopy: SkillCopyPlan[];
    toSkip: string[];
  };
  workspaces: {
    toCopy: WorkspaceCopyPlan[];
    toSkip: string[];
  };
};

async function exists(target: string) {
  try {
    await fs.access(target);
    return true;
  } catch {
    return false;
  }
}

export async function buildAssetPlan(input: AssetPlanInput): Promise<AssetPlan> {
  const plan: AssetPlan = {
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
