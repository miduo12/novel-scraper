from __future__ import annotations

from .base import SiteAdapter
from .deqixs import DeqixsAdapter

_ADAPTERS: tuple[type[SiteAdapter], ...] = (DeqixsAdapter,)


def adapter_for_url(url: str, http_client: object) -> SiteAdapter:
    for adapter_type in _ADAPTERS:
        if adapter_type.matches(url):
            return adapter_type(http_client)

    from ..exceptions import UnsupportedSiteError

    raise UnsupportedSiteError(f"暂不支持该网站：{url}")


__all__ = ["SiteAdapter", "DeqixsAdapter", "adapter_for_url"]
