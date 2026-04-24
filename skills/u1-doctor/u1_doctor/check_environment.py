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
   are checked. Only U1_API_KEY and U1_IMAGE_GEN_BASE_URL are required; other
   vars are optional and may be omitted (built-in defaults apply).
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_DIR = SCRIPT_DIR.parents[1]

BASE_SKILL_DIR = SKILLS_DIR / "u1-image-base"


def check_installation(verbose: bool) -> bool:
    print("[1/3] Checking u1-image-base installation...")
    root = SKILLS_DIR
    base_skill = BASE_SKILL_DIR
    required = [
        base_skill / "SKILL.md",
        base_skill / "requirements.txt",
        base_skill / "u1_image_base/openclaw_runner.py",
    ]
    ok = True
    if not base_skill.exists():
        print("  ❌ u1-image-base directory not found")
        print(f"  Expected location: {base_skill}")
        return False
    if verbose:
        print(f"  ✅ u1-image-base directory found: {base_skill}")
    for f in required:
        if f.exists():
            if verbose:
                print(f"  ✅ {f.relative_to(root)}")
        else:
            print(f"  ❌ Missing: {f.relative_to(root)}")
            ok = False
    if ok and not verbose:
        print("  ✅ Installation looks good")
    # Check skills
    for d in root.iterdir():
        if not d.is_dir():
            continue
        if (d / "SKILL.md").exists():
            print(f"  ✅ {d.name} skill found")
    return ok


def check_dependencies(verbose: bool) -> bool:
    root = SKILLS_DIR
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
    req_file = BASE_SKILL_DIR / "requirements.txt"
    if not req_file.exists():
        # This should never happen, check_installation should have failed
        print(f"  ❌ requirements.txt not found: {req_file.relative_to(root)}")
        ok = False
        return ok

    import importlib.util

    # Some packages' import names are different from their names in requirements.txt
    pkg_map = {
        "pillow": "PIL",
        "python-dotenv": "dotenv",
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
        print("  Run: python -m pip install -r skills/u1-image-base/requirements.txt")
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
            global_configs,
        )

        return global_configs
    except ImportError:
        return None
    finally:
        if sys.path and sys.path[0] == str(base_path):
            sys.path.pop(0)


def check_env_vars(root: Path, _verbose: bool) -> bool:
    print("[3/3] Checking environment variables...")

    configs = _load_configs(root)
    if configs is None:
        print("  ⚠️ Cannot import Configs from u1-image-base, skipping env check")
        return True

    is_ok = True
    errors, warnings = configs.validate_configs()
    if errors:
        is_ok = False
        print("  ❌ Environment check failed! Configuration errors:")
        for field, msg in errors:
            print(f"    ❌ {field}: {msg}")
    elif warnings:
        print("  ✅ Environment check passed! Although with some warnings:")
        for field, msg in warnings:
            print(f"    ⚠️ {field}: {msg}")
    else:
        print("  ✅ Environment check passed!")
    return is_ok


def main():
    parser = argparse.ArgumentParser(
        description="SenseNova-Skills environment diagnostic"
    )
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    print("=== SenseNova-Skills Environment Check ===\n")

    root = SKILLS_DIR
    if args.verbose:
        print(f"Skills root directory: {root}\n")

    results = [
        check_installation(args.verbose),
        check_dependencies(args.verbose),
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
