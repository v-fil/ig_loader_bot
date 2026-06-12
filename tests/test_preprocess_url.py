"""Phase 3: preprocess_url for ig (share-link resolution) and tiktok (short-link redirect)."""
import pytest
from aioresponses import aioresponses

from strategies import ig, tiktok


@pytest.fixture
def mock_http():
    with aioresponses() as m:
        yield m


async def test_ig_share_url_follows_redirect(mock_http):
    share_url = "https://www.instagram.com/share/reel/abc123"
    final_url = "https://www.instagram.com/reel/XYZ789/"
    mock_http.get(share_url, status=302, headers={"Location": final_url})
    mock_http.get(final_url, status=200)

    assert await ig.preprocess_url(share_url) == final_url


async def test_ig_non_share_url_untouched(mock_http):
    # no mock registered: must return without any HTTP request
    url = "https://www.instagram.com/p/ABC/"
    assert await ig.preprocess_url(url) == url


async def test_tiktok_short_url_returns_location(mock_http):
    short_url = "https://vt.tiktok.com/ZSabc/"
    full_url = "https://www.tiktok.com/@user/video/123?_t=x"
    mock_http.get(short_url, status=301, headers={"Location": full_url})

    assert await tiktok.preprocess_url(short_url) == full_url


async def test_tiktok_degraded_redirect_keeps_short_form(mock_http):
    # regression (2026-06-12): the shortener 302s server-side clients to an
    # empty-username fallback (tiktok.com/@/video/<id>) that snaptik rejects;
    # the short URL itself works there, so preprocess_url must keep it
    short_url = "https://vt.tiktok.com/ZSabc/"
    degraded = "https://www.tiktok.com/@/video/123?_r=1&utm_source=short_fallback"
    mock_http.get(short_url, status=302, headers={"Location": degraded})

    assert await tiktok.preprocess_url(short_url) == short_url


async def test_tiktok_missing_location_returns_original(mock_http):
    short_url = "https://vt.tiktok.com/ZSabc/"
    mock_http.get(short_url, status=200)

    assert await tiktok.preprocess_url(short_url) == short_url


async def test_tiktok_full_url_untouched(mock_http):
    # no mock registered: must return without any HTTP request
    url = "https://www.tiktok.com/@user/video/123"
    assert await tiktok.preprocess_url(url) == url
