from __future__ import annotations

from .base import SiteAdapter
from .deqixs import DeqixsAdapter
from .sudugu import SuduguAdapter

_ADAPTERS: tuple[type[SiteAdapter], ...] = (
    DeqixsAdapter,
    SuduguAdapter,
)


def adapter_for_url(url: str, http_client: object) -> SiteAdapter:
    for adapter_type in _ADAPTERS:
        if adapter_type.matches(url):
            return adapter_type(http_client)

    from ..exceptions import UnsupportedSiteError

    raise UnsupportedSiteError(f"暂不支持该网站：{url}")


def is_supported_url(url: str) -> bool:
    return any(adapter_type.matches(url) for adapter_type in _ADAPTERS)


__all__ = [
    "DeqixsAdapter",
    "SiteAdapter",
    "SuduguAdapter",
    "adapter_for_url",
    "is_supported_url",
]
