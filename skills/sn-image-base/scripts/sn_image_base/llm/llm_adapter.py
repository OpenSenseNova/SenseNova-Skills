"""Abstract base class for LLM (Language Model) adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LlmAdapter(ABC):
    """Uniform async interface for a single Language Model backend.

    Each concrete adapter wraps one LLM endpoint + model combination and
    exposes a single :meth:`text_completion` coroutine.  Synchronous
    calling is intentionally **not** supported; callers must run inside an
    asyncio event loop.

    **Client ownership contract** — when a shared
    :class:`httpx.AsyncClient` is supplied at construction time the adapter
    *reuses* it and must **not** close it; the caller retains full ownership
    of the client's lifecycle.  When no external client is provided the
    adapter creates and owns an internal client and must close it in
    :meth:`aclose`.
    """

    @abstractmethod
    async def text_completion(
        self,
        user_prompt: str,
        system_prompt: str = "",
        model: str | None = None,
    ) -> str:
        """Send a text-only prompt to the model and return the reply.

        Args:
            user_prompt: User-facing text instruction.
            system_prompt: System-level instruction prepended to the
                conversation.  Defaults to ''.
            model: Model name to use. If None, uses the default set at
                initialization.

        Returns:
            str: Raw text response from the model.
        """

    @abstractmethod
    async def aclose(self) -> None:
        """Release async resources owned by this adapter.

        Must be called when the adapter is no longer needed.  Adapters that
        were given an external shared client must implement this as a no-op;
        adapters that created their own internal client must close it here.
        """
