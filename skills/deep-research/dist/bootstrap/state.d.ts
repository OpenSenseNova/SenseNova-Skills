import type { BootstrapLockHandle, BootstrapState } from "./types.js";
export declare function acquireBootstrapLock(openclawHome: string): Promise<BootstrapLockHandle>;
export declare function releaseBootstrapLock(lock: BootstrapLockHandle): Promise<void>;
export declare function writeBootstrapState(openclawHome: string, state: BootstrapState): Promise<void>;
export declare function readBootstrapState(openclawHome: string): Promise<BootstrapState | null>;
