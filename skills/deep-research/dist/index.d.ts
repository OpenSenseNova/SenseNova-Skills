import type { OpenClawPluginConfigSchema } from "openclaw/plugin-sdk/plugin-entry";
declare const _default: {
    id: string;
    name: string;
    description: string;
    configSchema: OpenClawPluginConfigSchema;
    register: NonNullable<import("openclaw/plugin-sdk/plugin-entry").OpenClawPluginDefinition["register"]>;
} & Pick<import("openclaw/plugin-sdk/plugin-entry").OpenClawPluginDefinition, "kind" | "reload" | "nodeHostCommands" | "securityAuditCollectors">;
export default _default;
