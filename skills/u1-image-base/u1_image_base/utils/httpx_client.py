"""Shared httpx async client factory for vigeneval evaluators.

Centralizes connection pool limits, pool timeout, and optional file descriptor
limit check to avoid PoolTimeout and 'Too many open files' under high concurrency.
"""

import contextlib
import json
import resource
from typing import Any

import httpx

from .error_utils import (
    U1HttpAuthError,
    U1HttpBadRequestError,
    U1HttpNotFoundError,
    U1HttpServerError,
    U1HttpTooManyRequestsError,
)


def check_file_descriptor_limit(max_connections: int, margin: int = 200) -> None:
    """Raise if process file descriptor limit is too low for max_connections.

    Avoids 'Too many open files' mid-run when using a large httpx connection pool.
    No-op on Windows or when resource module has no RLIMIT_NOFILE.

    Args:
        max_connections: Intended httpx pool max_connections.
        margin: Extra FDs to reserve for app (logs, other files). Default 200.

    Raises:
        RuntimeError: If soft limit < max_connections + margin.
    """
    try:
        soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    except (ImportError, AttributeError, OSError):
        return
    required = max_connections + margin
    if soft < required:
        raise RuntimeError(
            f"File descriptor limit too low for max_connections={max_connections}. "
            f"Current soft limit: {soft}, need at least {required}. "
            "Raise the limit before running, e.g.: ulimit -n 2048  # or higher, then re-run."
        )


def create_async_httpx_client(
    headers: dict[str, str],
    *,
    timeout: float = 600.0,
    max_connections: int = 500,
    pool_timeout: float = 60.0,
    check_fd_limit: bool = False,
    verify: bool = True,
    **client_kwargs: Any,
) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient with shared defaults for vigeneval evaluators.

    Automatically uses proxy from environment variables (HTTPS_PROXY, HTTP_PROXY, etc.)
    when trust_env=True (default). Supports proxy authentication via URL format:
    http://username:password@proxy_host:port

    Connection pool limits and pool timeout help avoid PoolTimeout under high concurrency.
    Optionally checks process file descriptor limit before creating the client.

    Args:
        headers: Request headers (e.g. Content-Type, Authorization).
        timeout: Request timeout in seconds. Default 600.
        max_connections: Connection pool size. Default 500; use 1000 for batch
            high parallelism (and check_fd_limit=True).
        pool_timeout: Max seconds to wait for a connection from the pool. Default 60.
        check_fd_limit: If True, call check_file_descriptor_limit(max_connections)
            and raise before creating the client. Use for batch evaluators.
        verify: If False, disable SSL certificate verification (avoids
            CERTIFICATE_VERIFY_FAILED). Use only for dev/testing or trusted networks.
        **client_kwargs: Passed through to httpx.AsyncClient (e.g. base_url).

    Returns:
        A new httpx.AsyncClient. Caller must aclose() when done.

    Example:
        # Set proxy with authentication in environment
        export HTTP_PROXY="http://user:pass@proxy.example.com:3128"
        export HTTPS_PROXY="http://user:pass@proxy.example.com:3128"

        # Create client - proxy is automatically used
        client = create_async_httpx_client(
            headers={"Authorization": "Bearer token"},
            max_connections=100,
        )
    """
    if check_fd_limit:
        check_file_descriptor_limit(max_connections)

    # Note: Proxy configuration is handled automatically by httpx when trust_env=True.
    # We don't need to explicitly read or pass proxy URLs - httpx will read from
    # environment variables (HTTPS_PROXY, HTTP_PROXY, etc.) and handle authentication.

    limits = httpx.Limits(
        max_connections=max_connections,
        max_keepalive_connections=min(400, max_connections),
        keepalive_expiry=30.0,
    )

    # Create transport without explicit proxy parameter when trust_env=True
    # This allows httpx to properly handle proxy authentication from environment
    transport = httpx.AsyncHTTPTransport(
        verify=verify,
        trust_env=True,
        local_address="0.0.0.0",
        limits=limits,
    )

    # Create client with trust_env=True to enable proxy from environment
    return httpx.AsyncClient(
        transport=transport,
        headers=headers,
        timeout=httpx.Timeout(timeout, pool=pool_timeout),
        verify=verify,
        trust_env=True,  # Enable reading proxy from environment variables
        **client_kwargs,
    )


def httpx_response_raise_for_status_code(response: httpx.Response) -> None:
    """Check httpx response status code and raise appropriate exceptions.

    Args:
        response: The httpx response object.
        verbose: Whether to log verbose information.

    Raises:
        AuthError: If response status is 401 or 403.
        APIError: If response status is 429 or 5xx.
        InvalidRequestError: If response status is 4xx (except 401, 403, 429).
    """
    # Try best effort to parse response content & headers
    response_headers = "[N/A]"  # Not available
    response_content = "[N/A]"  # Not available
    request_url = "[N/A]"
    request_method = "[N/A]"
    with contextlib.suppress(Exception):
        response_headers = response.headers
        response_headers = dict(response_headers)
    with contextlib.suppress(Exception):
        response_content = response.content
        response_content = response_content.decode("utf-8")
        response_content = json.loads(response_content)
    with contextlib.suppress(Exception):
        request_method = response.request.method
        request_method = request_method.upper()
        request_url = str(response.request.url)

    if response.status_code == 404:
        raise U1HttpNotFoundError(
            detail=f"{request_method} {request_url!r} not found. Please check the URL and the model name.",
            code=response.status_code,
        )
    if response.status_code in (401, 403):
        raise U1HttpAuthError(
            detail=f"Authentication or authorization failed. {request_method} {request_url!r}. Response content: {response_content}",
            code=response.status_code,
        )
    elif response.status_code in (429, 503):
        raise U1HttpTooManyRequestsError(
            detail=f"Service temporarily unavailable. Please try again later. {request_method} {request_url!r}. Response content: {response_content}",
            code=response.status_code,
        )
    elif 500 <= response.status_code <= 599:
        raise U1HttpServerError(
            detail=f"Request failed. {request_method} {request_url!r}. Response content: {response_content}",
            code=response.status_code,
        )
    elif 400 <= response.status_code <= 499:
        raise U1HttpBadRequestError(
            detail=f"Bad request. {request_method} {request_url!r}. Response content: {response_content}",
            code=response.status_code,
        )
