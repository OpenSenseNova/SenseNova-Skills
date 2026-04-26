from __future__ import annotations

import contextlib
import os
import warnings
from pathlib import Path
from typing import Annotated, Literal, get_args, get_origin, get_type_hints
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).absolute().parent
# "skills" directory that contains "sn-*" skills (e.g. "sn-image-base", "sn-infographic", etc.)
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

    __slots__ = ("env_names", "required", "secret")

    def __init__(self, *env_names: str, required: bool = False, secret: bool = False) -> None:
        self.env_names: tuple[str, ...] | None = tuple(env_names) if env_names else None
        self.required = required
        self.secret = secret

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
    SN_IMAGE_GEN_API_KEY: Annotated[
        str, Field("SN_IMAGE_GEN_API_KEY", required=True, secret=True)
    ] = ""
    SN_IMAGE_GEN_BASE_URL: Annotated[
        str, Field("SN_IMAGE_GEN_BASE_URL", required=True)
    ] = "https://token.sensenova.cn/v1"
    SN_IMAGE_GEN_MODEL_TYPE: Annotated[
        Literal["sensenova", "nano-banana", "openai-image"], Field("SN_IMAGE_GEN_MODEL_TYPE")
    ] = "sensenova"
    SN_IMAGE_GEN_MODEL: Annotated[str, Field("SN_IMAGE_GEN_MODEL")] = "sensenova-u1-fast"

    # chat runtime shared by text and vision commands; command-specific
    # SN_TEXT_* / SN_VISION_* values override these defaults.
    SN_CHAT_API_KEY: Annotated[str, Field("SN_CHAT_API_KEY", secret=True)] = ""
    SN_CHAT_BASE_URL: Annotated[str, Field("SN_CHAT_BASE_URL")] = (
        "https://token.sensenova.cn/v1"
    )
    SN_CHAT_TYPE: Annotated[
        Literal["anthropic-messages", "openai-completions"], Field("SN_CHAT_TYPE")
    ] = "openai-completions"
    SN_CHAT_MODEL: Annotated[str, Field("SN_CHAT_MODEL")] = "sensenova-6.7-flash-lite"
    SN_TEXT_API_KEY: Annotated[str, Field("SN_TEXT_API_KEY", "SN_CHAT_API_KEY", secret=True)] = ""
    SN_TEXT_BASE_URL: Annotated[str, Field("SN_TEXT_BASE_URL", "SN_CHAT_BASE_URL")] = ""
    SN_TEXT_TYPE: Annotated[
        Literal["anthropic-messages", "openai-completions"],
        Field("SN_TEXT_TYPE", "SN_CHAT_TYPE"),
    ] = ""
    SN_TEXT_MODEL: Annotated[str, Field("SN_TEXT_MODEL", "SN_CHAT_MODEL")] = (
        "sensenova-6.7-flash-lite"
    )
    SN_VISION_API_KEY: Annotated[str, Field("SN_VISION_API_KEY", "SN_CHAT_API_KEY", secret=True)] = ""
    SN_VISION_BASE_URL: Annotated[str, Field("SN_VISION_BASE_URL", "SN_CHAT_BASE_URL")] = ""
    SN_VISION_TYPE: Annotated[
        Literal["anthropic-messages", "openai-completions"],
        Field("SN_VISION_TYPE", "SN_CHAT_TYPE"),
    ] = ""
    SN_VISION_MODEL: Annotated[str, Field("SN_VISION_MODEL", "SN_CHAT_MODEL")] = (
        "sensenova-6.7-flash-lite"
    )

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

    def to_string(self, mask_secrets: bool = True) -> str:
        rows = []
        for field_name, hint in get_type_hints(type(self), include_extras=True).items():
            field = next((a for a in get_args(hint) if isinstance(a, Field)), None)
            value = getattr(self, field_name, None)
            v = str(value)
            if mask_secrets and v and field and field.secret:
                if len(v) > 10:
                    v = f"{v[:6]}{'*' * (len(v) - 10)}{v[-4:]}"
                elif len(v) > 4:
                    v = f"{v[:4]}{'*' * (len(v) - 4)}"
                else:
                    v = "*" * len(v)
            rows.append(f"{field_name}: {v}")
        return "\n".join(rows)

    def validate_configs(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        field_env_names: dict[str, tuple[str, ...] | str] = {}
        errors: list[tuple[str, str]] = []
        for field_name, hint in get_type_hints(type(self), include_extras=True).items():
            field = next((a for a in get_args(hint) if isinstance(a, Field)), None)
            if field is None:
                continue
            if env_names := field.env_names:
                if len(env_names) > 1:
                    field_env_names[field_name] = env_names
                elif len(env_names) == 1:
                    field_env_names[field_name] = env_names[0]
            value = getattr(self, field_name, None)
            if not value:
                if field.required:
                    msg = f"Field '{field_name}' is required but not set; try setting the environment variable(s) {field.env_names}"
                    errors.append((field_name, msg))
                continue

        # Check fields combination rules:
        if not self.SN_IMAGE_GEN_MODEL:
            errors.append((
                "SN_IMAGE_GEN_MODEL",
                f"SN_IMAGE_GEN_MODEL is required when SN_IMAGE_GEN_MODEL_TYPE is {self.SN_IMAGE_GEN_MODEL_TYPE!r}",
            ))

        warnings: list[tuple[str, str]] = []
        runtime_checks = {
            "text": {
                "api_key": ("SN_TEXT_API_KEY", "SN_CHAT_API_KEY"),
                "base_url": ("SN_TEXT_BASE_URL", "SN_CHAT_BASE_URL"),
                "model": ("SN_TEXT_MODEL", "SN_CHAT_MODEL"),
                "type": ("SN_TEXT_TYPE", "SN_CHAT_TYPE"),
            },
            "vision": {
                "api_key": ("SN_VISION_API_KEY", "SN_CHAT_API_KEY"),
                "base_url": ("SN_VISION_BASE_URL", "SN_CHAT_BASE_URL"),
                "model": ("SN_VISION_MODEL", "SN_CHAT_MODEL"),
                "type": ("SN_VISION_TYPE", "SN_CHAT_TYPE"),
            },
        }
        for runtime, checks in runtime_checks.items():
            for field_kind, keys in checks.items():
                if any(getattr(self, key) for key in keys):
                    continue
                env_help = " / ".join(
                    ", ".join(field_env_names[key])
                    if isinstance(field_env_names.get(key), tuple)
                    else str(field_env_names.get(key, key))
                    for key in keys
                )
                warnings.append((
                    keys[0],
                    f"{keys[0]} is not set; {runtime} {field_kind} may be unavailable. Try setting: {env_help}",
                ))

        # check urls
        errors.extend(
            (
                key,
                f"{key} is not a valid base URL: {getattr(self, key)}",
            )
            for key in ("SN_CHAT_BASE_URL", "SN_TEXT_BASE_URL", "SN_VISION_BASE_URL")
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
            field_name: The name of the configuration field (e.g., "SN_CHAT_API_KEY").

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


def reload_env() -> None:
    global global_configs

    prepare_env()
    try:
        global_configs = Configs()
        print("✅ Reloaded global_configs")
    except Exception as e:
        warnings.warn(f"Failed to reload global_configs: {e}", stacklevel=2)


global_configs = Configs()
