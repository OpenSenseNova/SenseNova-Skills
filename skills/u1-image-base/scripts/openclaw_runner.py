"""OpenClaw unified runner for u1-image-base skills.

All tools are invoked as async coroutines and executed via asyncio.run().

Usage:
    python openclaw_runner.py u1-image-generate --prompt "..."
    python openclaw_runner.py u1-image-edit --image "..." --prompt "..."
    python openclaw_runner.py u1-image-recognize --user-prompt "..." --images "..." --api-key "..." --base-url "..." --model "..."
    python openclaw_runner.py u1-text-optimize --user-prompt "..." --api-key "..." --base-url "..." --model "..."
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from exceptions import MissingApiKeyError
from generation.text_to_image import TextToImageClient
from image_edit.image_edit import ImageEditClient
from llm.anthropic_adapter import AnthropicMessagesAdapter
from llm.chat_completions_adapter import ChatCompletionsLlmAdapter
from vlm.anthropic_adapter import AnthropicVlmAdapter
from vlm.chat_completions_adapter import ChatCompletionsVlmAdapter

API_KEY_ENV = "U1_API_KEY"
BASE_URL_ENV = "U1_BASE_URL"

# Shared built-in defaults for VLM (image-recognize) and LLM (text-optimize)
# No hardcoded defaults - must be supplied via env var or CLI
DEFAULT_BASE_URL = ""
DEFAULT_MODEL = ""
DEFAULT_API_KEY = ""
DEFAULT_TYPE = "openai-completions"


def _resolve_param(cli_value: str | None, env_name: str, default: str) -> str:
    """Resolve a parameter using CLI > env > default priority."""
    return cli_value or os.getenv(env_name, "") or default


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
            Configured parser with subcommands for u1-image-generate,
            u1-image-edit, u1-image-recognize, and u1-text-optimize.
    """
    parser = argparse.ArgumentParser(
        description="u1-image-base unified runner - async tool execution."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # u1-image-generate
    gen_parser = subparsers.add_parser(
        "u1-image-generate", help="Generate image from text prompt (U1 API)"
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
        "--api-key", default="", help="API key (falls back to U1_API_KEY env var)"
    )
    gen_parser.add_argument(
        "--base-url",
        default="",
        help="API base URL (falls back to U1_BASE_URL env var)",
    )
    gen_parser.add_argument("--poll-interval", type=float, default=5.0)
    gen_parser.add_argument("--timeout", type=float, default=300.0)
    gen_parser.add_argument("--insecure", action="store_true", help="Disable TLS verification")
    gen_parser.add_argument("-o", "--output-format", choices=["text", "json"], default="text")
    gen_parser.add_argument("--save-path", type=Path, default=None)

    # u1-image-edit
    edit_parser = subparsers.add_parser("u1-image-edit", help="Edit image based on prompt (U1 API)")
    edit_parser.add_argument(
        "--image",
        required=True,
        help="Local image path, remote URL, or cached file key",
    )
    edit_parser.add_argument("--prompt", required=True, help="Edit instruction prompt")
    edit_parser.add_argument("--seed", type=int, default=None, help="Random seed")
    edit_parser.add_argument(
        "--api-key", default="", help="API key (falls back to U1_API_KEY env var)"
    )
    edit_parser.add_argument(
        "--base-url",
        default="",
        help="API base URL (falls back to U1_BASE_URL env var)",
    )
    edit_parser.add_argument("--poll-interval", type=float, default=5.0)
    edit_parser.add_argument("--timeout", type=float, default=300.0)
    edit_parser.add_argument("--insecure", action="store_true")
    edit_parser.add_argument("-o", "--output-format", choices=["text", "json"], default="text")
    edit_parser.add_argument("--save-path", type=Path, default=None)

    # u1-image-recognize (VLM)
    recog_parser = subparsers.add_parser(
        "u1-image-recognize", help="Recognize image content using VLM"
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
        help="API base URL (CLI > VLM_BASE_URL > U1_LM_BASE_URL > built-in default)",
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

    # u1-text-optimize (LLM)
    opt_parser = subparsers.add_parser("u1-text-optimize", help="Optimize text using LLM")
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
        help="API base URL (CLI > LLM_BASE_URL > U1_LM_BASE_URL > built-in default)",
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
    api_key = args.api_key or os.getenv(API_KEY_ENV, "")
    if not api_key:
        raise MissingApiKeyError()

    base_url = args.base_url or os.getenv(BASE_URL_ENV, "")
    if not base_url:
        raise MissingApiKeyError(
            "No base URL provided. Set U1_BASE_URL env var or pass --base-url."
        )

    client = TextToImageClient(
        api_key=api_key,
        base_url=base_url,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
        insecure=args.insecure,
    )
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


async def run_image_edit(args: argparse.Namespace) -> tuple[dict, int]:
    """Run image-edit command using the U1 image-edit API.

    Args:
        args: Parsed command-line arguments from ``image-edit`` subcommand.

    Returns:
        tuple[dict, int]:
            A (result_dict, exit_code) pair. result_dict contains status,
            output (image path), task_id, and message. exit_code is 0 on
            success and 1 on failure.
    """
    api_key = args.api_key or os.getenv(API_KEY_ENV, "")
    if not api_key:
        raise MissingApiKeyError()

    base_url = args.base_url or os.getenv(BASE_URL_ENV, "")
    if not base_url:
        raise MissingApiKeyError(
            "No base URL provided. Set U1_BASE_URL env var or pass --base-url."
        )

    client = ImageEditClient(
        api_key=api_key,
        base_url=base_url,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
        insecure=args.insecure,
    )
    try:
        result = await client.edit(
            image=args.image,
            prompt=args.prompt,
            seed=args.seed,
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

    vlm_type = _resolve_param(args.vlm_type, "VLM_TYPE", DEFAULT_TYPE)
    base_url = _resolve_param(
        args.base_url, "VLM_BASE_URL", os.getenv("U1_LM_BASE_URL", DEFAULT_BASE_URL)
    )
    model = _resolve_param(args.model, "VLM_MODEL", DEFAULT_MODEL)
    api_key = args.api_key or os.getenv("VLM_API_KEY", "") or os.getenv("U1_LM_API_KEY", "")
    if not api_key:
        raise MissingApiKeyError(
            "No API key provided for VLM. Set VLM_API_KEY, U1_LM_API_KEY, or pass --api-key."
        )
    if not base_url:
        raise MissingApiKeyError(
            "No base URL provided for VLM. Set VLM_BASE_URL, U1_LM_BASE_URL, or pass --base-url."
        )
    if not model:
        raise MissingApiKeyError("No model provided for VLM. Set VLM_MODEL or pass --model.")

    if vlm_type == "anthropic-messages":
        adapter = AnthropicVlmAdapter(
            endpoint_url=f"{base_url.rstrip('/')}/v1/messages",
            api_key=api_key,
            model=model,
        )
    else:
        adapter = ChatCompletionsVlmAdapter(
            endpoint_url=f"{base_url.rstrip('/')}/v1/chat/completions",
            api_key=api_key,
            model=model,
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

    llm_type = _resolve_param(args.llm_type, "LLM_TYPE", DEFAULT_TYPE)
    base_url = _resolve_param(
        args.base_url, "LLM_BASE_URL", os.getenv("U1_LM_BASE_URL", DEFAULT_BASE_URL)
    )
    model = _resolve_param(args.model, "LLM_MODEL", DEFAULT_MODEL)
    api_key = args.api_key or os.getenv("LLM_API_KEY", "") or os.getenv("U1_LM_API_KEY", "")
    if not api_key:
        raise MissingApiKeyError(
            "No API key provided for LLM. Set LLM_API_KEY, U1_LM_API_KEY, or pass --api-key."
        )
    if not base_url:
        raise MissingApiKeyError(
            "No base URL provided for LLM. Set LLM_BASE_URL, U1_LM_BASE_URL, or pass --base-url."
        )
    if not model:
        raise MissingApiKeyError("No model provided for LLM. Set LLM_MODEL or pass --model.")

    if llm_type == "anthropic-messages":
        adapter = AnthropicMessagesAdapter(
            endpoint_url=f"{base_url.rstrip('/')}/v1/messages",
            api_key=api_key,
            model=model,
        )
    else:
        adapter = ChatCompletionsLlmAdapter(
            endpoint_url=f"{base_url.rstrip('/')}/v1/chat/completions",
            api_key=api_key,
            model=model,
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


async def output_result(output_format: str, result: dict, elapsed: float | None = None) -> int:
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
            # text-optimize/image-recognize use "result", image-generate/image-edit use "output"
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
        if args.command == "u1-image-generate":
            result, code = await run_image_generate(args)
        elif args.command == "u1-image-edit":
            result, code = await run_image_edit(args)
        elif args.command == "u1-image-recognize":
            result, code = await run_image_recognize(args)
        elif args.command == "u1-text-optimize":
            result, code = await run_text_optimize(args)
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            return 1

        elapsed = round(time.time() - start_time, 2)
        return await output_result(args.output_format, result, elapsed)

    except MissingApiKeyError as exc:
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
    """Entry point for the openclaw_runner CLI.

    Returns:
        int: Exit code from the async dispatcher.
    """
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
