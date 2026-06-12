"""Phase 5: live smoke tests — these hit the real external services.

Excluded from default runs by the `live` marker (pyproject addopts:
-m "not live"). Run manually before a commit:

    .venv/bin/python -m pytest -m live -v

Instaloader tests are additionally skipped when tmp/ig.session is missing
(e.g. in CI), so `-m live` degrades gracefully anywhere — the remaining tests
still cover fastdl, snaptik, fxtwitter and threads.

Ported from /tmp/run_strategy.py (2026-06-12 session); unlike that harness,
links are fetched once with URL(link, encoded=True) to match production.
"""
import asyncio
from os import path

import pytest
from aiohttp import ClientSession
from yarl import URL

from strategies import ig, threads, tiktok
from strategies import x as x_mod
from strategies.base import get_provider_by_url
from strategies.types import FileType, ResultType
from strategies.utils import USER_AGENT, Answer

pytestmark = pytest.mark.live

STRATEGY_TIMEOUT = 120

# User-approved URLs (2026-06-12) — do not replace without asking the user.
IG_PHOTO = "https://www.instagram.com/p/Cf4_rZ8jz5z/"  # NASA Webb's First Deep Field
IG_CAROUSEL = "https://www.instagram.com/p/DXCYrJCDEcy/"  # NASA carousel
IG_REEL = "https://www.instagram.com/reels/DPsO-jwjMJm/"
X_POST = "https://twitter.com/TheEllenShow/status/440322224407314432"
THREADS_POST = "https://www.threads.com/@zuck/post/DPCXhCwkqEe"
TIKTOK_SHORT = "https://vt.tiktok.com/ZSffquwF2/"

requires_ig_session = pytest.mark.skipif(
    not path.exists(ig.SESSION_FILE),
    reason="needs tmp/ig.session (anonymous instaloader gets rate-limited)",
)

MEDIA_CONTENT_TYPES = ("image/", "video/", "application/octet-stream")


async def assert_links_fetchable(answer: Answer) -> None:
    """GET the first KB of every link exactly as production would (encoded=True)."""
    assert answer.links
    for link in answer.links:
        async with ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(URL(link.url, encoded=True)) as resp:
                assert resp.status == 200, f"{link.url[:120]}: HTTP {resp.status}"
                ctype = resp.headers.get("Content-Type", "")
                assert ctype.startswith(MEDIA_CONTENT_TYPES), (
                    f"{link.url[:120]}: content type {ctype!r}"
                )
                await resp.content.read(1024)


# --- Instagram: fastdl ---


async def test_ig_photo_fastdl():
    assert get_provider_by_url(IG_PHOTO) == "instagram"
    async with asyncio.timeout(STRATEGY_TIMEOUT):
        answer = await ig.FastDLSessionStrategy().run(IG_PHOTO)

    assert answer is not None
    assert answer.result_type == ResultType.image_url
    assert len(answer.links) == 1
    assert answer.links[0].filetype == FileType.img
    await assert_links_fetchable(answer)


async def test_ig_carousel_fastdl():
    assert get_provider_by_url(IG_CAROUSEL) == "instagram"
    async with asyncio.timeout(STRATEGY_TIMEOUT):
        answer = await ig.FastDLSessionStrategy().run(IG_CAROUSEL)

    assert answer is not None
    assert answer.result_type == ResultType.items_list
    assert len(answer.links) > 1
    await assert_links_fetchable(answer)


async def test_ig_reel_fastdl():
    # the /reels/ form: regression for the routing fix of 2026-06-12
    assert get_provider_by_url(IG_REEL) == "instagram"
    async with asyncio.timeout(STRATEGY_TIMEOUT):
        answer = await ig.FastDLSessionStrategy().run(IG_REEL)

    assert answer is not None
    assert answer.result_type == ResultType.video_url
    assert len(answer.links) == 1
    assert answer.links[0].filetype == FileType.video
    await assert_links_fetchable(answer)


# --- Instagram: instaloader (needs tmp/ig.session) ---


@requires_ig_session
async def test_ig_photo_instaloader():
    async with asyncio.timeout(STRATEGY_TIMEOUT):
        answer = await ig.InstaloaderStrategy().run(IG_PHOTO)

    assert answer is not None
    assert answer.result_type == ResultType.image_url
    assert len(answer.links) == 1
    await assert_links_fetchable(answer)


@requires_ig_session
async def test_ig_carousel_instaloader():
    async with asyncio.timeout(STRATEGY_TIMEOUT):
        answer = await ig.InstaloaderStrategy().run(IG_CAROUSEL)

    assert answer is not None
    assert answer.result_type == ResultType.items_list
    assert len(answer.links) > 1
    await assert_links_fetchable(answer)


@requires_ig_session
async def test_ig_reel_instaloader():
    async with asyncio.timeout(STRATEGY_TIMEOUT):
        answer = await ig.InstaloaderStrategy().run(IG_REEL)

    assert answer is not None
    assert answer.result_type == ResultType.video_url
    assert len(answer.links) == 1
    await assert_links_fetchable(answer)


# --- X / Twitter ---


async def test_x_photo_fxtwitter():
    assert get_provider_by_url(X_POST) == "twitter"
    async with asyncio.timeout(STRATEGY_TIMEOUT):
        answer = await x_mod.FxTwitterStrategy().run(X_POST)

    assert answer is not None
    assert answer.result_type == ResultType.items_list
    assert [link.filetype for link in answer.links] == [FileType.img]
    await assert_links_fetchable(answer)


# --- Threads ---


async def test_threads_post():
    assert get_provider_by_url(THREADS_POST) == "threads"
    # threads.com occasionally serves a JS-only shell to the first request;
    # one retry is enough in practice (observed 2026-06-12)
    answer = None
    for _ in range(2):
        async with asyncio.timeout(STRATEGY_TIMEOUT):
            answer = await threads.ThreadsStrategy().run(THREADS_POST)
        if answer is not None:
            break

    assert answer is not None
    assert answer.result_type == ResultType.items_list
    assert answer.text
    assert all(link.filetype == FileType.img for link in answer.links)
    await assert_links_fetchable(answer)


# --- TikTok ---


async def test_tiktok_short_link_snaptik():
    assert get_provider_by_url(TIKTOK_SHORT) == "tiktok"
    resolved = await tiktok.preprocess_url(TIKTOK_SHORT)
    # TikTok's shortener serves server-side clients a degraded fallback
    # Location with an empty username, which snaptik rejects — preprocess_url
    # must never pass that form along (regression, 2026-06-12)
    assert "tiktok.com/@/" not in resolved

    async with asyncio.timeout(STRATEGY_TIMEOUT):
        answer = await tiktok.SnaptikSessionStrategy().run(resolved)

    assert answer is not None
    assert answer.result_type == ResultType.video_url
    assert len(answer.links) == 1
    await assert_links_fetchable(answer)
