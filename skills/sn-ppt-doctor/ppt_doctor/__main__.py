"""Entry point: `python -m ppt_doctor [--non-interactive]`"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ppt_doctor.checks import run_all_checks
from ppt_doctor.interactive import interactive_fill_env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sn-ppt-doctor")
    parser.add_argument("--non-interactive", action="store_true", help="Skip interactive .env prompts")
    parser.add_argument("--env-path", type=Path, default=Path.cwd() / ".env")
    args = parser.parse_args(argv)

    print("== sn-ppt-doctor: environment check ==\n")
    results = run_all_checks()
    hard_failed = [r for r in results if r.severity == "hard" and not r.passed]

    for r in results:
        tag = "OK  " if r.passed else ("FAIL" if r.severity == "hard" else "WARN")
        print(f"[{tag}] [{r.severity}] {r.name}: {r.detail}")

    if hard_failed:
        print("\nSome required checks failed. Entering interactive fill...\n")
        fill = interactive_fill_env(env_path=args.env_path, non_interactive=args.non_interactive)
        if fill.written:
            print(f"\nWrote .env at {fill.path}. Please re-run /skill sn-ppt-doctor to verify.")
        else:
            print("\nNothing written. Re-run after fixing environment manually.")
        return 1

    print("\nAll hard checks passed. PPT family is ready to use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
