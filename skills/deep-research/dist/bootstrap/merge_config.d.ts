type JsonObject = Record<string, any>;
type MergeOptions = {
    force: boolean;
};
type MergeResult = {
    config: JsonObject;
    changes: string[];
};
export declare function mergeDeepResearchConfig(input: JsonObject, options: MergeOptions): MergeResult;
export {};
