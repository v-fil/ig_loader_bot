"""Phase 1: filters.url_regex and UrlFilter."""
import re
from types import SimpleNamespace

import pytest

from filters import UrlFilter, url_regex


def find_urls(text: str) -> list[str]:
    # findall returns one tuple per match; group 1 is the full URL
    return [m[0] for m in re.findall(url_regex, text)]


def test_no_urls():
    assert find_urls("just some words, no links here.") == []


def test_single_url():
    assert find_urls("go to https://example.com/watch?v=1 now") == [
        "https://example.com/watch?v=1"
    ]


def test_multiple_urls():
    text = "first https://a.example/one then https://b.example/two ok"
    assert find_urls(text) == ["https://a.example/one", "https://b.example/two"]


def test_url_in_parens():
    assert find_urls("(see: https://example.com/path)") == ["https://example.com/path"]


def test_bare_domain_without_scheme():
    assert find_urls("see example.com/page ok") == ["example.com/page"]
    assert find_urls("see www.example.com ok") == ["www.example.com"]


async def test_url_filter_matches():
    assert await UrlFilter()(SimpleNamespace(text="https://example.com/x")) is True


async def test_url_filter_no_url():
    assert await UrlFilter()(SimpleNamespace(text="no links")) is False


async def test_url_filter_text_is_none():
    # e.g. photo/sticker messages have text=None
    assert await UrlFilter()(SimpleNamespace(text=None)) is False
