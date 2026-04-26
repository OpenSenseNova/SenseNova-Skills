"""Lightweight, self-contained LLM/VLM client for ppt-* skills.

Reads env from .env (via python-dotenv) and hits two endpoints:

    llm(system, user) -> str                              # LLM_BASE_URL/v1/chat/completions
    vlm(system, user, images) -> str                      # VLM_BASE_URL/v1/chat/completions

**T2I is intentionally NOT here.** Image generation routes through
u1-image-base/openclaw_runner.py u1-image-generate. This module is LLM/VLM only.

No asyncio. No adapters. No configs.Configs. Just httpx.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*a, **kw): return False  # noqa

import httpx


# ---------------------------------------------------------------------------
# .env loading — search repo root / skills/.env / cwd, in that order
# ---------------------------------------------------------------------------

def _find_and_load_env() -> list[Path]:
    here = Path(__file__).resolve()
    # skills/ppt-standard/lib/model_client.py → parents[3] = repo root
    repo_root = here.parents[3]
    loaded: list[Path] = []
    for candidate in (repo_root / ".env", repo_root / "skills" / ".env", Path.cwd() / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)
            loaded.append(candidate)
    return loaded


_LOADED_ENV = _find_and_load_env()


def _env(name: str, *fallbacks: str, default: str = "") -> str:
    for key in (name, *fallbacks):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return default


# ---------------------------------------------------------------------------
# Config (read lazily each call — cheap + supports env mutation between calls)
# ---------------------------------------------------------------------------


@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    timeout: float = 120.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            api_key=_env("LLM_API_KEY", "U1_LM_API_KEY"),
            base_url=_env("LLM_BASE_URL", "U1_LM_BASE_URL"),
            model=_env("LLM_MODEL", "U1_LM_MODEL", default=""),
            timeout=float(_env("LLM_TIMEOUT", default="120")),
        )


@dataclass
class VLMConfig:
    api_key: str
    base_url: str
    model: str
    timeout: float = 120.0

    @classmethod
    def from_env(cls) -> "VLMConfig":
        return cls(
            api_key=_env("VLM_API_KEY", "U1_LM_API_KEY"),
            base_url=_env("VLM_BASE_URL", "U1_LM_BASE_URL"),
            model=_env("VLM_MODEL", "U1_LM_MODEL", default=""),
            timeout=float(_env("VLM_TIMEOUT", default="120")),
        )


# NOTE: T2I is intentionally NOT handled here. Image generation must go through
# u1-image-base/openclaw_runner.py u1-image-generate. This module is LLM/VLM only.


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ModelClientError(RuntimeError):
    pass


class MissingConfigError(ModelClientError):
    pass


# ---------------------------------------------------------------------------
# LLM / VLM  (OpenAI-compatible chat/completions)
# ---------------------------------------------------------------------------


def _require(value: str, name: str) -> str:
    if not value:
        raise MissingConfigError(f"{name} is not set (check .env)")
    return value


_LLM_CONNECT_TIMEOUT_S = 10.0
_LLM_WRITE_TIMEOUT_S = 30.0
_RETRIABLE_STATUS_CODES = {502, 503, 504}


def _build_llm_timeout(timeout_s: float) -> httpx.Timeout:
    return httpx.Timeout(timeout_s, connect=_LLM_CONNECT_TIMEOUT_S, write=_LLM_WRITE_TIMEOUT_S)


def _is_transient_llm_error(exc: httpx.HTTPError) -> bool:
    if isinstance(exc, (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRIABLE_STATUS_CODES
    return False


def llm(system_prompt: str, user_prompt: str, *, model: str | None = None,
        timeout: float | None = None, retries: int = 0,
        request_name: str = "llm") -> str:
    """Call the LLM chat endpoint. Returns the assistant message text."""
    cfg = LLMConfig.from_env()
    _require(cfg.api_key, "LLM_API_KEY / U1_LM_API_KEY")
    _require(cfg.base_url, "LLM_BASE_URL / U1_LM_BASE_URL")
    timeout_s = float(cfg.timeout if timeout is None else timeout)
    max_attempts = max(1, int(retries) + 1)
    timeout_cfg = _build_llm_timeout(timeout_s)

    url = f"{cfg.base_url.rstrip('/')}/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": model or _require(cfg.model, "LLM_MODEL / U1_LM_MODEL"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    for attempt in range(1, max_attempts + 1):
        started_at = time.monotonic()
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=timeout_cfg)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            body = ""
            if isinstance(e, httpx.HTTPStatusError):
                body = e.response.text[:500]
            elapsed = time.monotonic() - started_at
            if _is_transient_llm_error(e) and attempt < max_attempts:
                sys.stderr.write(
                    f"[llm:{request_name}] transient {type(e).__name__} on attempt {attempt}/{max_attempts} after {elapsed:.1f}s, retrying\n"
                )
                continue
            raise ModelClientError(
                f"LLM call failed [{request_name}] attempt {attempt}/{max_attempts}: {type(e).__name__}: {e} after {elapsed:.1f}s | body: {body}"
            ) from e

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ModelClientError(
                f"LLM response shape unexpected [{request_name}]: {json.dumps(data)[:500]}"
            ) from e


def vlm(system_prompt: str, user_prompt: str, images: list[str | Path], *,
        model: str | None = None) -> str:
    """Call the VLM chat endpoint with one or more image paths. Returns assistant text."""
    cfg = VLMConfig.from_env()
    _require(cfg.api_key, "VLM_API_KEY / U1_LM_API_KEY")
    _require(cfg.base_url, "VLM_BASE_URL / U1_LM_BASE_URL")

    content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
    for img in images:
        p = Path(img)
        if not p.exists():
            raise MissingConfigError(f"image not found: {p}")
        mime = mimetypes.guess_type(str(p))[0] or "image/png"
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        })

    url = f"{cfg.base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model or _require(cfg.model, "VLM_MODEL / U1_LM_MODEL"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
    }
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=cfg.timeout)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        body = ""
        if isinstance(e, httpx.HTTPStatusError):
            body = e.response.text[:500]
        raise ModelClientError(f"VLM call failed: {e} | body: {body}") from e

    data = resp.json()
    try:
        msg = data["choices"][0]["message"]["content"]
        if isinstance(msg, list):
            return "".join(blk.get("text", "") for blk in msg if blk.get("type") == "text")
        return msg
    except (KeyError, IndexError, TypeError) as e:
        raise ModelClientError(f"VLM response shape unexpected: {json.dumps(data)[:500]}") from e


# ---------------------------------------------------------------------------
# Debug / health
# ---------------------------------------------------------------------------


def env_summary() -> dict[str, str]:
    llm_cfg = LLMConfig.from_env()
    vlm_cfg = VLMConfig.from_env()
    return {
        "loaded_env_files": " ".join(str(p) for p in _LOADED_ENV) or "(none)",
        "LLM.base_url": llm_cfg.base_url or "(unset)",
        "LLM.model": llm_cfg.model or "(unset)",
        "VLM.base_url": vlm_cfg.base_url or "(unset)",
        "VLM.model": vlm_cfg.model or "(unset)",
    }


if __name__ == "__main__":
    # Quick sanity: `python -m ppt_standard.lib.model_client health` or similar
    if len(sys.argv) > 1 and sys.argv[1] == "health":
        for k, v in env_summary().items():
            print(f"{k:24s}  {v}")
        try:
            out = llm("You are a helpful assistant.", "Say 'ok' and nothing else.")
            print(f"LLM ping: {out[:60]!r}")
        except Exception as e:
            print(f"LLM ping failed: {e}")
    else:
        print("usage: python model_client.py health")
