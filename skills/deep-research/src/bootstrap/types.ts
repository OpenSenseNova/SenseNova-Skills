export type BootstrapMode = "auto" | "manual";

export type BootstrapSummary = {
  skills: {
    copied: string[];
    skipped: string[];
    overwritten: string[];
  };
  workspaces: {
    copied: string[];
    skipped: string[];
    overwritten: string[];
  };
  config: {
    updated: boolean;
    changes: string[];
  };
};

export type BootstrapState = {
  mode: BootstrapMode;
  success: boolean;
  pluginVersion: string;
  timestamp: string;
  summary: BootstrapSummary;
  errorMessage?: string;
};

export type BootstrapLockHandle =
  | {
      acquired: true;
      path: string;
    }
  | {
      acquired: false;
      path: string;
      reason: "already_locked";
    };
