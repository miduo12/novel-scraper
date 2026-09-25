from __future__ import annotations

import pytest

from novel_scraper.adapters import (
    AdapterRegistry,
    BqgAdapter,
    DeqixsAdapter,
    SuduguAdapter,
    adapter_for_url,
    list_adapters,
)
from novel_scraper.exceptions import UnsupportedSiteError


def test_default_registry_loads_existing_adapters() -> None:
    adapters = list_adapters()
    assert adapters == (DeqixsAdapter, SuduguAdapter, BqgAdapter)
    assert {adapter.id for adapter in adapters} == {"deqixs", "sudugu", "bqg"}


def test_adapter_for_url_selects_deqixs() -> None:
    adapter = adapter_for_url("https://www.deqixs.cc/books/99/")
    try:
        assert isinstance(adapter, DeqixsAdapter)
    finally:
        adapter.http.close()


def test_adapter_for_url_selects_sudugu() -> None:
    adapter = adapter_for_url("https://www.sudugu.cc/674/")
    try:
        assert isinstance(adapter, SuduguAdapter)
    finally:
        adapter.http.close()


def test_unknown_url_raises_clear_error() -> None:
    with pytest.raises(UnsupportedSiteError, match="暂不支持该网站"):
        adapter_for_url("https://example.org/book/")


def test_duplicate_registration_is_idempotent_but_conflicting_id_fails() -> None:
    registry = AdapterRegistry((DeqixsAdapter,))
    assert registry.register(DeqixsAdapter) is DeqixsAdapter
    assert registry.list_adapters() == (DeqixsAdapter,)

    class ConflictingAdapter(DeqixsAdapter):
        pass

    with pytest.raises(ValueError, match="adapter id already registered: deqixs"):
        registry.register(ConflictingAdapter)
