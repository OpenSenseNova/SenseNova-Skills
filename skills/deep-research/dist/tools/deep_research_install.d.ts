type DeepResearchInstallToolParams = {
    pluginRoot: string;
    openclawHome: string;
    pluginVersion: string;
};
type DeepResearchInstallInput = {
    force?: boolean;
    dryRun?: boolean;
};
export declare function deepResearchInstallTool(params: DeepResearchInstallToolParams): {
    name: string;
    label: string;
    description: string;
    parameters: {
        type: "object";
        additionalProperties: boolean;
        properties: {
            force: {
                type: string;
                description: string;
                default: boolean;
            };
            dryRun: {
                type: string;
                description: string;
                default: boolean;
            };
        };
    };
    execute(_toolCallId: string, input: DeepResearchInstallInput): Promise<{
        content: {
            type: "text";
            text: string;
        }[];
        details: {
            success: true;
            summary: import("../bootstrap/types.js").BootstrapSummary;
        } | {
            success: false;
            error: {
                code: "bootstrap_locked" | "bootstrap_failed";
                message: string;
            };
            summary: import("../bootstrap/types.js").BootstrapSummary;
        };
    }>;
};
export {};
