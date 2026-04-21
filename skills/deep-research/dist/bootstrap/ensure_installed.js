import fs from "node:fs/promises";
import path from "node:path";
import { buildAssetPlan } from "./copy_assets.js";
import { mergeDeepResearchConfig } from "./merge_config.js";
import { acquireBootstrapLock, readBootstrapState, releaseBootstrapLock, writeBootstrapState, } from "./state.js";
function emptySummary() {
    return {
        skills: { copied: [], skipped: [], overwritten: [] },
        workspaces: { copied: [], skipped: [], overwritten: [] },
        config: { updated: false, changes: [] },
    };
}
async function copySkill(plan) {
    await fs.mkdir(path.dirname(plan.targetDir), { recursive: true });
    if (plan.overwrite) {
        await fs.rm(plan.targetDir, { recursive: true, force: true });
    }
    await fs.cp(plan.sourceDir, plan.targetDir, { recursive: true });
}
async function copyWorkspace(plan) {
    await fs.mkdir(path.dirname(plan.targetFile), { recursive: true });
    await fs.copyFile(plan.sourceFile, plan.targetFile);
}
export async function ensureInstalled(params) {
    const lock = await acquireBootstrapLock(params.openclawHome);
    const summary = emptySummary();
    if (!lock.acquired) {
        return {
            success: false,
            error: { code: "bootstrap_locked", message: "bootstrap already running" },
            summary,
        };
    }
    try {
        const previousState = await readBootstrapState(params.openclawHome);
        const versionChanged = previousState?.success === true && previousState.pluginVersion !== params.pluginVersion;
        const shouldOverwriteManagedAssets = params.force || versionChanged;
        const assetPlan = await buildAssetPlan({
            pluginRoot: params.pluginRoot,
            openclawHome: params.openclawHome,
            force: shouldOverwriteManagedAssets,
        });
        summary.skills.skipped = [...assetPlan.skills.toSkip];
        summary.workspaces.skipped = [...assetPlan.workspaces.toSkip];
        if (!params.dryRun) {
            for (const skill of assetPlan.skills.toCopy) {
                await copySkill(skill);
            }
            for (const workspace of assetPlan.workspaces.toCopy) {
                await copyWorkspace(workspace);
            }
        }
        for (const skill of assetPlan.skills.toCopy) {
            (skill.overwrite ? summary.skills.overwritten : summary.skills.copied).push(skill.sourceName);
        }
        for (const workspace of assetPlan.workspaces.toCopy) {
            (workspace.overwrite ? summary.workspaces.overwritten : summary.workspaces.copied).push(workspace.agentId);
        }
        const configPath = path.join(params.openclawHome, "openclaw.json");
        let currentConfig = {};
        try {
            currentConfig = JSON.parse(await fs.readFile(configPath, "utf8"));
        }
        catch (error) {
            if (error.code !== "ENOENT") {
                throw error;
            }
        }
        const merged = mergeDeepResearchConfig(currentConfig, { force: params.force });
        summary.config = {
            updated: merged.changes.length > 0,
            changes: merged.changes,
        };
        if (!params.dryRun && merged.changes.length > 0) {
            await fs.mkdir(path.dirname(configPath), { recursive: true });
            await fs.writeFile(configPath, JSON.stringify(merged.config, null, 2) + "\n", "utf8");
        }
        if (!params.dryRun) {
            await writeBootstrapState(params.openclawHome, {
                mode: params.mode,
                success: true,
                pluginVersion: params.pluginVersion,
                timestamp: new Date().toISOString(),
                summary,
            });
        }
        return { success: true, summary };
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        await writeBootstrapState(params.openclawHome, {
            mode: params.mode,
            success: false,
            pluginVersion: params.pluginVersion,
            timestamp: new Date().toISOString(),
            summary,
            errorMessage: message,
        });
        return {
            success: false,
            error: { code: "bootstrap_failed", message },
            summary,
        };
    }
    finally {
        await releaseBootstrapLock(lock);
    }
}
//# sourceMappingURL=ensure_installed.js.map