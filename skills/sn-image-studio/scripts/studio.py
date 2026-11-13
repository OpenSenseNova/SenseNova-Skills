#!/usr/bin/env python3
"""Harness-neutral prompt tasks and scripted SenseNova U1.5 image calls."""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import http.server
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
import uuid
from pathlib import Path

from studio_errors import StudioError

from agent_bridge import AgentBridge, PROFILES
from configuration import Configuration
from catalog import case_context, load_catalog, public_catalog
from execution_limits import DEFAULT_AGENT_TIMEOUT, IMAGE_PROCESS_TIMEOUT, error_text

SKILL_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = SKILL_DIR / "assets" / "web"
SERVICE = "sn-image-studio"
API_VERSION = 4
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_task(body):
    if not isinstance(body, dict) or body.get("operation") not in {"rewrite_prompt", "generate_image"}:
        raise StudioError("invalidOperation", "请选择 Prompt 改写或图片生成操作。")
    for field in ("request_id", "session_id", "sample_id"):
        if not isinstance(body.get(field), str) or not ID_PATTERN.fullmatch(body[field]):
            raise StudioError("invalidTaskField", "无效的 {field}。", field=field)
    prompt = body.get("current_prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 64000:
        raise StudioError("invalidPrompt", "current_prompt 不能为空且最多为 64000 字符。")
    if type(body.get("base_revision")) is not int or body["base_revision"] < 1:
        raise StudioError("invalidDraftVersion", "无效的草稿版本。")
    result = {key: body[key] for key in ("request_id", "session_id", "sample_id", "operation", "base_revision", "current_prompt")}
    if "prompt_language" in body:
        if body["prompt_language"] not in ("zh-CN", "en"):
            raise StudioError("invalidPromptLanguage", "Prompt 语言须为 zh-CN 或 en。")
        result["prompt_language"] = body["prompt_language"]
    context = case_context(body["sample_id"])
    if body.get("case_revision") and body["case_revision"] != context["revision"]:
        raise StudioError("caseUpdated", "案例已经更新，请刷新页面后重新提交。")
    images = body.get("input_images", [])
    if not isinstance(images, list) or len(images) > 10 or any(not isinstance(x, str) or not ID_PATTERN.fullmatch(x) for x in images):
        raise StudioError("invalidInputImages", "请先上传图片，使用有序的图片资产 ID。")
    roles = body.get("input_image_roles", [])
    if not isinstance(roles, list) or (roles and len(roles) != len(images)) or any(not isinstance(x, str) or len(x) > 200 for x in roles):
        raise StudioError("invalidImageRoles", "图片角色须与输入图片逐一对应，且每项最多 200 字符。")
    default_roles = context["recipe"]["inputRoles"]
    if not roles:
        roles = [default_roles[i] if i < len(default_roles) else "补充参考图" for i in range(len(images))]
    result.update(case_context=context, input_images=images, input_image_roles=roles)
    if body["operation"] == "rewrite_prompt":
        request = body.get("user_request")
        if not isinstance(request, str) or not request.strip() or len(request) > 6000:
            raise StudioError("invalidRewriteRequest", "user_request 不能为空且最多为 6000 字符。")
        if type(body.get("preserve_style", True)) is not bool:
            raise StudioError("invalidPreserveStyle", "preserve_style 必须为布尔值。")
        result.update(user_request=request, preserve_style=body.get("preserve_style", True))
    generate_after = body.get("generate_after_rewrite", False)
    if type(generate_after) is not bool:
        raise StudioError("invalidGenerateAfter", "generate_after_rewrite 必须为布尔值。")
    if body["operation"] == "rewrite_prompt":
        result["generate_after_rewrite"] = generate_after
    if body["operation"] == "generate_image" or generate_after:
        if len(images) < context["required_inputs"]:
            raise StudioError("requiredImages", "此案例需要至少 {count} 张输入图。", count=context["required_inputs"])
        mode = "edit" if images else "generate"
        parameters = body.get("parameters", {})
        if not isinstance(parameters, dict):
            raise StudioError("invalidImageParameters", "无效的图像参数。")
        ratio, size = parameters.get("aspect_ratio", "auto"), parameters.get("image_size", "2k")
        if not isinstance(ratio, str) or (ratio != "auto" and not re.fullmatch(r"[1-9][0-9]{0,2}:[1-9][0-9]{0,2}", ratio)):
            raise StudioError("invalidImageRatio", "无效的图片比例。")
        if size not in {"2k", "4k"}:
            raise StudioError("invalidImageSize", "图片尺寸须为 2k 或 4k。")
        result.update(creation_mode=mode, input_images=images, parameters={"aspect_ratio": ratio, "image_size": size})
    return result


def validate_response(value, task):
    if not isinstance(value, dict) or set(value) != {"new_prompt", "summary", "changes"}:
        raise ValueError("需要 new_prompt、summary、changes 三个字段。")
    if not isinstance(value["new_prompt"], str) or not value["new_prompt"].strip() or len(value["new_prompt"]) > 64000:
        raise ValueError("请返回有效的完整 Prompt。")
    if not isinstance(value["summary"], str) or len(value["summary"]) > 2000:
        raise ValueError("修改摘要无效。")
    if not isinstance(value["changes"], list) or len(value["changes"]) > 30 or any(not isinstance(x, str) or len(x) > 2000 for x in value["changes"]):
        raise ValueError("修改列表无效。")
    try:
        original = json.loads(task["current_prompt"])
    except ValueError:
        original = None
    if isinstance(original, (dict, list)):
        try:
            revised = json.loads(value["new_prompt"])
        except ValueError as exc:
            raise ValueError("结构化 Prompt 必须保持有效 JSON。") from exc
        if type(revised) is not type(original):
            raise ValueError("请保留结构化 Prompt 的根类型。")
    return value


class TaskStore:
    def __init__(self, directory, image_runner=None, asset_resolver=None, bridge=None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.image_runner = image_runner
        self.asset_resolver = asset_resolver
        self.bridge = bridge or AgentBridge()
        self.condition = threading.Condition()
        self.tasks = {}
        self.cancellations = {}
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="studio-task")
        for path in self.directory.glob("*/task.json"):
            try:
                task = json.loads(path.read_text(encoding="utf-8"))
                if task.get("status") in {"queued", "running"}:
                    task.update(status="failed", error_code="serviceRestarted", error="服务已重启，上次结果可能未确认。请检查原任务文件；不会自动重试。")
                    write_json(path, task)
                self.tasks[task["request_id"]] = task
            except (OSError, ValueError, KeyError):
                continue

    def _save(self, task):
        directory = self.directory / task["request_id"]
        directory.mkdir(exist_ok=True)
        write_json(directory / "task.json", task)

    def submit(self, body):
        request = validate_task(body)
        if request["input_images"]:
            if self.asset_resolver is None:
                raise StudioError("assetsUnavailable", "图片资产尚未就绪。")
            for asset_id in request["input_images"]:
                self.asset_resolver(asset_id)
        fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self.condition:
            existing = self.tasks.get(request["request_id"])
            if existing:
                if existing["fingerprint"] != fingerprint:
                    raise FileExistsError("同一请求 ID 已用于其他内容。")
                return dict(existing)
            if sum(t["status"] in {"queued", "running"} for t in self.tasks.values()) >= 8:
                raise OverflowError("待处理任务较多，请稍后再试。")
            if (request["operation"] == "generate_image" or request.get("generate_after_rewrite")) and self.image_runner is None:
                raise StudioError("imageRunnerUnavailable", "图片执行脚本尚未就绪。")
            if request["operation"] == "rewrite_prompt" and not self.bridge.public()["available"]:
                raise StudioError("configureAgent", self.bridge.public()["message"])
            task = {**request, "status": "queued", "phase": "queued", "fingerprint": fingerprint, "created_at": time.time()}
            if request["operation"] == "rewrite_prompt":
                task.update(harness=self.bridge.harness, execution_token=secrets.token_urlsafe(32))
            self.tasks[request["request_id"]] = task
            self.cancellations[request["request_id"]] = threading.Event()
            self._save(task)
            self.pool.submit(self._run_image if request["operation"] == "generate_image" else self._run_agent, request["request_id"])
            return dict(task)

    def get(self, request_id):
        with self.condition:
            task = self.tasks.get(request_id)
            return dict(task) if task else None

    def cancel(self, request_id):
        with self.condition:
            task = self.tasks.get(request_id)
            if not task:
                raise StudioError("unknownTask", "未找到任务。")
            if task["status"] not in {"queued", "running"}:
                return dict(task)
            if task.get("phase") == "generating":
                raise FileExistsError("生图已提交，请等待原请求结果，避免重复计费。")
            self.cancellations[request_id].set()
            task.update(status="cancelled", phase="cancelled", finished_at=time.time())
            self._save(task)
            return dict(task)

    def _event(self, request_id, event):
        with self.condition:
            task = self.tasks[request_id]
            if task["status"] != "running" or task.get("phase") == "generating":
                return
            task.update({k: v for k, v in event.items() if k in {"phase", "agent_info", "acp_session_id", "activity", "tool_status"}})
            self._save(task)

    def _run_agent(self, request_id):
        with self.condition:
            task = self.tasks[request_id]
            if task["status"] != "queued":
                return
            task.update(status="running", phase="connecting")
            self._save(task)
        mailbox_stop = threading.Event()
        mailbox_thread = None
        try:
            directory = self.directory / request_id / "agent"
            directory.mkdir(exist_ok=True)
            inputs = []
            for index, asset_id in enumerate(task["input_images"]):
                item = self.asset_resolver(asset_id)
                target = directory / f"input-{index + 1}{Path(item['path']).suffix}"
                shutil.copyfile(item["path"], target)
                inputs.append({"path": str(target), "order": index + 1, "role": task["input_image_roles"][index], "media_type": item["media_type"]})
            snapshot = {**public_task(task), "input_assets": inputs}
            write_json(directory / "task-input.json", snapshot)
            write_json(directory / "job-access.json", {"request_id": request_id, "token": task["execution_token"]})
            shutil.copyfile(SKILL_DIR / "SKILL.md", directory / "SKILL.md")
            shutil.copyfile(SKILL_DIR / "scripts" / "execute_task.py", directory / "execute_task.py")
            shutil.copyfile(SKILL_DIR / "scripts" / "execution_limits.py", directory / "execution_limits.py")
            mailbox_thread = threading.Thread(target=self._serve_mailbox, args=(request_id, directory, mailbox_stop), daemon=True)
            mailbox_thread.start()
            self.bridge.run(snapshot, directory, lambda event: self._event(request_id, event), self.cancellations[request_id])
            with self.condition:
                if task["status"] == "running" and task.get("phase") != "generating":
                    raise StudioError("agentNoResult", "Agent 已结束，但未通过 execute_task.py 提交有效结果。")
        except Exception as exc:
            with self.condition:
                # A late ACP error must not overwrite a paid request's result.
                if task["status"] == "running" and task.get("phase") != "generating":
                    issue = exc.payload() if isinstance(exc, StudioError) else {
                        "error_code": "agentFailed", "error": str(exc)[:1200] or "ACP 连接超时。",
                    }
                    task.update(status="failed", **issue, finished_at=time.time())
                    self._save(task)

        finally:
            mailbox_stop.set()
            if mailbox_thread:
                mailbox_thread.join()

    def _serve_mailbox(self, request_id, directory, stop):
        incoming = directory / "execution-request.json"
        while not stop.wait(.05):
            if not incoming.is_file():
                continue
            try:
                if incoming.stat().st_size > 262144:
                    raise ValueError("任务结果过大。")
                body = json.loads(incoming.read_text(encoding="utf-8"))
                if body.get("request_id") != request_id:
                    raise ValueError("任务 ID 不匹配。")
                task = self.execute_result(request_id, body.get("token"), body.get("response"))
                receipt = {key: task[key] for key in ("status", "phase", "response", "image", "error") if key in task}
            except (ValueError, TypeError, OSError, KeyError) as exc:
                receipt = {"status": "failed", "error": str(exc)[:1200]}
            write_json(directory / "execution-receipt.json", receipt)
            return

    def execute_result(self, request_id, token, response):
        with self.condition:
            task = self.tasks.get(request_id)
            if not task or not isinstance(token, str) or not secrets.compare_digest(task.get("execution_token", ""), token):
                raise ValueError("无效的任务凭证。")
            response = validate_response(response, task)
            if "response" in task:
                if task["response"] != response:
                    raise FileExistsError("此任务已提交不同的改写结果。")
                return dict(task)  # Idempotent, including failures/uncertain images.
            if task["status"] != "running":
                raise FileExistsError("任务已结束，无法执行。")
            task["response"] = response
            generate = task["generate_after_rewrite"]
            if generate:
                task["phase"] = "generating"
                task["generation_started_at"] = time.time()
            else:
                task.update(status="succeeded", phase="completed", finished_at=time.time())
            self._save(task)  # Durable boundary BEFORE the paid request.
            image_task = {**task, "current_prompt": response["new_prompt"]}
        if generate:
            self._produce_image(task, image_task, image_key="image")
        return self.get(request_id)

    def _run_image(self, request_id):
        with self.condition:
            task = self.tasks[request_id]
            if task["status"] != "queued":
                return
            task.update(status="running", phase="generating", generation_started_at=time.time())
            self._save(task)
            snapshot = dict(task)
        self._produce_image(task, snapshot, image_key="response")

    def _produce_image(self, task, snapshot, image_key):
        try:
            response = self.image_runner(snapshot, self.directory / task["request_id"])
            update = {"status": "succeeded", "phase": "completed", image_key: response}
        except Exception as exc:
            update = {"status": "failed", "error_code": "imageFailed", "error": error_text(exc, "图像任务失败")[:1200]}
        with self.condition:
            task.update(update, finished_at=time.time())
            self._save(task)


def public_task(task):
    return {k: v for k, v in task.items() if k not in {"execution_token", "fingerprint"}}


class Assets:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def get(self, asset_id):
        if not isinstance(asset_id, str) or not ID_PATTERN.fullmatch(asset_id):
            raise StudioError("invalidAssetID", "无效的图片 ID。")
        path = self.directory / f"{asset_id}.json"
        if not path.is_file():
            raise StudioError("assetNotFound", "未找到图片，请重新上传。")
        return json.loads(path.read_text(encoding="utf-8"))

    def register(self, data, name, media_type):
        suffixes = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
        if media_type not in suffixes or not data or len(data) > 80 * 1024 * 1024:
            raise StudioError("invalidImageFormat", "不支持的图片格式或文件过大。")
        valid = ((media_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or
                 (media_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff")) or
                 (media_type == "image/webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP"))
        if not valid:
            raise StudioError("imageFormatMismatch", "图片内容与文件类型不匹配。")
        asset_id = uuid.uuid4().hex
        path = self.directory / (asset_id + suffixes[media_type])
        path.write_bytes(data)
        item = {"asset_id": asset_id, "file_name": Path(name).name, "media_type": media_type,
                "path": str(path), "url": f"/api/assets/{asset_id}/file"}
        write_json(self.directory / f"{asset_id}.json", item)
        return item

    def upload(self, body):
        if not isinstance(body, dict) or not isinstance(body.get("data_url"), str):
            raise StudioError("imageContentRequired", "请提交图片内容。")
        media_type, encoded = body["data_url"].split(";base64,", 1)
        media_type = media_type.removeprefix("data:")
        data = base64.b64decode(encoded, validate=True)
        if len(data) > 20 * 1024 * 1024:
            raise StudioError("imageTooLarge", "上传图片最多 20 MB。")
        return self.register(data, str(body.get("file_name", "image")), media_type)


def run_image(task, directory, config, assets):
    prompt_file = directory / "submitted-prompt.txt"
    prompt_file.write_text(task["current_prompt"], encoding="utf-8")
    paths = [assets.get(asset_id)["path"] for asset_id in task["input_images"]]
    ratio = task["parameters"]["aspect_ratio"]
    if ratio == "auto":
        sample = task.get("case_context") or case_context(task["sample_id"])
        ratio = f"{sample['width']}:{sample['height']}" if sample.get("width") and sample.get("height") else "1:1"
    command = [sys.executable, str(SKILL_DIR / "scripts" / "images.py"), "--env-file", str(config.env_file),
               "--prompt-file", str(prompt_file), "--save-path", str(directory / "result.png"),
               "--aspect-ratio", ratio, "--image-size", task["parameters"]["image_size"]]
    if paths:
        command.extend(["--images", *paths])
    try:
        result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True,
                                timeout=IMAGE_PROCESS_TIMEOUT, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"生图脚本总等待超时（{IMAGE_PROCESS_TIMEOUT} 秒）；服务端结果尚未确认，请检查原任务，不要直接重复提交。") from exc
    try:
        response = json.loads(result.stdout)
    except ValueError as exc:
        raise RuntimeError("生图脚本未返回有效结果，请检查本 skill 的 requirements.txt 依赖。") from exc
    if result.returncode or response.get("status") != "ok":
        raise RuntimeError(response.get("error") or "生图调用失败，脚本未提供错误详情。")
    output = Path(response["output"]).resolve()
    if not output.is_relative_to(directory.resolve()) or not output.is_file():
        raise RuntimeError("生图脚本未保存预期的图片文件。")
    asset = assets.register(output.read_bytes(), output.name, "image/png")
    return {"asset_id": asset["asset_id"], "image_url": asset["url"], "model": response["model"],
            "submitted_prompt": task["current_prompt"], "operation": response["operation"]}


def make_server(port, store, config, assets):
    config_lock = threading.Lock()
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(WEB_DIR), **kwargs)

        def _valid_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def json_response(self, status, value):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._valid_host():
                return self.json_response(403, {"error": "仅支持本机访问。", "error_code": "localOnly"})
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/catalog":
                try:
                    return self.json_response(200, public_catalog(load_catalog()))
                except (OSError, ValueError) as exc:
                    return self.json_response(500, {"error": str(exc)})
            if path == "/api/health":
                return self.json_response(200, {"service": SERVICE, "api_version": API_VERSION,
                    "rewrite_available": store.bridge.public()["available"], "rewrite_mode": "acp", "agent": store.bridge.public(),
                    "configuration": config.public()})
            if path == "/api/config":
                return self.json_response(200, config.public())
            if path.startswith("/api/tasks/"):
                request_id = path.rsplit("/", 1)[-1]
                task = store.get(request_id) if ID_PATTERN.fullmatch(request_id) else None
                return self.json_response(200 if task else 404, public_task(task) if task else {"error": "未找到任务。", "error_code": "unknownTask"})
            if path.startswith("/api/assets/") and path.endswith("/file"):
                try:
                    item = assets.get(path.split("/")[-2])
                    file = Path(item["path"])
                    self.send_response(200)
                    self.send_header("Content-Type", item["media_type"])
                    self.send_header("Content-Length", str(file.stat().st_size))
                    self.send_header("Cache-Control", "private, max-age=3600")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    with file.open("rb") as stream:
                        shutil.copyfileobj(stream, self.wfile)
                except (ValueError, OSError):
                    return self.json_response(404, {"error": "未找到图片。", "error_code": "unknownAsset"})
                return
            if path.startswith("/api/"):
                return self.json_response(404, {"error": "未找到接口。", "error_code": "unknownEndpoint"})
            super().do_GET()

        def send_head(self):
            # GET and HEAD share this allowlist; package files and directory listings are not web assets.
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            pages = {"/", "/index.html", "/app.js", "/case-copy.js", "/drafts.js", "/i18n.js", "/styles.css", "/favicon.ico", "/sensetime-brand.png"}
            asset = re.fullmatch(r"/assets/[A-Za-z0-9_.-]+\.(?:png|jpg|jpeg|webp|svg|ico)", path)
            target = (WEB_DIR / path.lstrip("/")).resolve()
            if not self._valid_host() or (path not in pages and not asset) or not target.is_relative_to(WEB_DIR.resolve()):
                self.send_error(404, "File not found")
                return None
            return super().send_head()

        def end_headers(self):
            if not self.path.startswith("/api/assets/"):
                self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def do_POST(self):
            origin = self.headers.get("Origin")
            allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if not self._valid_host() or self.headers.get("X-Image-Studio") != "1" or (origin and origin not in allowed):
                return self.json_response(403, {"error": "请从本地 Image Studio 页面或 skill 脚本提交。", "error_code": "localSubmitOnly"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                limit = 30 * 1024 * 1024 if self.path == "/api/assets" else 262144
                if not 0 < length <= limit:
                    return self.json_response(413, {"error": "请求过大或为空。", "error_code": "invalidRequestSize"})
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise StudioError("invalidJSONBody", "请求必须是 JSON 对象。")
                if self.path == "/api/config":
                    with config_lock:
                        return self.json_response(200, config.save(body))
                if self.path.startswith("/api/tasks/") and self.path.endswith("/cancel"):
                    return self.json_response(200, public_task(store.cancel(self.path.split("/")[-2])))
                if self.path not in {"/api/assets", "/api/rewrites", "/api/generations"}:
                    return self.json_response(404, {"error": "未找到接口。", "error_code": "unknownEndpoint"})
                status = config.public()
                if not status["configured"]:
                    return self.json_response(412, {"error": "请先配置 SenseNova API Key 和模型。", "error_code": "configureBeforeUse", "configuration": status})
                if self.path == "/api/assets":
                    item = assets.upload(body)
                    return self.json_response(201, {k: v for k, v in item.items() if k != "path"})
                if self.path in {"/api/rewrites", "/api/generations"}:
                    expected = "rewrite_prompt" if self.path == "/api/rewrites" else "generate_image"
                    if not isinstance(body, dict) or body.get("operation") != expected:
                        raise StudioError("operationMismatch", "任务类型与接口不匹配。")
                    if expected == "generate_image" or body.get("generate_after_rewrite") is True:
                        if not status["image_ready"]:
                            return self.json_response(412, {"error": "请安装 sn-image-studio/requirements.txt 中的图像依赖。", "error_code": "missingImageDependencies", "configuration": status})
                    return self.json_response(202, public_task(store.submit(body)))
                return self.json_response(404, {"error": "未找到接口。", "error_code": "unknownEndpoint"})
            except FileExistsError as exc:
                code = "cancelAlreadyGenerating" if self.path.endswith("/cancel") else "duplicateTaskId"
                return self.json_response(409, {"error": str(exc), "error_code": code})
            except OverflowError as exc:
                return self.json_response(429, {"error": str(exc), "error_code": "queueFull"})
            except StudioError as exc:
                return self.json_response(400, exc.payload())
            except (ValueError, TypeError, UnicodeDecodeError, KeyError) as exc:
                return self.json_response(400, {"error": str(exc)})

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server


def api_call(port, route, body=None, timeout=5):
    headers = {"Content-Type": "application/json", "X-Image-Studio": "1"}
    req = urllib.request.Request(f"http://127.0.0.1:{port}{route}",
        data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def probe(port):
    try:
        value = api_call(port, "/api/health", timeout=1)
        return value if value.get("service") == SERVICE else None
    except (OSError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Start the harness-neutral local studio")
    serve.add_argument("--data-dir", type=Path)
    serve.add_argument("--background", action="store_true")
    serve.add_argument("--language", choices=("auto", "zh-CN", "en"), default="auto",
                       help="Initial UI language in the launch URL; auto uses the saved preference or browser language")
    doctor = sub.add_parser("doctor", help="Check SN_* configuration without printing credentials")
    configure = sub.add_parser("configure", help="Save configuration from JSON on stdin")
    serve.add_argument("--port", type=int, default=4318)
    for command in (serve, doctor):
        command.add_argument("--harness", choices=PROFILES)
        command.add_argument("--acp-command", help="ACP launch argv as a JSON array; overrides the selected profile's executable")
        command.add_argument("--agent-timeout", type=int, default=DEFAULT_AGENT_TIMEOUT)
    for command in (serve, doctor, configure):
        command.add_argument("--env-file", type=Path, default=Path.cwd() / ".env")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        bridge = AgentBridge(getattr(args, "harness", None),
                             json.loads(args.acp_command) if getattr(args, "acp_command", None) else None,
                             getattr(args, "agent_timeout", DEFAULT_AGENT_TIMEOUT))
        if bridge.command and not bridge.harness:
            raise ValueError("使用 --acp-command 时必须指定 --harness。")
        if bridge.timeout <= 0:
            raise ValueError("--agent-timeout 必须为正数。")
        if args.command in {"doctor", "configure"}:
            config = Configuration(args.env_file)
            status = config.save(json.load(sys.stdin)) if args.command == "configure" else config.public()
            print(json.dumps({**status, "agent": bridge.public()}, ensure_ascii=False))
            return 0 if status["configured"] and (not bridge.harness or bridge.public()["available"]) else 2
        if not 1 <= args.port <= 65535:
            raise ValueError("无效的端口。")
        directory = (args.data_dir or Path.home() / ".cache" / SERVICE / str(args.port)).expanduser().resolve()
        config = Configuration(args.env_file)
        directory.mkdir(parents=True, exist_ok=True)
        url = f"http://127.0.0.1:{args.port}/"
        if args.language != "auto":
            url += "?" + urllib.parse.urlencode({"lang": args.language})
        if args.background:
            existing = probe(args.port)
            if existing:
                if existing.get("api_version") != API_VERSION or existing.get("agent", {}).get("launch_id") != bridge.launch_id or existing.get("configuration", {}).get("env_file") != str(config.env_file):
                    raise ValueError("该端口运行不同版本或 harness 的服务，请先停止旧进程或另选端口。")
                print(json.dumps({"status": "ok", "url": url, "reused": True, "configuration": existing["configuration"]}, ensure_ascii=False))
                return 0
            command = [sys.executable, str(Path(__file__).resolve()), "serve", "--port", str(args.port),
                       "--data-dir", str(directory), "--env-file", str(config.env_file), "--agent-timeout", str(args.agent_timeout)]
            if args.harness:
                command.extend(["--harness", args.harness])
            if args.acp_command:
                command.extend(["--acp-command", args.acp_command])
            with (directory / "server.log").open("ab") as log:
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=os.name != "nt")
            for _ in range(40):
                if probe(args.port):
                    print(json.dumps({"status": "ok", "url": url, "pid": child.pid, "configuration": config.public(), "agent": bridge.public()}, ensure_ascii=False))
                    return 0
                if child.poll() is not None:
                    break
                time.sleep(.1)
            if child.poll() is None:
                child.terminate()
            raise RuntimeError(f"服务未启动，请查看 {directory / 'server.log'}。")
        assets = Assets(directory / "assets")
        load_catalog()  # Fail before serving if a published case is incomplete.
        store = TaskStore(directory / "tasks", lambda task, run_dir: run_image(task, run_dir, config, assets), assets.get, bridge)
        server = make_server(args.port, store, config, assets)
        print(json.dumps({"status": "ok", "url": url, "configuration": config.public(), "agent": bridge.public()}, ensure_ascii=False), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            store.pool.shutdown(wait=True)
        return 0
    except urllib.error.HTTPError as exc:
        try:
            error = json.load(exc)
        except ValueError:
            error = {"error": f"HTTP {exc.code}"}
        print(json.dumps({"status": "failed", **error}, ensure_ascii=False))
        return 1
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
