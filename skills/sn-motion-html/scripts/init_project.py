#!/usr/bin/env python3
"""Initialize an SN Motion HTML project from the bundled template."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL_ROOT / "assets" / "template"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default="Untitled Story")
    parser.add_argument("--style", choices=["anime", "cinematic", "cgi"], default="cinematic")
    parser.add_argument("--ui", choices=["folio", "caption", "graphic"], default="folio")
    parser.add_argument("--force", action="store_true", help="allow copying into a non-empty directory")
    args = parser.parse_args()

    output = args.output.expanduser().resolve()
    if output.exists() and any(output.iterdir()) and not args.force:
        parser.error(f"output directory is not empty: {output}; pass --force to merge")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE, output, dirs_exist_ok=True)

    project_scripts = output / "scripts"
    project_scripts.mkdir(parents=True, exist_ok=True)
    for name in ("seedance_pipeline.py", "make_posters.py", "verify_media.py", "contact_sheet.py", "serve_project.py"):
        source = SKILL_ROOT / "scripts" / name
        target = project_scripts / name
        shutil.copy2(source, target)
        target.chmod(0o755)

    index = output / "index.html"
    index.write_text(index.read_text(encoding="utf-8").replace("{{TITLE}}", args.title), encoding="utf-8")

    story_path = output / "content" / "story.json"
    story = json.loads(story_path.read_text(encoding="utf-8").replace("{{TITLE}}", args.title))
    story["meta"]["style"] = args.style
    story["meta"]["ui"] = args.ui
    story["meta"].pop("accent", None)
    story_path.write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    preset_path = SKILL_ROOT / "assets" / "style-presets" / f"{args.style}.json"
    preset = json.loads(preset_path.read_text(encoding="utf-8"))
    (output / "prompts" / "style-preamble.txt").write_text(preset["image_prompt"].strip() + "\n", encoding="utf-8")
    (output / "prompts" / "style-motion.txt").write_text(preset["video_prompt"].strip() + "\n", encoding="utf-8")

    for relative in (
        "assets/images/characters",
        "assets/images/scenes",
        "assets/video/dives",
        "assets/video/connectors",
        "assets/video/frames",
        "docs",
        "tmp",
    ):
        directory = output / relative
        directory.mkdir(parents=True, exist_ok=True)
        if relative != "tmp":
            (directory / ".gitkeep").touch()

    env = output / ".env"
    if not env.exists():
        shutil.copyfile(output / ".env.example", env)
        env.chmod(0o600)

    print(f"Initialized SN Motion HTML project: {output}")
    print(f"Style preset: {args.style}")
    print(f"Interface preset: {args.ui}")
    print("Next: replace content/story.json and prompts/video-manifest.json, then add scene images.")
    print("Preview safely with: python scripts/serve_project.py . --port 8080")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
