"""Shared SN_* image configuration; public status never includes a key."""
from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from studio_errors import StudioError

DEFAULT_BASE_URL = "https://token.sensenova.cn/v1"
DEFAULT_MODEL = "sensenova-u1.5-lite"


def is_u15_model(model):
    value = model.lower()
    return re.fullmatch(r"sensenova-u1\.5(?:-[a-z0-9._-]+)?", value) is not None


def read_env_file(path):
    values = {}
    if not path.is_file():
        return values
    try:
        from dotenv import dotenv_values
        return {k: v for k, v in dotenv_values(path).items() if isinstance(v, str)}
    except ImportError:
        pass
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if not match:
            continue
        key, value = match.groups()
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                value = value.strip('"')
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        if isinstance(value, str):
            values[key] = value
    return values


class Configuration:
    def __init__(self, env_file, environ=None):
        self.env_file = Path(env_file).expanduser().resolve()
        self.environ = dict(os.environ if environ is None else environ)

    def resolve(self):
        values = {**self.environ, **read_env_file(self.env_file)}
        def first(*names, default=""):
            for name in names:
                if values.get(name, "").strip():
                    return values[name].strip(), name
            return default, "default"
        key, key_source = first("SN_IMAGE_GEN_API_KEY", "SN_API_KEY")
        base_url, base_source = first("SN_IMAGE_GEN_BASE_URL", "SN_BASE_URL", default=DEFAULT_BASE_URL)
        model, _ = first("SN_IMAGE_GEN_MODEL", default=DEFAULT_MODEL)
        protocol, _ = first("SN_IMAGE_GEN_MODEL_TYPE", default="sensenova")
        return {"api_key": key, "base_url": base_url.rstrip("/"), "model": model,
                "protocol": protocol, "key_source": key_source, "base_url_source": base_source}

    def public(self):
        value = self.resolve()
        missing = []
        if not value["api_key"]:
            missing.append("SN_API_KEY（或 SN_IMAGE_GEN_API_KEY）")
        parts = urlsplit(value["base_url"])
        if parts.scheme not in {"https", "http"} or not parts.netloc or parts.username or parts.password:
            missing.append("有效的 SN_BASE_URL（或 SN_IMAGE_GEN_BASE_URL）")
        if not is_u15_model(value["model"]):
            missing.append("SN_IMAGE_GEN_MODEL 必须属于 sensenova-u1.5 系列")
        if value["protocol"] != "sensenova":
            missing.append("SN_IMAGE_GEN_MODEL_TYPE=sensenova")
        dependencies = [name for name in ("httpx", "PIL", "dotenv")
                        if importlib.util.find_spec(name) is None]
        return {"configured": not missing, "has_key": bool(value["api_key"]), "missing": missing,
                "base_url": value["base_url"], "model": value["model"], "key_source": value["key_source"],
                "base_url_source": value["base_url_source"], "env_file": str(self.env_file),
                "image_ready": not missing and not dependencies, "missing_dependencies": dependencies}

    def save(self, body):
        if not isinstance(body, dict):
            raise StudioError("invalidConfig", "配置必须是 JSON 对象。")
        current = self.resolve()
        key = body.get("api_key", "")
        base_url = body.get("base_url", current["base_url"])
        model = body.get("model", current["model"])
        if not all(isinstance(v, str) for v in (key, base_url, model)):
            raise StudioError("invalidConfigFields", "配置字段必须是字符串。")
        key, base_url, model = key.strip(), base_url.strip().rstrip("/"), model.strip()
        if not key and not current["api_key"]:
            raise StudioError("keyRequired", "请填写 API Key。")
        if any(c in key for c in ("\n", "\r", "\x00")) or len(key) > 4096:
            raise StudioError("invalidKey", "API Key 格式无效。")
        parts = urlsplit(base_url)
        if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password or parts.query or parts.fragment:
            raise StudioError("invalidBaseURL", "请填写不含凭据、查询参数的 API Base URL。")
        if not is_u15_model(model) or len(model) > 120:
            raise StudioError("invalidModel", "模型名须属于 sensenova-u1.5 系列，具体型号以账号可用项为准。")
        updates = {"SN_IMAGE_GEN_BASE_URL": base_url, "SN_IMAGE_GEN_MODEL": model,
                   "SN_IMAGE_GEN_MODEL_TYPE": "sensenova"}
        if key:
            updates["SN_IMAGE_GEN_API_KEY"] = key
        # Preserve unrelated shared and harness settings in the existing .env.
        lines = self.env_file.read_text(encoding="utf-8").splitlines() if self.env_file.is_file() else []
        keys = set(updates)
        lines = [line for line in lines if not any(re.match(rf"^\s*(?:export\s+)?{name}\s*=", line) for name in keys)]
        lines.extend(f"{name}={json.dumps(value, ensure_ascii=False)}" for name, value in updates.items())
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.env_file.with_name(self.env_file.name + ".studio-tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            stream.write("\n".join(lines) + "\n")
        temporary.replace(self.env_file)
        os.chmod(self.env_file, 0o600)
        return self.public()
