"""OpenClaw unified runner for sn-image-base skills.

All tools are invoked as async coroutines and executed via asyncio.run().

Usage:
    python sn_agent_runner.py sn-image-generate --prompt "..."
    python sn_agent_runner.py sn-image-recognize --user-prompt "..." --images "..." --api-key "..." --base-url "..." --model "..."
    python sn_agent_runner.py sn-text-optimize --user-prompt "..." --api-key "..." --base-url "..." --model "..."
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import cast

SCRIPT_DIR = Path(__file__).resolve().parent
if (d := str(SCRIPT_DIR)) not in sys.path:
    sys.path.insert(0, d)

from sn_image_base.configs import global_configs, is_valid_base_url, urlparse
from sn_image_base.exceptions import (
    BadConfigurationError,
    InvalidBaseUrlError,
    MissingApiKeyError,
    U1BaseError,
)
from sn_image_base.generation import (
    NanoBananaText2ImageClient,
    OpenAIImageGenerationClient,
    SensenovaText2ImageClient,
    U1Text2ImageClient,
)
from sn_image_base.llm import AnthropicMessagesAdapter, ChatCompletionsLlmAdapter
from sn_image_base.vlm import AnthropicVlmAdapter, ChatCompletionsVlmAdapter


def _resolve_prompt(
    direct: str | None,
    path: str | None,
    required: bool,
    name: str,
) -> str:
    """Resolve a prompt value from either a direct string or a file path.

    Raises ValueError on mutual exclusion, missing required value, or file read failure.
    """
    if direct is not None and path is not None:
        raise ValueError(
            f"Cannot use both --{name} and --{name}-path; they are mutually exclusive."
        )
    if required and not direct and not path:
        raise ValueError(f"--{name} or --{name}-path is required.")
    if path is not None:
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except OSError as exc:
            raise ValueError(f"Failed to read {name} from file {path}: {exc}") from exc
    return direct or ""


def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser.

    Returns:
        argparse.ArgumentParser:
            Configured parser with subcommands for sn-image-generate,
            sn-image-recognize, and sn-text-optimize.
    """
    parser = argparse.ArgumentParser(
        description="sn-image-base unified runner - async tool execution."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sn-image-generate
    gen_parser = subparsers.add_parser(
        "sn-image-generate", help="Generate image from text prompt (U1 API)"
    )
    gen_parser.add_argument("--prompt", required=True, help="Text prompt for image generation")
    gen_parser.add_argument("--negative-prompt", default="", help="Negative prompt")
    gen_parser.add_argument(
        "--image-size", default="2k", choices=["1k", "2k"], help="Image size preset"
    )
    gen_parser.add_argument(
        "--aspect-ratio",
        default="16:9",
        choices=[
            "2:3",
            "3:2",
            "3:4",
            "4:3",
            "4:5",
            "5:4",
            "1:1",
            "16:9",
            "9:16",
            "21:9",
            "9:21",
        ],
        help="Aspect ratio",
    )
    gen_parser.add_argument("--seed", type=int, default=None, help="Random seed")
    gen_parser.add_argument("--unet-name", dest="unet_name", default=None, help="UNet model name")
    gen_parser.add_argument(
        "--api-key", default="", help="API key (falls back to SN_API_KEY env var)"
    )
    gen_parser.add_argument(
        "--base-url",
        default="",
        help="API base URL (falls back to SN_BASE_URL env var)",
    )
    gen_parser.add_argument("--poll-interval", type=float, default=5.0)
    gen_parser.add_argument("--timeout", type=float, default=300.0)
    gen_parser.add_argument("--insecure", action="store_true", help="Disable TLS verification")
    gen_parser.add_argument("-o", "--output-format", choices=["text", "json"], default="text")
    gen_parser.add_argument("--save-path", type=Path, default=None)

    # sn-image-recognize (VLM)
    recog_parser = subparsers.add_parser(
        "sn-image-recognize", help="Recognize image content using VLM"
    )
    recog_parser.add_argument("--user-prompt", default=None, help="User-facing text instruction")
    recog_parser.add_argument(
        "--user-prompt-path",
        default=None,
        help="Path to a local file containing the user prompt (mutually exclusive with --user-prompt)",
    )
    recog_parser.add_argument("--system-prompt", default=None, help="System-level instruction")
    recog_parser.add_argument(
        "--system-prompt-path",
        default=None,
        help="Path to a local file containing the system prompt (mutually exclusive with --system-prompt)",
    )
    recog_parser.add_argument("--images", required=True, nargs="+", help="Image file paths or URLs")
    recog_parser.add_argument(
        "--api-key", default=None, help="API key (CLI > VLM_API_KEY env > dummy-key)"
    )
    recog_parser.add_argument(
        "--base-url",
        default=None,
        help="API base URL (CLI > VLM_BASE_URL > SN_LM_BASE_URL > built-in default)",
    )
    recog_parser.add_argument(
        "--model",
        default=None,
        help="Model name (CLI > VLM_MODEL env > built-in default)",
    )
    recog_parser.add_argument(
        "--vlm-type",
        default=None,
        choices=["openai-completions", "anthropic-messages"],
        help="VLM interface type (CLI > VLM_TYPE env > openai-completions)",
    )
    recog_parser.add_argument("-o", "--output-format", choices=["text", "json"], default="text")

    # sn-text-optimize (LLM)
    opt_parser = subparsers.add_parser("sn-text-optimize", help="Optimize text using LLM")
    opt_parser.add_argument("--user-prompt", default=None, help="User-facing text instruction")
    opt_parser.add_argument(
        "--user-prompt-path",
        default=None,
        help="Path to a local file containing the user prompt (mutually exclusive with --user-prompt)",
    )
    opt_parser.add_argument("--system-prompt", default=None, help="System-level instruction")
    opt_parser.add_argument(
        "--system-prompt-path",
        default=None,
        help="Path to a local file containing the system prompt (mutually exclusive with --system-prompt)",
    )
    opt_parser.add_argument(
        "--api-key", default=None, help="API key (CLI > LLM_API_KEY env > dummy-key)"
    )
    opt_parser.add_argument(
        "--base-url",
        default=None,
        help="API base URL (CLI > LLM_BASE_URL > SN_LM_BASE_URL > built-in default)",
    )
    opt_parser.add_argument(
        "--model",
        default=None,
        help="Model name (CLI > LLM_MODEL env > built-in default)",
    )
    opt_parser.add_argument(
        "--llm-type",
        default=None,
        choices=["openai-completions", "anthropic-messages"],
        help="LLM interface type (CLI > LLM_TYPE env > openai-completions)",
    )
    opt_parser.add_argument("-o", "--output-format", choices=["text", "json"], default="text")

    return parser


async def run_image_generate(args: argparse.Namespace) -> tuple[dict, int]:
    """Run image-generate command using the U1 text-to-image API.

    Args:
        args: Parsed command-line arguments from ``image-generate`` subcommand.

    Returns:
        tuple[dict, int]:
            A (result_dict, exit_code) pair. result_dict contains status,
            output (image path), task_id, and message. exit_code is 0 on
            success and 1 on failure.
    """
    api_key = args.api_key or global_configs.SN_API_KEY
    if not api_key:
        raise MissingApiKeyError()

    base_url = args.base_url or global_configs.SN_IMAGE_GEN_BASE_URL
    if not base_url:
        raise InvalidBaseUrlError(
            "No base URL provided. Set SN_BASE_URL env var or pass --base-url."
        )

    if global_configs.SN_IMAGE_GEN_MODEL_TYPE == "sensenova":
        if not global_configs.SN_IMAGE_GEN_MODEL:
            env_var_help = global_configs.get_env_var_help("SN_IMAGE_GEN_MODEL")
            raise BadConfigurationError(f"No model provided. {env_var_help}")
        client = SensenovaText2ImageClient(
            api_key=api_key,
            base_url=base_url,
            model=global_configs.SN_IMAGE_GEN_MODEL,
            timeout=args.timeout,
            ssl_verify=not args.insecure,
        )
        print(f"Using SenseNova model {global_configs.SN_IMAGE_GEN_MODEL!r} for image generation")
    elif global_configs.SN_IMAGE_GEN_MODEL_TYPE == "nano-banana":
        if not global_configs.SN_IMAGE_GEN_MODEL:
            env_var_help = global_configs.get_env_var_help("SN_IMAGE_GEN_MODEL")
            raise BadConfigurationError(f"No model provided. {env_var_help}")
        client = NanoBananaText2ImageClient(
            api_key=api_key,
            base_url=base_url,
            model=global_configs.SN_IMAGE_GEN_MODEL,
            timeout=args.timeout,
            ssl_verify=not args.insecure,
        )
        print(f"Using Nano Banana model {global_configs.SN_IMAGE_GEN_MODEL!r} for image generation")
    elif global_configs.SN_IMAGE_GEN_MODEL_TYPE == "openai-image":
        if not global_configs.SN_IMAGE_GEN_MODEL:
            env_var_help = global_configs.get_env_var_help("SN_IMAGE_GEN_MODEL")
            raise BadConfigurationError(f"No model provided. {env_var_help}")
        client = OpenAIImageGenerationClient(
            api_key=api_key,
            base_url=base_url,
            model=global_configs.SN_IMAGE_GEN_MODEL,
        )
        print(
            f"Using OpenAI-compatible model {global_configs.SN_IMAGE_GEN_MODEL!r} for image generation"
        )
    else:
        client = U1Text2ImageClient(
            api_key=api_key,
            base_url=base_url,
            poll_interval=args.poll_interval,
            timeout=args.timeout,
            ssl_verify=not args.insecure,
        )
        print(f"Using U1 model {global_configs.SN_IMAGE_GEN_MODEL!r} for image generation")
    try:
        result = await client.generate(
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            image_size=args.image_size,
            aspect_ratio=args.aspect_ratio,
            seed=args.seed,
            unet_name=args.unet_name,
            output_path=args.save_path,
        )
        return result, 0 if result["status"] == "ok" else 1
    finally:
        await client.aclose()


async def run_image_recognize(args: argparse.Namespace) -> tuple[dict, int]:
    """Run image-recognize command using a VLM adapter.

    Args:
        args: Parsed command-line arguments from ``image-recognize`` subcommand.

    Returns:
        tuple[dict, int]:
            A (result_dict, exit_code) pair. result_dict contains status,
            result (model response text), model, base_url, and interface_type.
            exit_code is 0 on success and 1 on failure.
    """
    user_prompt = _resolve_prompt(
        args.user_prompt, args.user_prompt_path, required=True, name="user-prompt"
    )
    system_prompt = _resolve_prompt(
        args.system_prompt,
        args.system_prompt_path,
        required=False,
        name="system-prompt",
    )

    vlm_type, base_url, model, api_key = _resolve_model_runtime("vlm", args)
    adapter = cast(
        "AnthropicVlmAdapter | ChatCompletionsVlmAdapter",
        _build_endpoint_and_adapter("vlm", vlm_type, base_url, model, api_key),
    )
    try:
        result_text = await adapter.vision_completion(
            user_prompt=user_prompt,
            images=args.images,
            system_prompt=system_prompt,
            model=model,
        )
        return {
            "status": "ok",
            "result": result_text,
            "model": model,
            "base_url": base_url,
            "interface_type": vlm_type,
        }, 0
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}, 1
    finally:
        await adapter.aclose()


async def run_text_optimize(args: argparse.Namespace) -> tuple[dict, int]:
    """Run text-optimize command using an LLM adapter.

    Args:
        args: Parsed command-line arguments from ``text-optimize`` subcommand.

    Returns:
        tuple[dict, int]:
            A (result_dict, exit_code) pair. result_dict contains status,
            result (model response text), model, base_url, and interface_type.
            exit_code is 0 on success and 1 on failure.
    """
    user_prompt = _resolve_prompt(
        args.user_prompt, args.user_prompt_path, required=True, name="user-prompt"
    )
    system_prompt = _resolve_prompt(
        args.system_prompt,
        args.system_prompt_path,
        required=False,
        name="system-prompt",
    )

    llm_type, base_url, model, api_key = _resolve_model_runtime("llm", args)
    adapter = cast(
        "AnthropicMessagesAdapter | ChatCompletionsLlmAdapter",
        _build_endpoint_and_adapter("llm", llm_type, base_url, model, api_key),
    )
    try:
        result_text = await adapter.text_completion(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            model=model,
        )
        return {
            "status": "ok",
            "result": result_text,
            "model": model,
            "base_url": base_url,
            "interface_type": llm_type,
        }, 0
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}, 1
    finally:
        await adapter.aclose()


def _resolve_model_runtime(kind: str, args: argparse.Namespace) -> tuple[str, str, str, str]:
    """Resolve and validate model runtime settings for VLM/LLM.

    Returns:
        tuple[str, str, str, str]:
            (interface_type, base_url, model, api_key).
    """
    if kind == "vlm":
        iface_type = args.vlm_type or global_configs.VLM_TYPE
        base_url = args.base_url or global_configs.VLM_BASE_URL
        model = args.model or global_configs.VLM_MODEL
        api_key = args.api_key or global_configs.VLM_API_KEY
        label = "VLM"
        key_env = "VLM_API_KEY, SN_LM_API_KEY"
        url_env = "VLM_BASE_URL, SN_LM_BASE_URL"
        model_env = "VLM_MODEL"
    elif kind == "llm":
        iface_type = args.llm_type or global_configs.LLM_TYPE
        base_url = args.base_url or global_configs.LLM_BASE_URL
        model = args.model or global_configs.LLM_MODEL
        api_key = args.api_key or global_configs.LLM_API_KEY
        label = "LLM"
        key_env = "LLM_API_KEY, SN_LM_API_KEY"
        url_env = "LLM_BASE_URL, SN_LM_BASE_URL"
        model_env = "LLM_MODEL"
    else:
        raise ValueError(f"Unsupported runtime kind: {kind}")

    if not api_key:
        raise MissingApiKeyError(
            f"No API key provided for {label}. Set {key_env}, or pass --api-key."
        )
    if not base_url:
        raise InvalidBaseUrlError(
            f"No base URL provided for {label}. Set {url_env}, or pass --base-url."
        )
    if not is_valid_base_url(base_url):
        raise InvalidBaseUrlError(f"Invalid base URL: {base_url}")
    if not model:
        raise BadConfigurationError(
            f"No model provided for {label}. Set {model_env} or pass --model."
        )
    return iface_type, base_url, model, api_key


def _build_endpoint_and_adapter(
    kind: str, iface_type: str, base_url: str, model: str, api_key: str
):
    """Build endpoint URL and instantiate the matching adapter."""
    base_url_obj = urlparse(base_url.rstrip("/"))

    if iface_type == "anthropic-messages":
        endpoint = "/v1/messages" if not base_url_obj.path else "/messages"
        endpoint_url = f"{base_url_obj.geturl()}{endpoint}"
        if kind == "vlm":
            adapter = AnthropicVlmAdapter(
                endpoint_url=endpoint_url,
                api_key=api_key,
                model=model,
            )
            print(f"Using Anthropic VLM adapter for {model!r} on {endpoint_url!r}")
        elif kind == "llm":
            adapter = AnthropicMessagesAdapter(
                endpoint_url=endpoint_url,
                api_key=api_key,
                model=model,
            )
            print(f"Using Anthropic LLM adapter for {model!r} on {endpoint_url!r}")
        else:
            raise ValueError(f"Unsupported runtime kind: {kind}")
    else:
        endpoint = "/v1/chat/completions" if not base_url_obj.path else "/chat/completions"
        endpoint_url = f"{base_url_obj.geturl()}{endpoint}"
        if kind == "vlm":
            adapter = ChatCompletionsVlmAdapter(
                endpoint_url=endpoint_url,
                api_key=api_key,
                model=model,
            )
            print(f"Using OpenAI VLM adapter for {model!r} on {endpoint_url!r}")
        elif kind == "llm":
            adapter = ChatCompletionsLlmAdapter(
                endpoint_url=endpoint_url,
                api_key=api_key,
                model=model,
            )
            print(f"Using OpenAI LLM adapter for {model!r} on {endpoint_url!r}")
        else:
            raise ValueError(f"Unsupported runtime kind: {kind}")

    return adapter


def _output_result(output_format: str, result: dict, elapsed: float | None = None) -> int:
    """Print the result in the specified format and return the appropriate exit code.

    Args:
        output_format: Either ``"text"`` or ``"json"``.
        result: Result dictionary with at least a ``status`` key ("ok" or "failed").
        elapsed: Optional elapsed time in seconds; appended to result as
            ``elapsed_seconds`` when provided.

    Returns:
        int: Exit code (0 if status is "ok", 1 otherwise).
    """
    if elapsed is not None:
        result["elapsed_seconds"] = elapsed
    if output_format == "json":
        print(json.dumps(result, ensure_ascii=False))
    else:
        if result["status"] == "ok":
            if result.get("message"):
                print(result["message"])
            # text-optimize/image-recognize use "result", image-generate uses "output"
            print(result.get("result") or result.get("output") or "")
        else:
            print(result.get("message") or result["error"], file=sys.stderr)
    return 0 if result["status"] == "ok" else 1


async def main_async(args: argparse.Namespace) -> int:
    """Dispatch to the appropriate command handler.

    Args:
        args: Parsed command-line arguments from any subcommand.

    Returns:
        int: Exit code (0 on success, 1 on failure).
    """
    start_time = time.time()
    try:
        if args.command == "sn-image-generate":
            result, _code = await run_image_generate(args)
        elif args.command == "sn-image-recognize":
            result, _code = await run_image_recognize(args)
        elif args.command == "sn-text-optimize":
            result, _code = await run_text_optimize(args)
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            return 1

        elapsed = round(time.time() - start_time, 2)
        return _output_result(args.output_format, result, elapsed)

    except U1BaseError as exc:
        elapsed = round(time.time() - start_time, 2)
        if args.output_format == "json":
            print(
                json.dumps(
                    {"status": "failed", "error": str(exc), "elapsed_seconds": elapsed},
                    ensure_ascii=False,
                )
            )
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    except ValueError as exc:
        elapsed = round(time.time() - start_time, 2)
        if args.output_format == "json":
            print(
                json.dumps(
                    {"status": "failed", "error": str(exc), "elapsed_seconds": elapsed},
                    ensure_ascii=False,
                )
            )
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    """Entry point for the sn_agent_runner CLI.

    Returns:
        int: Exit code from the async dispatcher.
    """
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
