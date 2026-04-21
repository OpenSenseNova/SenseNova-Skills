import os from "node:os";
import path from "node:path";
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import type { OpenClawPluginConfigSchema } from "openclaw/plugin-sdk/plugin-entry";
import { ensureInstalled } from "./bootstrap/ensure_installed.js";
import { buildVolcengineImageProvider } from "./providers/volcengine_image_provider.js";
import { deepResearchInstallTool } from "./tools/deep_research_install.js";
import { prepareReportCitationsTool } from "./tools/prepare_citations.js";

const configSchema: OpenClawPluginConfigSchema = {
  jsonSchema: {
    type: "object",
    additionalProperties: true,
    properties: {
      subagent: {
        type: "object",
        properties: { allowModelOverride: { type: "boolean" } },
      },
      reports: {
        type: "object",
        properties: { rootDir: { type: "string" } },
      },
    },
  },
  safeParse(value: unknown) {
    if (value === undefined || value === null) {
      return { success: true, data: {} };
    }
    if (typeof value !== "object" || Array.isArray(value)) {
      return {
        success: false,
        error: { issues: [{ path: [], message: "expected config object" }] },
      };
    }
    return { success: true, data: value };
  },
};

function resolvePluginRoot() {
  return path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
}

function resolveOpenClawHome() {
  return process.env.OPENCLAW_STATE_DIR || path.join(os.homedir(), ".openclaw");
}

export default definePluginEntry({
  id: "deep-research",
  name: "Deep Research",
  description: "多 agent 深度研究工作流（controller skill + 5 专家 agent）",
  configSchema,

  register(api) {
    const pluginRoot = resolvePluginRoot();
    const openclawHome = resolveOpenClawHome();
    const pluginVersion = "0.1.0";

    api.registerTool(prepareReportCitationsTool());
    api.registerTool(
      deepResearchInstallTool({
        pluginRoot,
        openclawHome,
        pluginVersion,
      }),
    );
    api.registerImageGenerationProvider(buildVolcengineImageProvider());

    void ensureInstalled({
      pluginRoot,
      openclawHome,
      mode: "auto",
      force: false,
      dryRun: false,
      pluginVersion,
    }).catch((error) => {
      api.logger?.warn?.(
        `deep-research bootstrap failed: ${error instanceof Error ? error.message : String(error)}`,
      );
    });

    api.logger?.info?.(
      "deep-research plugin registered (prepare_report_citations + volcengine-image provider, bootstrap)",
    );
  },
});
