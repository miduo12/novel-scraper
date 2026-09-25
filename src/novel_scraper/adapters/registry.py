from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from ..exceptions import UnsupportedSiteError
from .base import SiteAdapter

AdapterType = TypeVar("AdapterType", bound=type[SiteAdapter])


class AdapterRegistry:
    """Registry for the site adapters available to the application."""

    def __init__(self, adapters: Iterable[type[SiteAdapter]] = ()) -> None:
        self._adapters: list[type[SiteAdapter]] = []
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: AdapterType) -> AdapterType:
        if not isinstance(adapter, type) or not issubclass(adapter, SiteAdapter):
            raise TypeError("adapter must be a SiteAdapter subclass")

        adapter_id = getattr(adapter, "id", None) or getattr(adapter, "name", "")
        if not adapter_id or adapter_id == "base":
            raise ValueError("adapter must define a non-empty id or name")

        for registered in self._adapters:
            registered_id = getattr(registered, "id", None) or getattr(registered, "name", "")
            if registered is adapter:
                return adapter
            if registered_id == adapter_id:
                raise ValueError(f"adapter id already registered: {adapter_id}")

        self._adapters.append(adapter)
        return adapter

    def adapter_for_url(
        self,
        url: str,
        http_client: object | None = None,
    ) -> SiteAdapter:
        for adapter in self._adapters:
            if adapter.matches(url):
                if http_client is None:
                    from ..http import HttpClient

                    http_client = HttpClient()
                return adapter(http_client)
        raise UnsupportedSiteError(f"暂不支持该网站：{url}")

    def list_adapters(self) -> tuple[type[SiteAdapter], ...]:
        return tuple(self._adapters)

    def is_supported_url(self, url: str) -> bool:
        return any(adapter.matches(url) for adapter in self._adapters)
