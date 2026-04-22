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
export declare function buildAssetPlan(input: AssetPlanInput): Promise<AssetPlan>;
export {};
