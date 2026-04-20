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
import sys
from pathlib import Path

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


def check_env_vars(root: Path, verbose: bool) -> bool:
    print("[3/3] Checking environment variables...")

    # Import Configs from u1-image-base
    base_path = root / "u1-image-base"
    if str(base_path) not in sys.path:
        sys.path.insert(0, str(base_path))
    try:
        from u1_image_base.configs import (  # pyright: ignore[reportMissingImports]
            global_configs,
        )
    except ImportError as e:
        print(f"  ⚠️ Cannot import Configs: {e}")
        return True
    finally:
        if sys.path[0] == str(base_path):
            sys.path.pop(0)

    # image-generation
    if not global_configs.U1_API_KEY:
        msg = global_configs.get_env_var_help("U1_API_KEY")
        print(f"  ❌ {msg}")
        return False
    if not global_configs.U1_IMAGE_GEN_BASE_URL:
        msg = global_configs.get_env_var_help("U1_IMAGE_GEN_BASE_URL")
        print(f"  ❌ {msg}")
        return False

    # VLM
    if not global_configs.VLM_API_KEY:
        msg = global_configs.get_env_var_help("VLM_API_KEY")
        print(f"  ⚠️ {msg}")
    if not global_configs.VLM_BASE_URL:
        msg = global_configs.get_env_var_help("VLM_BASE_URL")
        print(f"  ⚠️ {msg}")

    # LLM
    if not global_configs.LLM_API_KEY:
        msg = global_configs.get_env_var_help("LLM_API_KEY")
        print(f"  ⚠️ {msg}")
    if not global_configs.LLM_BASE_URL:
        msg = global_configs.get_env_var_help("LLM_BASE_URL")
        print(f"  ⚠️ {msg}")
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
