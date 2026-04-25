from __future__ import annotations

import contextlib
import os
import warnings
from pathlib import Path
from typing import Annotated, Literal, get_args, get_origin, get_type_hints
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).absolute().parent
# "skills" directory that contains "u1-*" skills (e.g. "u1-image-base", "u1-infographic", etc.)
SKILLS_DIR = SCRIPT_DIR.parents[1]


def prepare_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        warnings.warn("python-dotenv is not installed, `.env` files will be ignored", stacklevel=2)
        return
    # Priorities:
    # 1. ".env" in the agent's config directory:
    #    - openclaw: ~/.openclaw/.env
    #    - hermes: ~/.openclaw/.env
    # 2. ".env" in current working directory. (depends on how the agent runs the skill)
    # 3. Environment variables
    # ------------------------------------------------------------
    # In reverse order of priority, the latter overrides the former:
    # 3 -- do nothing; overridden by other env files
    # 2 --
    load_dotenv(override=True)
    # 1 --
    if "OPENCLAW_SHELL" in os.environ:
        agent_config_dir = Path("~/.openclaw").expanduser()
    else:
        agent_config_dir = Path("~/.hermes").expanduser()
    if (dotenv_path := agent_config_dir / ".env").exists():
        load_dotenv(dotenv_path, override=True)


prepare_env()


class Field:
    """Metadata marker that pairs a field with one or more env var names.

    Env vars are tried in order; the first env var that is set is returned.
    """

    __slots__ = ("env_names", "required")

    def __init__(self, *env_names: str, required: bool = False) -> None:
        self.env_names: tuple[str, ...] | None = tuple(env_names) if env_names else None
        self.required = required

    def resolve(self, target_type: type | None = None) -> str | int | float | None:
        """Return the first env var value that is set, converted to target_type.

        Args:
            target_type: The type to convert to (str, int, float, etc.) or None.
                If not int or float, returns the raw string.

        Returns:
            The converted value, or None if none of the env vars exist.
        """
        if not self.env_names:
            return None
        for n in self.env_names:
            if n in os.environ:
                raw = os.environ[n]
                if target_type is int:
                    return int(raw)
                if target_type is float:
                    return float(raw)
                # For other types (Literal, etc.), return raw string
                return raw
        return None


class Configs:
    """Central registry of env var names and built-in defaults.

    Fields annotated with ``Annotated[str, EnvVar(...)]`` are resolved in
    ``__init__``: env vars are tried in order; if none is set, the class-level
    default is kept.
    """

    # image-generate
    U1_API_KEY: Annotated[str, Field("U1_API_KEY", required=True)] = ""
    U1_IMAGE_GEN_BASE_URL: Annotated[
        str, Field("U1_IMAGE_GEN_BASE_URL", "U1_BASE_URL", required=True)
    ] = "https://u1-api.sensenova.cn/model"
    # if U1_IMAGE_GEN_MODEL_TYPE is not "u1", U1_IMAGE_GEN_MODEL must be set
    #   "nano-banana": available models are "gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview"
    U1_IMAGE_GEN_MODEL_TYPE: Annotated[
        Literal["u1", "nano-banana"],
        Field("U1_IMAGE_GEN_MODEL_TYPE"),
    ] = "u1"
    U1_IMAGE_GEN_MODEL: Annotated[str, Field("U1_IMAGE_GEN_MODEL")] = ""

    # NOTE: "U1_LM_*" vars are shared between VLM and LLM
    # image-recognize (VLM) — falls back to shared U1_LM_* vars
    VLM_API_KEY: Annotated[str, Field("VLM_API_KEY", "U1_LM_API_KEY")] = "dummy"
    VLM_BASE_URL: Annotated[str, Field("VLM_BASE_URL", "U1_LM_BASE_URL")] = ""
    VLM_MODEL: Annotated[str, Field("VLM_MODEL", "U1_LM_MODEL")] = ""
    VLM_TYPE: Annotated[
        Literal["anthropic-messages", "openai-completions"],
        Field("VLM_TYPE", "U1_LM_TYPE"),
    ] = "openai-completions"

    # text-optimize (LLM) — falls back to shared U1_LM_* vars
    LLM_API_KEY: Annotated[str, Field("LLM_API_KEY", "U1_LM_API_KEY")] = "dummy"
    LLM_BASE_URL: Annotated[str, Field("LLM_BASE_URL", "U1_LM_BASE_URL")] = ""
    LLM_MODEL: Annotated[str, Field("LLM_MODEL", "U1_LM_MODEL")] = ""
    LLM_TYPE: Annotated[
        Literal["anthropic-messages", "openai-completions"],
        Field("LLM_TYPE", "U1_LM_TYPE"),
    ] = "openai-completions"

    def __init__(self) -> None:
        for field, hint in get_type_hints(type(self), include_extras=True).items():
            env_var = next((a for a in get_args(hint) if isinstance(a, Field)), None)
            if env_var is None:
                continue
            # Extract the actual type (unwrap Annotated, handle Literal)
            origin = get_origin(hint)
            actual_type = get_args(hint)[0] if origin is Annotated else hint
            if (val := env_var.resolve(actual_type)) is not None:
                setattr(self, field, val)

    def validate_configs(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        field_env_names: dict[str, tuple[str, ...] | str] = {}
        errors: list[tuple[str, str]] = []
        for field, hint in get_type_hints(type(self), include_extras=True).items():
            env_var = next((a for a in get_args(hint) if isinstance(a, Field)), None)
            if env_var is None:
                continue
            if env_names := env_var.env_names:
                if len(env_names) > 1:
                    field_env_names[field] = env_names
                elif len(env_names) == 1:
                    field_env_names[field] = env_names[0]
            value = getattr(self, field, None)
            if not value:
                if env_var.required:
                    msg = f"Field '{field}' is required but not set; try setting the environment variable(s) {env_var.env_names}"
                    errors.append((field, msg))
                continue

        # Check fields combination rules:
        if self.U1_IMAGE_GEN_MODEL_TYPE != "u1" and not self.U1_IMAGE_GEN_MODEL:
            errors.append(
                (
                    "U1_IMAGE_GEN_MODEL",
                    "U1_IMAGE_GEN_MODEL is required when U1_IMAGE_GEN_MODEL_TYPE is not 'u1'",
                )
            )

        warnings: list[tuple[str, str]] = []
        vlm_keys = ("VLM_API_KEY", "VLM_BASE_URL", "VLM_MODEL", "VLM_TYPE")
        warnings.extend(
            [
                (
                    key,
                    f"{key} is not set; VLM may be not available. Try setting environment variable(s): {field_env_names[key]}",
                )
                for key in vlm_keys
                if not getattr(self, key)
            ]
        )
        llm_keys = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_TYPE")
        warnings.extend(
            [
                (
                    key,
                    f"{key} is not set; LLM may be not available. Try setting environment variable(s): {field_env_names[key]}",
                )
                for key in llm_keys
                if not getattr(self, key)
            ]
        )

        # check urls
        errors.extend(
            (
                key,
                f"{key} is not a valid base URL: {getattr(self, key)}",
            )
            for key in ("VLM_BASE_URL", "LLM_BASE_URL")
            if getattr(self, key) and not is_valid_base_url(getattr(self, key))
        )
        return errors, warnings

    def get_annotated_field(self, field_name: str) -> Field | None:
        hints = get_type_hints(type(self), include_extras=True)
        if field_name not in hints:
            return None
        hint = hints[field_name]
        field_inst = next((a for a in get_args(hint) if isinstance(a, Field)), None)
        return field_inst

    def get_env_var_help(self, field_name: str) -> str:
        """Return a help string describing which environment variables can be used
        to set the specified configuration field.

        Args:
            field_name: The name of the configuration field (e.g., "VLM_API_KEY").

        Returns:
            A string describing the environment variable(s) that control this field.
            Returns an error message if the field does not exist or has no EnvVar annotation.
        """
        if not hasattr(type(self), field_name):
            return f"Field '{field_name}' does not exist in Configs."

        field_inst = self.get_annotated_field(field_name)
        if field_inst is None:
            return f"Field '{field_name}' is not configurable via environment variables."

        current_value = getattr(self, field_name)
        env_names = list(field_inst.env_names) if field_inst.env_names else []
        if len(env_names) == 1:
            return (
                f"To set '{field_name}', configure the environment variable: {env_names[0]}\n"
                f"Current value: {current_value!r}"
            )
        else:
            env_list = ", ".join(env_names)
            return (
                f"To set '{field_name}', configure one of these environment variables: {env_list}\n"
                f"They are tried in order; the first set value is used.\n"
                f"Current value: {current_value!r}"
            )


def is_valid_base_url(url: str) -> bool:
    with contextlib.suppress(ValueError):
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    return False


def reload_env(override: bool = True) -> None:
    global global_configs

    try:
        from dotenv import load_dotenv

        load_dotenv(override=override)
    except ImportError:
        print("❌ python-dotenv is not installed, `.env` file will not be loaded on reload")

    try:
        global_configs = Configs()
        print("✅ Reloaded global_configs")
    except Exception as e:
        warnings.warn(f"Failed to reload global_configs: {e}", stacklevel=2)


global_configs = Configs()
