import os
import warnings
from typing import Annotated, Literal, get_args, get_origin, get_type_hints

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    warnings.warn("python-dotenv is not installed, `.env` file will be ignored", stacklevel=2)


class EnvVar:
    """Metadata marker that pairs a field with one or more env var names.

    Env vars are tried in order; the first env var that is set is returned.
    """

    __slots__ = ("env_names",)

    def __init__(self, *env_names: str) -> None:
        self.env_names = env_names

    def resolve(self, target_type: type | None = None) -> str | int | float | None:
        """Return the first env var value that is set, converted to target_type.

        Args:
            target_type: The type to convert to (str, int, float, etc.) or None.
                If not int or float, returns the raw string.

        Returns:
            The converted value, or None if none of the env vars exist.
        """
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
    U1_API_KEY: Annotated[str, EnvVar("U1_API_KEY")] = ""
    U1_IMAGE_GEN_BASE_URL: Annotated[
        str,
        EnvVar("U1_IMAGE_GEN_BASE_URL", "U1_BASE_URL"),
    ] = "https://zoe-api.sensetime.com/zoe-model"

    # NOTE: "U1_LM_*" vars are shared between VLM and LLM
    # image-recognize (VLM) — falls back to shared U1_LM_* vars
    VLM_API_KEY: Annotated[str, EnvVar("VLM_API_KEY", "U1_LM_API_KEY")] = "dummy"
    VLM_BASE_URL: Annotated[str, EnvVar("VLM_BASE_URL", "U1_LM_BASE_URL")] = ""
    VLM_MODEL: Annotated[str, EnvVar("VLM_MODEL", "U1_LM_MODEL")] = "sensenova-122b-128k-step9k"
    VLM_TYPE: Annotated[
        Literal["anthropic-messages", "openai-completions"],
        EnvVar("VLM_TYPE", "U1_LM_TYPE"),
    ] = "openai-completions"

    # text-optimize (LLM) — falls back to shared U1_LM_* vars
    LLM_API_KEY: Annotated[str, EnvVar("LLM_API_KEY", "U1_LM_API_KEY")] = "dummy"
    LLM_BASE_URL: Annotated[str, EnvVar("LLM_BASE_URL", "U1_LM_BASE_URL")] = ""
    LLM_MODEL: Annotated[str, EnvVar("LLM_MODEL", "U1_LM_MODEL")] = "sensenova-122b-128k-step9k"
    LLM_TYPE: Annotated[
        Literal["anthropic-messages", "openai-completions"],
        EnvVar("LLM_TYPE", "U1_LM_TYPE"),
    ] = "openai-completions"

    def __init__(self) -> None:
        for field, hint in get_type_hints(type(self), include_extras=True).items():
            env_var = next((a for a in get_args(hint) if isinstance(a, EnvVar)), None)
            if env_var is None:
                continue
            # Extract the actual type (unwrap Annotated, handle Literal)
            origin = get_origin(hint)
            if origin is Annotated:
                actual_type = get_args(hint)[0]
            else:
                actual_type = hint
            if (val := env_var.resolve(actual_type)) is not None:
                setattr(self, field, val)


global_configs = Configs()
