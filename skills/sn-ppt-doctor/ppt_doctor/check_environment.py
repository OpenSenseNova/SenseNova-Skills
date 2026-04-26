#!/usr/bin/env python3
"""sn-ppt-doctor: environment diagnostic for the PPT skill family.

Single-file script runnable directly:

    python skills/sn-ppt-doctor/ppt_doctor/check_environment.py [--non-interactive] [--env-path PATH]

No package imports across modules, no `-m`, no PYTHONPATH. Mirrors sn-image-doctor's
self-contained design so OpenClaw can invoke it via a plain file path.

Sections:
    1. CheckResult dataclass + shared helpers
    2. Hard checks   (SN_LM_API_KEY, SN_LM_BASE_URL, SN_API_KEY,
                      SN_IMAGE_BASE discovery, sn_agent_runner executable,
                      Node >= 18)
    3. Soft checks   (PPT_DECK_ROOT writable, optional env vars,
                      export_pptx node_modules, Python deps)
    4. Aggregator    (run_all_checks)
    5. Interactive .env filler
    6. CLI main()
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


_SUBPROCESS_TIMEOUT = 5
_MIN_NODE_MAJOR = 18


def _load_dotenv_if_available() -> list[Path]:
    """Load .env into os.environ from a few well-known locations.

    Search order (each loaded, later ones DO NOT override existing values):
        1. <repo_root>/.env           (where this script sits at <repo>/skills/sn-ppt-doctor/ppt_doctor/check_environment.py)
        2. <repo_root>/skills/.env    (user may place it here)
        3. cwd / .env                 (python-dotenv default)

    Returns list of paths that were actually loaded (for display).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return []
    script = Path(__file__).resolve()
    repo_root = script.parents[3]
    loaded: list[Path] = []
    for candidate in (repo_root / ".env", repo_root / "skills" / ".env", Path.cwd() / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)
            loaded.append(candidate)
    return loaded


_LOADED_DOTENV_PATHS = _load_dotenv_if_available()


# ---------------------------------------------------------------------------
# 1. CheckResult + shared helpers
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    severity: Literal["hard", "soft"]
    passed: bool
    detail: str


def _env(name: str) -> str | None:
    val = os.environ.get(name, "").strip()
    return val or None


def _find_sn_agent_runner() -> Path | None:
    """Three-level discovery for sn_agent_runner.py.

    Level 1: SN_IMAGE_BASE env var -> <path>/scripts/sn_agent_runner.py
              If the var is set but the runner isn't there, stop (do not fall through).
    Level 2: TODO - openclaw registry (not yet implemented)
    Level 3: repo-relative skills/sn-image-base/scripts/sn_agent_runner.py
              Only tried when SN_IMAGE_BASE is NOT set at all.
    """
    base_env = _env("SN_IMAGE_BASE")
    if base_env is not None:
        candidate = Path(base_env) / "scripts" / "sn_agent_runner.py"
        return candidate if candidate.exists() else None

    repo_candidate = Path.cwd() / "skills" / "sn-image-base" / "scripts" / "sn_agent_runner.py"
    if repo_candidate.exists():
        return repo_candidate

    return None


# ---------------------------------------------------------------------------
# 2. Hard checks
# ---------------------------------------------------------------------------


def check_u1_lm_api_key() -> CheckResult:
    val = _env("SN_LM_API_KEY")
    return CheckResult(
        name="SN_LM_API_KEY",
        severity="hard",
        passed=val is not None,
        detail="set" if val else "SN_LM_API_KEY is required for LLM/VLM calls; set it or run /skill sn-ppt-doctor to configure interactively",
    )


def check_u1_lm_base_url() -> CheckResult:
    val = _env("SN_LM_BASE_URL")
    return CheckResult(
        name="SN_LM_BASE_URL",
        severity="hard",
        passed=val is not None,
        detail="set" if val else "SN_LM_BASE_URL is required for LLM/VLM calls; set it to the base URL of your LLM service",
    )


def check_u1_api_key() -> CheckResult:
    val = _env("SN_API_KEY")
    return CheckResult(
        name="SN_API_KEY",
        severity="hard",
        passed=val is not None,
        detail="set" if val else "SN_API_KEY is required for image generation calls; set it to your U1 API key",
    )


def check_sn_image_base_discoverable() -> CheckResult:
    runner = _find_sn_agent_runner()
    if runner is not None:
        return CheckResult(
            name="SN_IMAGE_BASE",
            severity="hard",
            passed=True,
            detail=f"sn_agent_runner.py found at {runner}",
        )
    return CheckResult(
        name="SN_IMAGE_BASE",
        severity="hard",
        passed=False,
        detail=(
            "sn_agent_runner.py not found. Set SN_IMAGE_BASE to the sn-image-base skill root, "
            "or run this check from the repo root where skills/sn-image-base/ is a sibling."
        ),
    )


def check_sn_agent_runner_executable() -> CheckResult:
    runner = _find_sn_agent_runner()
    if runner is None:
        return CheckResult(
            name="OPENCLAW_RUNNER",
            severity="hard",
            passed=False,
            detail="sn_agent_runner.py not found; see check_sn_image_base_discoverable",
        )
    skill_root = str(runner.parent.parent)
    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join([skill_root, existing_pp]) if existing_pp else skill_root
    try:
        result = subprocess.run(
            [sys.executable, str(runner), "--help"],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            env=env,
        )
        if result.returncode == 0:
            return CheckResult(
                name="OPENCLAW_RUNNER",
                severity="hard",
                passed=True,
                detail=f"--help exited 0 for {runner}",
            )
        return CheckResult(
            name="OPENCLAW_RUNNER",
            severity="hard",
            passed=False,
            detail=f"--help exited {result.returncode}: {result.stderr.strip()[:200]}",
        )
    except FileNotFoundError:
        return CheckResult(
            name="OPENCLAW_RUNNER",
            severity="hard",
            passed=False,
            detail="python interpreter not found",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="OPENCLAW_RUNNER",
            severity="hard",
            passed=False,
            detail=f"--help timed out after {_SUBPROCESS_TIMEOUT} seconds",
        )


def check_node_version() -> CheckResult:
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        raw = result.stdout.strip()
        if result.returncode != 0 or not raw.startswith("v"):
            return CheckResult(
                name="NODE_VERSION",
                severity="hard",
                passed=False,
                detail=f"node --version returned unexpected output: {raw!r}",
            )
        parts = raw.lstrip("v").split(".")
        major = int(parts[0])
        passed = major >= _MIN_NODE_MAJOR
        return CheckResult(
            name="NODE_VERSION",
            severity="hard",
            passed=passed,
            detail=raw if passed else f"node {raw} found but >= {_MIN_NODE_MAJOR} required",
        )
    except FileNotFoundError:
        return CheckResult(
            name="NODE_VERSION",
            severity="hard",
            passed=False,
            detail="node not found in PATH",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="NODE_VERSION",
            severity="hard",
            passed=False,
            detail=f"node --version timed out after {_SUBPROCESS_TIMEOUT} seconds",
        )
    except (ValueError, IndexError) as exc:
        return CheckResult(
            name="NODE_VERSION",
            severity="hard",
            passed=False,
            detail=f"could not parse node version: {exc}",
        )


# ---------------------------------------------------------------------------
# 3. Soft checks
# ---------------------------------------------------------------------------


def check_ppt_deck_root_writable() -> CheckResult:
    """Verify that $(cwd)/ppt_decks/ can be created/written.

    Decks are always created under `$(cwd)/ppt_decks/` — in OpenClaw that
    resolves to the agent workspace. PPT_DECK_ROOT env var is no longer
    consulted (removed to avoid drift; see sn-ppt-entry SKILL.md step 4).
    """
    cwd = Path.cwd()
    target = cwd / "ppt_decks"
    try:
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target, delete=True):
            pass
        return CheckResult(
            name="PPT_DECK_ROOT",
            severity="soft",
            passed=True,
            detail=f"{target} is writable",
        )
    except OSError as exc:
        return CheckResult(
            name="PPT_DECK_ROOT",
            severity="soft",
            passed=False,
            detail=f"{target} is not creatable/writable: {exc}",
        )


_OPTIONAL_VARS = [
    "SN_IMAGE_GEN_BASE_URL",
    "SN_BASE_URL",
    "SN_IMAGE_GEN_MODEL",
    # NOTE: PPT_DECK_ROOT removed — deck_dir is now always $(cwd)/ppt_decks/
    "SN_IMAGE_GEN_MODEL_TYPE",
    "VLM_API_KEY",
    "VLM_BASE_URL",
    "VLM_MODEL",
    "VLM_TYPE",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_TYPE",
    "SN_IMAGE_BASE",
]


def check_optional_env_vars() -> CheckResult:
    parts = []
    for var in _OPTIONAL_VARS:
        val = _env(var)
        parts.append(f"{var}={'<set>' if val else 'unset'}")
    return CheckResult(
        name="OPTIONAL_ENV_VARS",
        severity="soft",
        passed=True,
        detail="; ".join(parts),
    )


def check_export_pptx_node_modules(base: Path | None = None) -> CheckResult:
    if base is None:
        # check_environment.py sits at skills/sn-ppt-doctor/ppt_doctor/check_environment.py
        # -> parents[3] = repo root
        repo_root = Path(__file__).resolve().parents[3]
        base = repo_root / "skills" / "sn-ppt-standard" / "scripts" / "export_pptx"

    node_modules = base / "node_modules"
    if node_modules.exists():
        return CheckResult(
            name="EXPORT_PPTX_NODE_MODULES",
            severity="soft",
            passed=True,
            detail=f"node_modules found at {node_modules}",
        )
    return CheckResult(
        name="EXPORT_PPTX_NODE_MODULES",
        severity="soft",
        passed=False,
        detail=f"node_modules not found at {node_modules}; run `npm install` in {base}",
    )


def check_python_deps() -> CheckResult:
    checks = [
        ("pypdf", "pypdf"),
        ("python-docx", "docx"),
        ("python-pptx", "pptx"),
    ]
    parts = []
    missing: list[str] = []
    for display_name, module_name in checks:
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            missing.append(display_name)
            parts.append(f"{display_name}: missing")
        else:
            parts.append(f"{display_name}: installed")
    detail = "; ".join(parts)
    if missing:
        detail += f"  (install with: pip install {' '.join(missing)})"
    return CheckResult(
        name="PYTHON_DEPS",
        severity="soft",
        passed=True,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# 4. Aggregator
# ---------------------------------------------------------------------------


def run_all_checks() -> list[CheckResult]:
    return [
        check_u1_lm_api_key(),
        check_u1_lm_base_url(),
        check_u1_api_key(),
        check_sn_image_base_discoverable(),
        check_sn_agent_runner_executable(),
        check_node_version(),
        check_ppt_deck_root_writable(),
        check_optional_env_vars(),
        check_export_pptx_node_modules(),
        check_python_deps(),
    ]


# ---------------------------------------------------------------------------
# 5. Interactive .env filler
# ---------------------------------------------------------------------------


REQUIRED = [
    ("SN_LM_API_KEY", "LLM/VLM API key"),
    ("SN_LM_BASE_URL", "LLM/VLM endpoint URL"),
    ("SN_API_KEY", "Image generation API key"),
]


@dataclass
class FillResult:
    written: bool
    path: Path | None


def interactive_fill_env(env_path: Path, non_interactive: bool = False) -> FillResult:
    missing: list[tuple[str, str]] = [
        (name, desc) for name, desc in REQUIRED if not os.environ.get(name, "").strip()
    ]
    if not missing:
        return FillResult(written=False, path=None)
    if non_interactive:
        return FillResult(written=False, path=None)

    lines: list[str] = []
    for name, desc in missing:
        value = input(f"{name} ({desc}): ").strip()
        if value:
            lines.append(f"{name}={value}")

    if not lines:
        return FillResult(written=False, path=None)

    env_path.parent.mkdir(parents=True, exist_ok=True)
    existing = env_path.read_text() if env_path.exists() else ""
    with env_path.open("w", encoding="utf-8") as f:
        if existing:
            f.write(existing)
            if not existing.endswith("\n"):
                f.write("\n")
        f.write("\n".join(lines) + "\n")
    return FillResult(written=True, path=env_path)


# ---------------------------------------------------------------------------
# 6. CLI main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sn-ppt-doctor")
    parser.add_argument("--non-interactive", action="store_true", help="Skip interactive .env prompts")
    parser.add_argument("--env-path", type=Path, default=Path.cwd() / ".env")
    args = parser.parse_args(argv)

    print("== sn-ppt-doctor: environment check ==\n")
    if _LOADED_DOTENV_PATHS:
        print("Loaded .env:")
        for p in _LOADED_DOTENV_PATHS:
            print(f"  - {p}")
        print()
    else:
        print("(No .env file loaded. Relying on OS environment variables.)\n")
    results = run_all_checks()
    hard_failed = [r for r in results if r.severity == "hard" and not r.passed]

    for r in results:
        tag = "OK  " if r.passed else ("FAIL" if r.severity == "hard" else "WARN")
        print(f"[{tag}] [{r.severity}] {r.name}: {r.detail}")

    if hard_failed:
        print("\nSome required checks failed. Entering interactive fill...\n")
        fill = interactive_fill_env(env_path=args.env_path, non_interactive=args.non_interactive)
        if fill.written:
            print(f"\nWrote .env at {fill.path}. Please re-run sn-ppt-doctor to verify.")
        else:
            print("\nNothing written. Re-run after fixing environment manually.")
        return 1

    print("\nAll hard checks passed. PPT family is ready to use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
