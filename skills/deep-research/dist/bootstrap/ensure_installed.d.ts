import type { BootstrapMode, BootstrapSummary } from "./types.js";
type EnsureInstalledParams = {
    pluginRoot: string;
    openclawHome: string;
    mode: BootstrapMode;
    force: boolean;
    dryRun: boolean;
    pluginVersion: string;
};
type EnsureInstalledResult = {
    success: true;
    summary: BootstrapSummary;
} | {
    success: false;
    error: {
        code: "bootstrap_locked" | "bootstrap_failed";
        message: string;
    };
    summary: BootstrapSummary;
};
export declare function ensureInstalled(params: EnsureInstalledParams): Promise<EnsureInstalledResult>;
export {};
