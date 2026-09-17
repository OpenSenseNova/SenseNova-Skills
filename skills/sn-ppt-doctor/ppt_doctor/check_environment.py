#!/usr/bin/env python3
"""Report deterministic dependencies and optional media fallbacks for PPT Skills."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib import parse


DEFAULT_SEARCH_BASE_URL = "https://google.serper.dev"


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def node_version() -> str | None:
    node = shutil.which("node")
    if not node:
        return None
    try:
        result = subprocess.run(
            [node, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def command_version(name: str) -> str | None:
    executable = shutil.which(name)
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def uv_playwright_python() -> list[str] | None:
    """Return the installed uv-tool Playwright Python runner without installing it."""
    uv = shutil.which("uv")
    if not uv:
        return None
    try:
        completed = subprocess.run(
            [uv, "tool", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    installed = any(
        line.strip().split(maxsplit=1)[0] == "playwright"
        for line in completed.stdout.splitlines()
        if line.strip() and not line.lstrip().startswith("-")
    )
    if completed.returncode != 0 or not installed:
        return None
    return [uv, "tool", "run", "--from", "playwright", "python"]


def playwright_chromium_status(standard_dir: Path) -> dict[str, Any]:
    """Check the exact Python Playwright + Chromium path used by Standard rendering."""
    python_runner = [sys.executable]
    python_source = "current_interpreter"
    current_interpreter_install_hint = [
        f'{sys.executable} -m pip install -r "{standard_dir / "requirements.txt"}"',
        f"{sys.executable} -m playwright install chromium",
    ]
    uv_tool_install_hint = [
        "uv tool install playwright",
        "uv tool run --from playwright playwright install chromium",
    ]
    install_hint = current_interpreter_install_hint
    if not module_available("playwright"):
        uv_runner = uv_playwright_python()
        if uv_runner is not None:
            python_runner = uv_runner
            python_source = "uv_tool"
            install_hint = ["uv tool run --from playwright playwright install chromium"]
        else:
            return {
                "status": "missing",
                "python_package": False,
                "python_source": None,
                "python_runner": None,
                "browser_present": False,
                "launchable": False,
                "reason": "python_playwright_missing",
                "install_hint": install_hint,
                "alternative_install_hint": uv_tool_install_hint,
            }

    probe = r'''
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

result = {
    "status": "missing",
    "python_package": True,
    "browser_present": False,
    "launchable": False,
}
try:
    with sync_playwright() as playwright:
        executable = playwright.chromium.executable_path
        result["browser_executable"] = executable
        result["browser_present"] = Path(executable).is_file()
        if not result["browser_present"]:
            result["reason"] = "chromium_not_installed"
        else:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            try:
                page = browser.new_page(viewport={"width": 320, "height": 180})
                page.set_content("<html><body>ppt doctor</body></html>")
                result["launchable"] = True
                result["status"] = "available"
            finally:
                browser.close()
except Exception as exc:
    result["reason"] = type(exc).__name__
    result["detail"] = str(exc).splitlines()[0][:300]
print(json.dumps(result))
'''
    try:
        completed = subprocess.run(
            [*python_runner, "-c", probe],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        result["python_source"] = python_source
        result["python_runner"] = python_runner
        if result.get("status") != "available":
            result["install_hint"] = install_hint
        return result
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, IndexError) as exc:
        return {
            "status": "failed",
            "python_package": True,
            "python_source": python_source,
            "python_runner": python_runner,
            "browser_present": False,
            "launchable": False,
            "reason": type(exc).__name__,
            "detail": str(exc)[:300],
            "install_hint": install_hint,
        }


def html_to_pptx_status(export_dir: Path) -> dict[str, Any]:
    """Check the Node dependencies and browser used by the HTML -> PPTX exporter."""
    script = export_dir / "html_to_pptx.mjs"
    package_json = export_dir / "package.json"
    node = shutil.which("node")
    install_hint = [
        f'npm --prefix "{export_dir}" install --omit=dev',
        f'npm --prefix "{export_dir}" exec playwright install chromium',
    ]
    required_packages = ["pptxgenjs", "playwright", "echarts"]
    if package_json.is_file():
        try:
            manifest = json.loads(package_json.read_text(encoding="utf-8"))
            required_packages = sorted(manifest.get("dependencies", {}).keys())
        except (OSError, json.JSONDecodeError):
            pass

    base: dict[str, Any] = {
        "status": "missing_dependency",
        "script_present": script.is_file(),
        "package_json_present": package_json.is_file(),
        "package_lock_present": (export_dir / "package-lock.json").is_file(),
        "node": node_version(),
        "npm": command_version("npm"),
        "required_packages": required_packages,
        "packages": {name: False for name in required_packages},
        "chromium_present": False,
        "chromium_launchable": False,
    }
    if not script.is_file():
        base["reason"] = "export_script_missing"
        return base
    if not node:
        base["reason"] = "node_missing"
        base["install_hint"] = install_hint
        return base

    probe = r'''
const fs = require('node:fs');
const packages = __PACKAGES__;

(async () => {
  const result = {
    status: 'missing_dependency',
    packages: {},
    chromium_present: false,
    chromium_launchable: false,
  };
  for (const packageName of packages) {
    try {
      result.packages[packageName] = require.resolve(packageName, { paths: [process.cwd()] });
    } catch {
      result.packages[packageName] = false;
    }
  }
  const missing = packages.filter((packageName) => !result.packages[packageName]);
  if (missing.length) {
    result.reason = 'node_packages_missing';
    result.missing_packages = missing;
    console.log(JSON.stringify(result));
    return;
  }

  const { chromium } = require(result.packages.playwright);
  const executable = chromium.executablePath();
  result.chromium_executable = executable;
  result.chromium_present = fs.existsSync(executable);
  if (!result.chromium_present) {
    result.reason = 'chromium_not_installed';
    console.log(JSON.stringify(result));
    return;
  }

  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    const page = await browser.newPage({ viewport: { width: 320, height: 180 } });
    await page.setContent('<html><body>ppt doctor</body></html>');
    result.chromium_launchable = true;
    result.status = 'available';
  } catch (error) {
    result.reason = 'chromium_launch_failed';
    result.detail = String(error && error.message ? error.message : error).split('\n')[0].slice(0, 300);
  } finally {
    if (browser) await browser.close().catch(() => undefined);
  }
  console.log(JSON.stringify(result));
})().catch((error) => {
  console.log(JSON.stringify({
    status: 'failed',
    reason: 'node_probe_failed',
    detail: String(error && error.message ? error.message : error).split('\n')[0].slice(0, 300),
  }));
});
'''.replace("__PACKAGES__", json.dumps(required_packages))

    try:
        completed = subprocess.run(
            [node, "-e", probe],
            cwd=export_dir,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        base.update(result)
        if base.get("status") != "available":
            base["install_hint"] = install_hint
        return base
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, IndexError) as exc:
        base.update(
            {
                "status": "failed",
                "reason": type(exc).__name__,
                "detail": str(exc)[:300],
                "install_hint": install_hint,
            }
        )
        return base


def _first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _first_env_name(*names: str) -> str | None:
    for name in names:
        if os.environ.get(name, "").strip():
            return name
    return None


def _valid_url(value: str) -> bool:
    parsed = parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _search_url(kind: str) -> tuple[str, str]:
    exact_name = (
        "SN_PPT_WEB_SEARCH_URL" if kind == "web_search" else "SN_PPT_IMAGE_SEARCH_URL"
    )
    exact = _first_env(exact_name)
    if exact:
        return exact, exact_name
    base_env = _first_env_name("SN_PPT_SEARCH_BASE_URL", "SERPER_BASE_URL")
    base = _first_env("SN_PPT_SEARCH_BASE_URL", "SERPER_BASE_URL") or DEFAULT_SEARCH_BASE_URL
    endpoint = "search" if kind == "web_search" else "images"
    return f"{base.rstrip('/')}/{endpoint}", base_env or "default_serper"


def _image_generation_url() -> tuple[str, str | None]:
    exact = _first_env("SN_PPT_IMAGE_GEN_URL")
    if exact:
        return exact, "SN_PPT_IMAGE_GEN_URL"
    base_env = _first_env_name("SN_IMAGE_GEN_BASE_URL", "SN_BASE_URL")
    base = _first_env("SN_IMAGE_GEN_BASE_URL", "SN_BASE_URL")
    return (
        f"{base.rstrip('/')}/images/generations" if base else "",
        base_env,
    )


def _load_ppt_env(skills_dir: Path) -> dict[str, Any]:
    scripts_dir = skills_dir / "sn-ppt-tools" / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        from env_config import load_ppt_env

        result = load_ppt_env().to_dict()
    except (ImportError, OSError, ValueError) as exc:
        result = {
            "path": None,
            "source": None,
            "exists": False,
            "loaded_keys": [],
            "preserved_process_keys": [],
            "invalid_lines": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        try:
            sys.path.remove(str(scripts_dir))
        except ValueError:
            pass
    relevant_prefixes = ("SN_PPT_", "SN_IMAGE_GEN_", "SERPER_")
    relevant_exact = {"SN_API_KEY", "SN_BASE_URL"}
    for field in ("loaded_keys", "preserved_process_keys"):
        result[field] = [
            name
            for name in result.get(field, [])
            if name.startswith(relevant_prefixes) or name in relevant_exact
        ]
    return result


def _probe(script: Path, args: list[str], timeout: float) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "failed", "reason": type(exc).__name__, "detail": str(exc)[:300]}
    output = result.stdout.strip().splitlines()
    if output:
        try:
            payload = json.loads(output[-1])
            if isinstance(payload, dict):
                payload.pop("detail", None)
                payload["exit_code"] = result.returncode
                return payload
        except json.JSONDecodeError:
            pass
    return {
        "status": "failed",
        "reason": "invalid probe output",
        "exit_code": result.returncode,
        "stderr": result.stderr.strip()[:300],
    }


def _bundled_media(
    skills_dir: Path,
    args: argparse.Namespace,
    env_load: dict[str, Any],
) -> dict[str, Any]:
    tools_dir = skills_dir / "sn-ppt-tools"
    scripts_dir = tools_dir / "scripts"
    scripts = {
        "web_search": scripts_dir / "web_search.py",
        "image_search": scripts_dir / "image_search.py",
        "fetch_image": scripts_dir / "fetch_image.py",
        "image_generation": scripts_dir / "image_generate.py",
    }

    search_key_env = _first_env_name(
        "SN_PPT_WEB_SEARCH_API_KEY",
        "SN_PPT_SEARCH_API_KEY",
        "SERPER_API_KEY",
    )
    image_search_key_env = _first_env_name(
        "SN_PPT_IMAGE_SEARCH_API_KEY",
        "SN_PPT_SEARCH_API_KEY",
        "SERPER_API_KEY",
    )
    image_generation_key_env = _first_env_name(
        "SN_PPT_IMAGE_GEN_API_KEY",
        "SN_IMAGE_GEN_API_KEY",
        "SN_API_KEY",
    )
    image_generation_model_env = _first_env_name(
        "SN_PPT_IMAGE_GEN_MODEL",
        "SN_IMAGE_GEN_MODEL",
    )

    web_url, web_url_env = _search_url("web_search")
    image_search_url, image_search_url_env = _search_url("image_search")
    image_generation_url, image_generation_url_env = _image_generation_url()

    media: dict[str, Any] = {
        "tools_dir": str(tools_dir),
        "config_file": env_load,
        "web_search": {
            "script_present": scripts["web_search"].is_file(),
            "url": web_url,
            "url_source": web_url_env,
            "url_valid": _valid_url(web_url),
            "api_key_configured": bool(search_key_env),
            "api_key_source": search_key_env,
        },
        "image_search": {
            "script_present": scripts["image_search"].is_file(),
            "fetch_script_present": scripts["fetch_image"].is_file(),
            "url": image_search_url,
            "url_source": image_search_url_env,
            "url_valid": _valid_url(image_search_url),
            "api_key_configured": bool(image_search_key_env),
            "api_key_source": image_search_key_env,
        },
        "image_generation": {
            "script_present": scripts["image_generation"].is_file(),
            "url": image_generation_url,
            "url_source": image_generation_url_env,
            "url_valid": _valid_url(image_generation_url),
            "api_key_configured": bool(image_generation_key_env),
            "api_key_source": image_generation_key_env,
            "model_configured": bool(image_generation_model_env),
            "model_source": image_generation_model_env,
        },
    }

    for name in ("web_search", "image_search"):
        item = media[name]
        item["missing"] = [
            field
            for field, missing in (
                ("script", not item["script_present"]),
                ("fetch_script", name == "image_search" and not item["fetch_script_present"]),
                ("url", not item["url_valid"]),
                ("api_key", not item["api_key_configured"]),
            )
            if missing
        ]
        item["status"] = (
            "configured"
            if not item["missing"]
            else "unconfigured"
        )
    generation = media["image_generation"]
    generation["missing"] = [
        field
        for field, missing in (
            ("script", not generation["script_present"]),
            ("url", not generation["url_valid"]),
            ("api_key", not generation["api_key_configured"]),
            ("model", not generation["model_configured"]),
        )
        if missing
    ]
    generation["status"] = (
        "configured"
        if not generation["missing"]
        else "unconfigured"
    )

    if args.probe_search:
        timeout = float(os.environ.get("SN_PPT_TOOL_TIMEOUT_SECONDS", "30")) + 5
        media["web_search"]["probe"] = _probe(
            scripts["web_search"],
            ["PPT capability probe", "--num", "1"],
            timeout,
        )
        media["image_search"]["probe"] = _probe(
            scripts["image_search"],
            ["presentation capability probe", "--num", "1"],
            timeout,
        )

    if args.probe_image_generation:
        output_dir = Path(args.probe_output_dir).expanduser().resolve()
        output_name = f"ppt_doctor_image_probe_{int(time.time())}.png"
        timeout = float(os.environ.get("SN_PPT_IMAGE_GEN_TIMEOUT_SECONDS", "300")) + 10
        media["image_generation"]["probe"] = _probe(
            scripts["image_generation"],
            [
                "--prompt",
                (
                    "A polished square key visual for SenseNova Skills AI presentation creation: "
                    "an editable slide canvas connected to research notes, a narrative outline, "
                    "charts, and image assets; modern professional editorial design, crisp layered "
                    "composition, restrained blue, white, and warm red palette, no logo, no "
                    "watermark, no small text"
                ),
                "--deck-dir",
                str(output_dir),
                "--output",
                output_name,
                "--size",
                "1344x1344",
            ],
            timeout,
        )
    media["configuration_help"] = {
        "edit_file": env_load.get("path"),
        "template": (
            'SN_PPT_SEARCH_API_KEY="<search-api-key>"\n'
            'SN_PPT_IMAGE_GEN_URL="https://your-host/images/generations"\n'
            'SN_PPT_IMAGE_GEN_API_KEY="<image-generation-api-key>"\n'
            'SN_PPT_IMAGE_GEN_MODEL="<image-generation-model>"'
        ),
        "note": "Existing process variables override values loaded from this file.",
    }
    return media


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect PPT Skill capabilities.")
    parser.add_argument(
        "--probe-search",
        action="store_true",
        help="Send one minimal web-search and image-search request.",
    )
    parser.add_argument(
        "--probe-image-generation",
        action="store_true",
        help="Send one real image-generation request; may incur cost.",
    )
    parser.add_argument(
        "--probe-output-dir",
        default="",
        help="Absolute existing output directory required for image-generation probe.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.probe_image_generation:
        probe_dir = Path(args.probe_output_dir).expanduser()
        if not args.probe_output_dir or not probe_dir.is_absolute() or not probe_dir.is_dir():
            raise SystemExit(
                "--probe-image-generation requires --probe-output-dir "
                "pointing to an absolute existing directory"
            )

    skills_dir = Path(__file__).resolve().parents[2]
    standard_dir = skills_dir / "sn-ppt-standard"
    standard_renderer = standard_dir / "scripts" / "render.py"
    export_dir = standard_dir / "scripts" / "export_pptx"
    standard_browser = playwright_chromium_status(standard_dir)
    html_export = html_to_pptx_status(export_dir)
    env_load = _load_ppt_env(skills_dir)
    workspace = Path.cwd().resolve()
    ppt_decks = workspace / "ppt_decks"
    checks = {
        "workspace": str(workspace),
        "ppt_decks": str(ppt_decks),
        "workspace_writable": workspace.is_dir() and os.access(workspace, os.W_OK),
        "pypdf": module_available("pypdf"),
        "python_docx": module_available("docx"),
        "python_pptx": module_available("pptx"),
        "node": node_version(),
        "python_playwright": standard_browser["python_package"],
        "playwright_chromium": standard_browser,
        "static_renderer": standard_renderer.is_file(),
        "standard_html": {
            "status": (
                "available"
                if standard_renderer.is_file() and standard_browser["status"] == "available"
                else "missing_dependency"
            ),
            "renderer_script": standard_renderer.is_file(),
            "python_playwright": standard_browser["python_package"],
            "chromium_present": standard_browser["browser_present"],
            "chromium_launchable": standard_browser["launchable"],
        },
        "html_to_pptx": html_export["script_present"],
        "html_to_pptx_environment": html_export,
        "workbench_runtime": (
            skills_dir
            / "sn-ppt-workbench"
            / "workbench-runtime"
            / "bin"
            / "sensenova-ppt-workbench.mjs"
        ).is_file(),
        "native_media": {
            "status": "agent_inspection_required",
            "presence_rule": "registered tool => present_unverified, never available",
            "available_requires": "successful config/health check or real probe",
        },
        "bundled_media": _bundled_media(skills_dir, args, env_load),
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
