from __future__ import annotations

from .base import SiteAdapter
from .bqg import BqgAdapter
from .deqixs import DeqixsAdapter
from .generic import GenericAdapter
from .registry import AdapterRegistry
from .sudugu import SuduguAdapter

DeqixsAdapter.id = "deqixs"
DeqixsAdapter.display_name = "得奇小说网"
DeqixsAdapter.domains = ("deqixs.cc",)
DeqixsAdapter.example_url = "https://www.deqixs.cc/books/99/"
SuduguAdapter.id = "sudugu"
SuduguAdapter.display_name = "速读谷"
SuduguAdapter.domains = ("sudugu.cc",)
SuduguAdapter.example_url = "https://www.sudugu.cc/674/"

registry = AdapterRegistry((DeqixsAdapter, SuduguAdapter, BqgAdapter, GenericAdapter))


def register(adapter: type[SiteAdapter]) -> type[SiteAdapter]:
    return registry.register(adapter)


def adapter_for_url(url: str, http_client: object | None = None) -> SiteAdapter:
    return registry.adapter_for_url(url, http_client)


def list_adapters() -> tuple[type[SiteAdapter], ...]:
    return registry.list_adapters()


def is_supported_url(url: str) -> bool:
    return registry.is_supported_url(url)


__all__ = [
    "AdapterRegistry",
    "BqgAdapter",
    "DeqixsAdapter",
    "GenericAdapter",
    "SiteAdapter",
    "SuduguAdapter",
    "adapter_for_url",
    "is_supported_url",
    "list_adapters",
    "register",
    "registry",
]
