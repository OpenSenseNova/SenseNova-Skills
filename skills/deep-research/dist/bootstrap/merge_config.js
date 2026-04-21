const PLUGIN_CONFIG = {
    agents: {
        defaults: {
            subagents: {
                maxSpawnDepth: 1,
                maxConcurrent: 8,
                runTimeoutSeconds: 1800,
                allowAgents: [
                    "scout-agent",
                    "plan-agent",
                    "research-agent",
                    "review-agent",
                    "report-agent",
                ],
            },
        },
        list: [
            {
                id: "scout-agent",
                workspace: "~/.openclaw/workspace-scout-agent",
                skills: ["search-code", "search-academic", "search-social-cn", "search-social-en"],
            },
            {
                id: "plan-agent",
                workspace: "~/.openclaw/workspace-plan-agent",
                skills: [
                    "search-code",
                    "search-academic",
                    "search-social-cn",
                    "search-social-en",
                    "report-format-discovery",
                ],
            },
            {
                id: "research-agent",
                workspace: "~/.openclaw/workspace-research-agent",
                skills: [
                    "search-code",
                    "search-academic",
                    "search-social-cn",
                    "search-social-en",
                ],
            },
            {
                id: "review-agent",
                workspace: "~/.openclaw/workspace-review-agent",
                skills: [],
            },
            {
                id: "report-agent",
                workspace: "~/.openclaw/workspace-report-agent",
                skills: ["research-report", "generate-image"],
            },
        ],
    },
    plugins: {
        entries: {
            "deep-research": {
                enabled: true,
                config: {
                    subagent: { allowModelOverride: false },
                    reports: { rootDir: "" },
                },
            },
        },
    },
};
function ensureObject(root, ...keys) {
    let current = root;
    for (const key of keys) {
        const existing = current[key];
        if (!existing || typeof existing !== "object" || Array.isArray(existing)) {
            current[key] = {};
        }
        current = current[key];
    }
    return current;
}
function mergeAllowAgents(existing, incoming) {
    const seen = new Set(existing ?? []);
    const merged = [...(existing ?? [])];
    for (const item of incoming) {
        if (seen.has(item)) {
            continue;
        }
        seen.add(item);
        merged.push(item);
    }
    return merged;
}
function upsertAgentsList(existing, force) {
    const result = [...(existing ?? [])];
    const indexById = new Map();
    for (const [index, entry] of result.entries()) {
        if (entry && typeof entry === "object" && typeof entry.id === "string") {
            indexById.set(entry.id, index);
        }
    }
    const changes = [];
    for (const incoming of PLUGIN_CONFIG.agents.list) {
        const currentIndex = indexById.get(incoming.id);
        if (currentIndex === undefined) {
            result.push({ ...incoming, skills: [...incoming.skills] });
            changes.push(`add:${incoming.id}`);
            continue;
        }
        if (!force) {
            continue;
        }
        result[currentIndex] = { ...incoming, skills: [...incoming.skills] };
        changes.push(`overwrite:${incoming.id}`);
    }
    return { list: result, changes };
}
function mergePluginEntry(existing) {
    const incoming = PLUGIN_CONFIG.plugins.entries["deep-research"];
    if (!existing || typeof existing !== "object" || Array.isArray(existing)) {
        return {
            enabled: incoming.enabled,
            config: {
                subagent: { ...incoming.config.subagent },
                reports: { ...incoming.config.reports },
            },
        };
    }
    const merged = { ...existing };
    if (!("enabled" in merged)) {
        merged.enabled = true;
    }
    const mergedConfig = ensureObject(merged, "config");
    for (const [section, defaults] of Object.entries(incoming.config)) {
        const targetSection = ensureObject(mergedConfig, section);
        for (const [key, value] of Object.entries(defaults)) {
            if (!(key in targetSection)) {
                targetSection[key] = value;
            }
        }
    }
    return merged;
}
export function mergeDeepResearchConfig(input, options) {
    const config = structuredClone(input);
    const changes = [];
    const subagents = ensureObject(config, "agents", "defaults", "subagents");
    const defaults = PLUGIN_CONFIG.agents.defaults.subagents;
    for (const key of ["maxSpawnDepth", "maxConcurrent", "runTimeoutSeconds"]) {
        if (!(key in subagents)) {
            subagents[key] = defaults[key];
            changes.push(`set agents.defaults.subagents.${key}=${String(subagents[key])}`);
        }
    }
    const beforeAllow = Array.isArray(subagents.allowAgents) ? [...subagents.allowAgents] : [];
    const afterAllow = mergeAllowAgents(beforeAllow, defaults.allowAgents);
    if (beforeAllow.join("\u0000") !== afterAllow.join("\u0000")) {
        subagents.allowAgents = afterAllow;
        changes.push(`merge agents.defaults.subagents.allowAgents -> ${afterAllow.join(",")}`);
    }
    const agents = ensureObject(config, "agents");
    const currentList = Array.isArray(agents.list) ? agents.list : [];
    const mergedAgents = upsertAgentsList(currentList, options.force);
    agents.list = mergedAgents.list;
    changes.push(...mergedAgents.changes.map((change) => `agents.list: ${change}`));
    const entries = ensureObject(config, "plugins", "entries");
    const existingEntry = entries["deep-research"];
    const mergedEntry = mergePluginEntry(existingEntry);
    if (JSON.stringify(existingEntry) !== JSON.stringify(mergedEntry)) {
        entries["deep-research"] = mergedEntry;
        changes.push("plugins.entries.deep-research: set/updated");
    }
    return { config, changes };
}
//# sourceMappingURL=merge_config.js.map