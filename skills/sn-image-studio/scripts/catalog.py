"""Load and publish image cases shared by the webpage and host Agent."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from studio_errors import StudioError

WEB_DIR = Path(__file__).resolve().parents[1] / "assets" / "web"
CATALOG_PATH = WEB_DIR / "catalog-prompts.json"
PUBLIC_CASE_FIELDS = {
    "name", "category", "mode", "style", "suggestion", "originalPrompt", "promptLocales",
    "format", "preview", "before", "beforeLabel", "inputImages", "requiredInputs", "width", "height",
    "archived", "sourceLabel", "source",
}


def example_paths(item):
    paths = [item.get("preview")]
    if item.get("before") is not None:
        paths.append(item["before"])
    paths.extend(path for path in item.get("inputImages", [])
                 if isinstance(path, str) and path.startswith("assets/"))
    if "alternateExample" in item:
        alternate = item["alternateExample"]
        if item.get("mode") != "edit" or not item.get("before") or not isinstance(alternate, dict):
            raise ValueError("第二组样例须与图片编辑案例的原图和结果配套。")
        paths.extend((alternate.get("before"), alternate.get("preview")))
    return paths


def validate_case(case_id, item, web_dir=WEB_DIR):
    if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", case_id):
        raise ValueError("案例 ID 请使用小写字母、数字和连字符，最多 64 字符。")
    if not isinstance(item, dict):
        raise ValueError(f"{case_id}: 案例必须为 JSON 对象。")
    for key in ("name", "category", "style", "suggestion", "originalPrompt", "sourceLabel"):
        value = item.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > (64000 if key == "originalPrompt" else 2000):
            raise ValueError(f"{case_id}: 请填写有效的 {key}。")
    if "promptLocales" in item:
        prompts = item["promptLocales"]
        if not isinstance(prompts, dict) or set(prompts) != {"zh-CN", "en"} or any(
                not isinstance(value, str) or not value.strip() or len(value) > 64000 for value in prompts.values()):
            raise ValueError(f"{case_id}: promptLocales 须包含完整的 zh-CN 和 en Prompt。")
        info = item.get("promptLocalization", {})
        digest = hashlib.sha256(item["originalPrompt"].encode()).hexdigest()
        if not isinstance(info, dict) or info.get("sourceLanguage") not in ("zh-CN", "en") or info.get("sourceSha256") != digest:
            raise ValueError(f"{case_id}: Prompt 翻译来源已变更，请核对两种语言后更新来源哈希。")
        literals = info.get("preservedText")
        if not isinstance(literals, list) or any(not isinstance(text, str) or not text or
                any(text not in prompt for prompt in [item["originalPrompt"], *prompts.values()]) for text in literals):
            raise ValueError(f"{case_id}: 双语 Prompt 须原样保留 preservedText 中的画内文字。")
    if item.get("mode") not in {"generate", "edit"}:
        raise ValueError(f"{case_id}: mode 须为 generate 或 edit。")
    if type(item.get("archived", False)) is not bool:
        raise ValueError(f"{case_id}: archived 须为布尔值。")
    if not isinstance(item.get("inputImages", []), list):
        raise ValueError(f"{case_id}: inputImages 须为示例输入图列表。")
    for value in example_paths(item):
        if not isinstance(value, str) or not value.startswith("assets/"):
            raise ValueError(f"{case_id}: 样例图片须指向 assets/ 内的本地图片。")
        path = (web_dir / value).resolve()
        if not path.is_relative_to((web_dir / "assets").resolve()) or not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError(f"{case_id}: {value} 图片不存在或格式不支持。")
    count = item.get("requiredInputs", 0)
    if type(count) is not int or not 0 <= count <= 10 or (item["mode"] == "edit" and count < 1):
        raise ValueError(f"{case_id}: requiredInputs 无效。")
    for key in ("width", "height"):
        if key in item and (type(item[key]) is not int or not 1 <= item[key] <= 20000):
            raise ValueError(f"{case_id}: {key} 无效。")
    if ("width" in item) != ("height" in item):
        raise ValueError(f"{case_id}: width 和 height 请同时填写。")
    recipe = item.get("recipe")
    if not isinstance(recipe, dict) or not isinstance(recipe.get("effect"), str) or not recipe["effect"].strip():
        raise ValueError(f"{case_id}: 请填写 recipe.effect。")
    for key in ("preserve", "editable", "checks", "inputRoles"):
        values = recipe.get(key)
        if not isinstance(values, list) or len(values) > 30 or any(not isinstance(x, str) or not x.strip() or len(x) > 2000 for x in values):
            raise ValueError(f"{case_id}: recipe.{key} 须为文字列表。")
    if len(recipe["inputRoles"]) < count:
        raise ValueError(f"{case_id}: 请说明每张必要输入图的角色。")
    return item


def load_catalog(path=CATALOG_PATH):
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 2 or not isinstance(data.get("templates"), dict) or not data["templates"]:
        raise ValueError("案例库须为 version=2 且包含非空 templates 对象。")
    for case_id, item in data["templates"].items():
        validate_case(case_id, item, path.parent)
    return data


def case_revision(item):
    return hashlib.sha256(json.dumps({k: v for k, v in item.items() if k != "revision"},
                                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def public_catalog(data):
    """Expose only fields used to select, edit, attribute, and run an example."""
    templates = {}
    for case_id, item in data["templates"].items():
        public = {key: value for key, value in item.items() if key in PUBLIC_CASE_FIELDS}
        public["recipe"] = {key: item["recipe"][key] for key in ("effect", "preserve", "editable", "inputRoles", "checks")}
        if "promptLocalization" in item:
            public["promptLocalization"] = {"sourceLanguage": item["promptLocalization"]["sourceLanguage"]}
        public["revision"] = case_revision(item)
        templates[case_id] = public
    return {"version": data["version"], "templates": templates}


def case_context(case_id, path=CATALOG_PATH):
    item = load_catalog(path)["templates"].get(case_id)
    if item is None:
        raise StudioError("caseNotFound", "案例不存在，请刷新页面后重新选择。")
    digest = case_revision(item)
    return {"id": case_id, "revision": digest, "name": item["name"], "mode": item["mode"],
            "style": item["style"], "source_label": item["sourceLabel"],
            "required_inputs": item["requiredInputs"], "recipe": item["recipe"],
            "width": item.get("width"), "height": item.get("height"),
            "sample_image_role": "preview_only"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    add = sub.add_parser("add", help="Publish a supplied prompt and effect image as a case")
    add.add_argument("--case-file", required=True, type=Path)
    add.add_argument("--prompt-file", required=True, type=Path)
    add.add_argument("--preview", required=True, type=Path)
    add.add_argument("--before", type=Path)
    add.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    try:
        data = load_catalog(CATALOG_PATH)
        if args.command == "validate":
            print(json.dumps({"status": "ok", "cases": len(data["templates"])}, ensure_ascii=False))
            return 0
        item = json.loads(args.case_file.read_text(encoding="utf-8"))
        case_id = item.pop("id")
        if case_id in data["templates"] and not args.replace:
            raise ValueError("案例 ID 已存在；需要替换时显式加 --replace。")
        item["originalPrompt"] = args.prompt_file.read_text(encoding="utf-8")
        item.setdefault("inputImages", [])
        item.setdefault("requiredInputs", 0)
        copies = []
        for key, source in (("preview", args.preview), ("before", args.before)):
            if source is None:
                continue
            # Content-based names keep existing published assets intact on validation failure.
            suffix = source.suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                raise ValueError("案例效果图须为 PNG、JPG 或 WebP。")
            content = source.read_bytes()
            name = hashlib.sha256(content).hexdigest()[:24] + suffix
            target = WEB_DIR / "assets" / name
            copies.append((source, target))
            item[key] = "assets/" + name
        # Check in a temporary directory before publishing images or changing the catalog.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            check_dir = Path(tmp)
            (check_dir / "assets").mkdir()
            copy_sources = {"assets/" + target.name: source for source, target in copies}
            for path in example_paths(item):
                if not isinstance(path, str) or not (check_dir / path).resolve().is_relative_to((check_dir / "assets").resolve()):
                    raise ValueError(f"{case_id}: 样例图片须指向 assets/ 内的本地图片。")
                source = copy_sources.get(path, WEB_DIR / path)
                if path not in copy_sources and not source.resolve().is_relative_to((WEB_DIR / "assets").resolve()):
                    raise ValueError(f"{case_id}: 样例图片须指向 assets/ 内的本地图片。")
                (check_dir / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, check_dir / path)
            validate_case(case_id, item, check_dir)
        for source, target in copies:
            if not target.exists():
                shutil.copyfile(source, target)
        data["templates"][case_id] = item
        temporary = CATALOG_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(CATALOG_PATH)
        print(json.dumps({"status": "ok", "id": case_id, "cases": len(data["templates"])}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
