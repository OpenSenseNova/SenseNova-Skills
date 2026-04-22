import { ensureInstalled } from "../bootstrap/ensure_installed.js";

type DeepResearchInstallToolParams = {
  pluginRoot: string;
  openclawHome: string;
  pluginVersion: string;
};

type DeepResearchInstallInput = {
  force?: boolean;
  dryRun?: boolean;
};

export function deepResearchInstallTool(params: DeepResearchInstallToolParams) {
  return {
    name: "deep_research_install",
    label: "Deep Research: install or repair",
    description:
      "Bootstrap or repair the Deep Research plugin assets under ~/.openclaw, including helper skills, agent workspaces, and openclaw.json config.",
    parameters: {
      type: "object" as const,
      additionalProperties: false,
      properties: {
        force: {
          type: "boolean",
          description: "Overwrite existing Deep Research-managed skill and workspace files.",
          default: false,
        },
        dryRun: {
          type: "boolean",
          description: "Preview changes without writing files.",
          default: false,
        },
      },
    },
    async execute(_toolCallId: string, input: DeepResearchInstallInput) {
      const result = await ensureInstalled({
        pluginRoot: params.pluginRoot,
        openclawHome: params.openclawHome,
        mode: "manual",
        force: input.force === true,
        dryRun: input.dryRun === true,
        pluginVersion: params.pluginVersion,
      });

      return {
        content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
        details: result,
      };
    },
  };
}
