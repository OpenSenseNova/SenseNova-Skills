const DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3";
function readTrimmedEnv(name) {
    const value = process.env[name]?.trim();
    return value && value.length > 0 ? value : undefined;
}
export function readVolcengineEnv() {
    return {
        apiKey: readTrimmedEnv("ARK_API_KEY") || readTrimmedEnv("VOLCANO_ENGINE_API_KEY"),
        baseUrl: (readTrimmedEnv("ARK_BASE_URL") || DEFAULT_BASE_URL).replace(/\/+$/, ""),
    };
}
//# sourceMappingURL=volcengine_env.js.map