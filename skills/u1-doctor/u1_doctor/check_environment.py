#!/usr/bin/env python3
"""SenseNova-Skills environment diagnostic tool.

Checks performed:

1. u1-image-base installation
   - Directory exists at skills/u1-image-base/
   - Required files: SKILL.md, requirements.txt,
     u1_image_base/__init__.py, u1_image_base/openclaw_runner.py

2. Python dependencies
   - Python version >= 3.9
   - All packages in u1-image-base/requirements.txt are installed

3. Environment variables
   Driven by u1_image_base.configs.Configs — all fields annotated with EnvVar
   are checked. Fields with empty string defaults are treated as required.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import get_args, get_type_hints

SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_DIR = SCRIPT_DIR.parents[1]


def check_installation(root: Path, verbose: bool) -> bool:
    print("[1/3] Checking u1-image-base installation...")
    base = root / "u1-image-base"
    required = [
        base / "SKILL.md",
        base / "requirements.txt",
        base / "u1_image_base" / "openclaw_runner.py",
    ]
    ok = True
    if not base.exists():
        print("  ❌ u1-image-base directory not found")
        print(f"  Expected location: {base}")
        return False
    if verbose:
        print(f"  ✅ u1-image-base directory found: {base}")
    for f in required:
        if f.exists():
            if verbose:
                print(f"  ✅ {f.relative_to(root)}")
        else:
            print(f"  ❌ Missing: {f.relative_to(root)}")
            ok = False
    if ok and not verbose:
        print("  ✅ Installation looks good")
    return ok


def check_dependencies(root: Path, verbose: bool) -> bool:
    print("[2/3] Checking Python dependencies...")
    ok = True

    # Python version
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 9):
        print(f"  ✅ Python {major}.{minor}.{sys.version_info[2]}")
    else:
        print(f"  ❌ Python {major}.{minor} is too old (need >= 3.9)")
        ok = False

    # Packages from requirements.txt
    req_file = root / "u1-image-base" / "requirements.txt"
    if not req_file.exists():
        print("  ❌ requirements.txt not found, skipping package check")
        return ok

    import importlib.util

    pkg_map = {
        "httpx": "httpx",
        "pillow": "PIL",
        "python-dotenv": "dotenv",
        "requests": "requests",
        "anthropic": "anthropic",
        "openai": "openai",
    }

    missing = []
    for line in req_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # strip version specifier
        pkg_name = line.split(">=")[0].split("==")[0].split("<=")[0].strip().lower()
        import_name = pkg_map.get(pkg_name, pkg_name)
        found = importlib.util.find_spec(import_name) is not None
        if found:
            if verbose:
                print(f"  ✅ {pkg_name}")
        else:
            missing.append(pkg_name)

    if missing:
        print(f"  ❌ Missing packages: {', '.join(missing)}")
        print("  Run: pip install -r skills/u1-image-base/requirements.txt")
        ok = False
    elif not verbose:
        print("  ✅ All required packages installed")

    return ok


def _load_configs(root: Path):
    """Import and return Configs from u1-image-base, or None on failure."""
    base_path = root / "u1-image-base"
    sys.path.insert(0, str(base_path))
    try:
        from u1_image_base.configs import (  # pyright: ignore[reportMissingImports]
            Configs,
        )

        return Configs
    except ImportError:
        return None
    finally:
        if sys.path and sys.path[0] == str(base_path):
            sys.path.pop(0)


def _write_env_file(env_file: Path, key: str, value: str) -> None:
    """Append or update a key=value line in the .env file."""
    lines = env_file.read_text().splitlines() if env_file.exists() else []
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
            lines[i] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    env_file.write_text("\n".join(lines) + "\n")


def check_env_vars(root: Path, verbose: bool) -> bool:
    print("[3/3] Checking environment variables...")

    Configs = _load_configs(root)
    if Configs is None:
        print("  ⚠️  Cannot import Configs from u1-image-base, skipping env check")
        return True

    from u1_image_base.configs import EnvVar  # pyright: ignore[reportMissingImports]

    hints = get_type_hints(Configs, include_extras=True)
    env_file = root / ".env"
    missing_required = []

    for field, hint in hints.items():
        env_var = next((a for a in get_args(hint) if isinstance(a, EnvVar)), None)
        if env_var is None:
            continue

        set_name = next((n for n in env_var.env_names if os.environ.get(n)), None)
        default = getattr(Configs, field, "")
        is_required = default == ""
        primary_name = env_var.env_names[0]

        if set_name:
            if verbose:
                suffix = f" (via {set_name})" if set_name != primary_name else ""
                print(f"  ✅ {primary_name} configured{suffix}")
        elif is_required:
            print(f"  ❌ {primary_name} not set (required)")
            missing_required.append(primary_name)
        else:
            if verbose:
                print(f"  ⚠️  {primary_name} not set (using default: {default!r})")

    if not missing_required:
        if not verbose:
            print("  ✅ All required environment variables configured")
        return True

    # Prompt user to fill in missing required vars
    print()
    print("  Some required environment variables are missing.")
    print(f"  Enter values below to save them to {env_file}.")
    print("  Press Enter to skip a variable.\n")

    saved = []
    for primary_name in missing_required:
        try:
            value = input(f"  {primary_name}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if value:
            _write_env_file(env_file, primary_name, value)
            os.environ[primary_name] = value
            saved.append(primary_name)

    if saved:
        print(f"\n  ✅ Saved to {env_file}: {', '.join(saved)}")

        # Reload environment
        try:
            from u1_image_base.configs import (  # pyright: ignore[reportMissingImports]
                reload_env,
            )

            print("  🔄 Reloading environment...")
            reload_env(override=True)
            print("  ✅ Environment reloaded successfully")
        except Exception as e:
            print(f"  ⚠️  Failed to reload environment: {e}")
            print("  💡 Suggestion: Restart the agent to apply new configuration")
    else:
        print("\n  ⚠️  No values entered. Required variables are still missing.")

    return True  # env vars are warnings, not hard failures


def main():
    parser = argparse.ArgumentParser(
        description="SenseNova-Skills environment diagnostic"
    )
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    print("=== SenseNova-Skills Environment Check ===\n")

    root = SKILLS_DIR
    if args.verbose:
        print(f"Project root: {root}\n")

    results = [
        check_installation(root, args.verbose),
        check_dependencies(root, args.verbose),
    ]
    check_env_vars(root, args.verbose)

    print("\n=== Summary ===")
    if all(results):
        print("  ✅ Environment is properly configured")
        sys.exit(0)
    else:
        print("  ❌ Environment check failed")
        print("Please fix the errors above before using SenseNova-Skills.")
        sys.exit(1)


if __name__ == "__main__":
    main()
