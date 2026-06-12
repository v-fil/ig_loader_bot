"""Integrity checks for captured fixtures + canaries for the pytest setup.

These don't test strategy logic (that's Phase 3) — they fail fast when a
fixture file is missing, truncated, or no longer contains what the strategy
tests will look for.
"""
import json
import re

from aioresponses import aioresponses
from aiohttp import ClientSession

from tests.conftest import load_fixture


def test_fastdl_fixture_has_js_payload():
    data = json.loads(load_fixture("fastdl_ajax_search.json"))
    assert data.get("status") == "ok"
    assert "data" in data and len(data["data"]) > 1000


def test_threads_fixture_unrolls():
    from strategies.threads import _parse_threads_url, _unroll

    html = load_fixture("threads_post.html")
    code, user = _parse_threads_url("https://www.threads.com/@zuck/post/DPCXhCwkqEe")
    posts = _unroll(html, url_code=code, username_hint=user)
    assert len(posts) == 3
    assert sum(len(p["image_urls"]) for p in posts) == 5


def test_threads_fixtures_are_sanitized():
    for name in ("threads_post.html", "threads_post_op_not_leading.html"):
        html = load_fixture(name)
        assert re.search(r'"csrf_token":"(?!REDACTED")', html) is None
        assert re.search(r'"device_id":"(?!REDACTED")', html) is None


def test_fxtwitter_fixture_has_photo_media():
    data = json.loads(load_fixture("fxtwitter_status.json"))
    items = data["tweet"]["media"]["all"]
    assert [i["type"] for i in items] == ["photo"]


def test_snaptik_fixtures():
    page = load_fixture("snaptik_page.html")
    assert re.search('<input type="hidden" name="token" value="(.*?)">', page)
    action = json.loads(load_fixture("snaptik_action.json"))
    assert not action.get("error")
    assert 'btn-container' in (action.get("html") or "")


async def test_asyncio_mode_and_aioresponses_work():
    """Canary: asyncio_mode=auto collects bare async tests, aioresponses mocks."""
    with aioresponses() as mock:
        mock.get("https://example.invalid/ping", status=200, body="pong")
        async with ClientSession() as session:
            async with session.get("https://example.invalid/ping") as resp:
                assert await resp.text() == "pong"
