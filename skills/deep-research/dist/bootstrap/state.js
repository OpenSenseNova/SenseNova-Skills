import fs from "node:fs/promises";
import path from "node:path";
const PLUGIN_STATE_DIR = ["plugins", "deep-research"];
const LOCK_FILE = "bootstrap.lock";
const STATE_FILE = "bootstrap-state.json";
function resolveStateDir(openclawHome) {
    return path.join(openclawHome, ...PLUGIN_STATE_DIR);
}
function resolveLockPath(openclawHome) {
    return path.join(resolveStateDir(openclawHome), LOCK_FILE);
}
function resolveStatePath(openclawHome) {
    return path.join(resolveStateDir(openclawHome), STATE_FILE);
}
export async function acquireBootstrapLock(openclawHome) {
    const stateDir = resolveStateDir(openclawHome);
    const lockPath = resolveLockPath(openclawHome);
    await fs.mkdir(stateDir, { recursive: true });
    try {
        const handle = await fs.open(lockPath, "wx");
        await handle.close();
        return { acquired: true, path: lockPath };
    }
    catch (error) {
        if (error.code === "EEXIST") {
            return { acquired: false, path: lockPath, reason: "already_locked" };
        }
        throw error;
    }
}
export async function releaseBootstrapLock(lock) {
    if (!lock.acquired) {
        return;
    }
    await fs.rm(lock.path, { force: true });
}
export async function writeBootstrapState(openclawHome, state) {
    const statePath = resolveStatePath(openclawHome);
    await fs.mkdir(path.dirname(statePath), { recursive: true });
    await fs.writeFile(statePath, JSON.stringify(state, null, 2) + "\n", "utf8");
}
export async function readBootstrapState(openclawHome) {
    const statePath = resolveStatePath(openclawHome);
    try {
        const content = await fs.readFile(statePath, "utf8");
        return JSON.parse(content);
    }
    catch (error) {
        if (error.code === "ENOENT") {
            return null;
        }
        throw error;
    }
}
//# sourceMappingURL=state.js.map