"""Individual environment checks for ppt-doctor.

Each function returns a CheckResult describing one aspect of the environment.
The caller aggregates results into a report.
"""
from __future__ import annotations

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


@dataclass
class CheckResult:
    name: str
    severity: Literal["hard", "soft"]
    passed: bool
    detail: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _env(name: str) -> str | None:
    val = os.environ.get(name, "").strip()
    return val or None


def _find_openclaw_runner() -> Path | None:
    """Three-level discovery for openclaw_runner.py.

    Level 1: U1_IMAGE_BASE env var → <path>/u1_image_base/openclaw_runner.py
              If the var is set but the runner isn't there, stop (do not fall through).
    Level 2: TODO — openclaw registry (not yet implemented)
    Level 3: repo-relative skills/u1-image-base/u1_image_base/openclaw_runner.py
              Only tried when U1_IMAGE_BASE is NOT set at all.
    """
    # Level 1: env var takes precedence; if set, do not fall through to other levels
    base_env = _env("U1_IMAGE_BASE")
    if base_env is not None:
        candidate = Path(base_env) / "u1_image_base" / "openclaw_runner.py"
        return candidate if candidate.exists() else None

    # Level 3: repo-relative from cwd (only when env var absent)
    repo_candidate = Path.cwd() / "skills" / "u1-image-base" / "u1_image_base" / "openclaw_runner.py"
    if repo_candidate.exists():
        return repo_candidate

    return None


# ---------------------------------------------------------------------------
# Hard checks
# ---------------------------------------------------------------------------

def check_u1_lm_api_key() -> CheckResult:
    val = _env("U1_LM_API_KEY")
    return CheckResult(
        name="U1_LM_API_KEY",
        severity="hard",
        passed=val is not None,
        detail="set" if val else "U1_LM_API_KEY is required for LLM/VLM calls; set it or run /skill ppt-doctor to configure interactively",
    )


def check_u1_lm_base_url() -> CheckResult:
    val = _env("U1_LM_BASE_URL")
    return CheckResult(
        name="U1_LM_BASE_URL",
        severity="hard",
        passed=val is not None,
        detail="set" if val else "U1_LM_BASE_URL is required for LLM/VLM calls; set it to the base URL of your LLM service",
    )


def check_u1_api_key() -> CheckResult:
    val = _env("U1_API_KEY")
    return CheckResult(
        name="U1_API_KEY",
        severity="hard",
        passed=val is not None,
        detail="set" if val else "U1_API_KEY is required for image generation calls; set it to your U1 API key",
    )


def check_u1_image_base_discoverable() -> CheckResult:
    runner = _find_openclaw_runner()
    if runner is not None:
        return CheckResult(
            name="U1_IMAGE_BASE",
            severity="hard",
            passed=True,
            detail=f"openclaw_runner.py found at {runner}",
        )
    return CheckResult(
        name="U1_IMAGE_BASE",
        severity="hard",
        passed=False,
        detail=(
            "openclaw_runner.py not found. Set U1_IMAGE_BASE to the u1-image-base skill root, "
            "or run this check from the repo root where skills/u1-image-base/ is a sibling."
        ),
    )


def check_openclaw_runner_executable() -> CheckResult:
    runner = _find_openclaw_runner()
    if runner is None:
        return CheckResult(
            name="OPENCLAW_RUNNER",
            severity="hard",
            passed=False,
            detail="openclaw_runner.py not found; see check_u1_image_base_discoverable",
        )
    # The runner's package root is the parent of u1_image_base/ (i.e. runner.parent.parent)
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
        raw = result.stdout.strip()  # e.g. "v20.11.0"
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
# Soft checks
# ---------------------------------------------------------------------------

def check_ppt_deck_root_writable() -> CheckResult:
    """Check that PPT_DECK_ROOT (or cwd fallback) is writable."""
    deck_root_env = _env("PPT_DECK_ROOT")

    if deck_root_env:
        target = Path(deck_root_env)
        # Probe writability by creating and deleting a temp file via NamedTemporaryFile
        try:
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
                detail=f"{target} is not writable: {exc}",
            )
    else:
        # Fallback: use os.access to check cwd writability without mutation
        cwd = Path.cwd()
        if os.access(cwd, os.W_OK):
            return CheckResult(
                name="PPT_DECK_ROOT",
                severity="soft",
                passed=True,
                detail=f"cwd {cwd} is writable (PPT_DECK_ROOT not set; will default to cwd/ppt_decks/)",
            )
        return CheckResult(
            name="PPT_DECK_ROOT",
            severity="soft",
            passed=False,
            detail=f"cwd {cwd} is not writable",
        )


_OPTIONAL_VARS = [
    "U1_IMAGE_GEN_BASE_URL",
    "U1_BASE_URL",
    "U1_IMAGE_GEN_MODEL",
    "U1_IMAGE_GEN_MODEL_TYPE",
    "VLM_API_KEY",
    "VLM_BASE_URL",
    "VLM_MODEL",
    "VLM_TYPE",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_TYPE",
    "U1_IMAGE_BASE",
    "PPT_DECK_ROOT",
]


def check_optional_env_vars() -> CheckResult:
    """Enumerate optional env vars; always passes (informational only)."""
    parts = []
    for var in _OPTIONAL_VARS:
        val = _env(var)
        parts.append(f"{var}={'<set>' if val else 'unset'}")
    detail = "; ".join(parts)
    return CheckResult(
        name="OPTIONAL_ENV_VARS",
        severity="soft",
        passed=True,
        detail=detail,
    )


def check_export_pptx_node_modules(base: Path | None = None) -> CheckResult:
    """Check that export_pptx script has its node_modules installed."""
    if base is None:
        # Default: repo-relative
        repo_root = Path(__file__).parent.parent.parent.parent  # skills/ppt-doctor/../../../ → repo
        base = repo_root / "skills" / "ppt-standard" / "scripts" / "export_pptx"

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
    """Check optional Python dependencies; always passed=True (informational)."""
    checks = [
        ("pypdf", "pypdf"),
        ("python-docx", "docx"),
    ]
    parts = []
    for display_name, module_name in checks:
        spec = importlib.util.find_spec(module_name)
        status = "installed" if spec is not None else "missing"
        parts.append(f"{display_name}: {status}")
    detail = "; ".join(parts)
    return CheckResult(
        name="PYTHON_DEPS",
        severity="soft",
        passed=True,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

def run_all_checks() -> list[CheckResult]:
    """Run all checks (hard and soft) and return the results."""
    return [
        check_u1_lm_api_key(),
        check_u1_lm_base_url(),
        check_u1_api_key(),
        check_u1_image_base_discoverable(),
        check_openclaw_runner_executable(),
        check_node_version(),
        # soft checks
        check_ppt_deck_root_writable(),
        check_optional_env_vars(),
        check_export_pptx_node_modules(),
        check_python_deps(),
    ]
