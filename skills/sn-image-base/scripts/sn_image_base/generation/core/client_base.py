from __future__ import annotations

import typing
from abc import ABC, abstractmethod
from typing import Any

from sn_image_base.utils.error_utils import U1HttpResponseParseError
from sn_image_base.utils.httpx_client import (
    create_async_httpx_client,
    httpx_response_raise_for_status_code,
)

if typing.TYPE_CHECKING:
    import httpx

DEFAULT_POLL_INTERVAL = 5.0
DEFAULT_HTTP_REQUEST_TIMEOUT = 300.0
DEFAULT_MAX_CONNECTIONS = 100


class T2IBaseClient(ABC):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        model: str | None = None,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        timeout: float = DEFAULT_HTTP_REQUEST_TIMEOUT,
        ssl_verify: bool = True,
        **kwargs: Any,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self.model = model
        self._client: httpx.AsyncClient | None = None
        self._max_connections = max_connections
        self._timeout = timeout
        self._ssl_verify = ssl_verify

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = create_async_httpx_client(
                self.headers,
                timeout=self._timeout,
                max_connections=self._max_connections,
                verify=self._ssl_verify,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def api_key(self) -> str | None:
        return self._api_key

    @property
    def base_url(self) -> str | None:
        return self._base_url

    @abstractmethod
    async def generate(self, prompt: str, *args: Any, **kwargs: Any) -> Any: ...

    @abstractmethod
    def get_api_url(self, *args: Any, **kwargs: Any) -> str: ...

    @abstractmethod
    def build_payload(self, *args: Any, **kwargs: Any) -> Any: ...

    @property
    @abstractmethod
    def headers(self) -> dict[str, str]: ...

    def parse_response(self, response: httpx.Response) -> dict:
        httpx_response_raise_for_status_code(response)
        try:
            data = response.json()
            return data
        except ValueError as exc:
            raise U1HttpResponseParseError(
                detail=f"Failed to parse HTTP response. {response.request.url}. Response content: {response.content}",
                code=response.status_code,
            ) from exc
