"""Capture live HTTP fixtures for the test suite.

The scraped sites change without notice; when a strategy breaks, re-run this
to refresh the fixtures it relies on:

    .venv/bin/python tests/fixtures/capture.py            # capture everything
    .venv/bin/python tests/fixtures/capture.py snaptik    # one service
    .venv/bin/python tests/fixtures/capture.py fastdl https://www.instagram.com/p/XXX/

Only response bodies are stored - no cookies or other headers.
"""
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from aiohttp import ClientSession

from strategies.threads import BROWSER_HEADERS
from strategies.utils import USER_AGENT

FIXTURES = Path(__file__).resolve().parent

# Stable, famous public posts - chosen to outlive the fixtures.
DEFAULT_URLS = {
    # NASA Webb's First Deep Field (@jameswebb_nasa), single photo
    "fastdl": "https://www.instagram.com/p/Cf4_rZ8jz5z/",
    # Mark Zuckerberg 3-post OP chain ("Introducing Vibes"), images in post 2.
    # NOTE: not every post works - e.g. @zuck/post/DTTnkzwkdSx renders with the
    # OP mid-array instead of leading, and _unroll yields nothing (that page is
    # kept as threads_post_op_not_leading.html). The check below catches this.
    "threads": "https://www.threads.com/@zuck/post/DPCXhCwkqEe",
    # Ellen's Oscar selfie (photo tweet)
    "fxtwitter": "https://twitter.com/TheEllenShow/status/440322224407314432",
    # Zach King's broomstick illusion
    "snaptik": "https://www.tiktok.com/@zachking/video/6768504823336815877",
}


def _save(name: str, content: str) -> None:
    path = FIXTURES / name
    path.write_text(content)
    print(f"  wrote {path.relative_to(FIXTURES.parent.parent)} ({len(content)} bytes)")


async def capture_fastdl(url: str, suffix: str = "") -> None:
    """fastdown.to ajaxSearch JSON (the 'data' field holds the JS payload)."""
    async with ClientSession() as session:
        async with session.get(
            "https://fastdown.to/en", headers={"User-Agent": USER_AGENT}
        ) as resp:
            assert resp.status == 200, f"fastdl landing: HTTP {resp.status}"
        async with session.post(
            "https://fastdown.to/api/ajaxSearch",
            data={"q": url, "t": "media", "v": "v2", "lang": "en", "cftoken": ""},
        ) as resp:
            assert resp.status == 200, f"fastdl ajaxSearch: HTTP {resp.status}"
            body = await resp.text()
    json.loads(body)  # fail loudly on a non-JSON (blocked/captcha) response
    _save(f"fastdl_ajax_search{suffix}.json", body)


# Anonymous-session tokens Meta embeds in the page; harmless but not ours to keep.
_THREADS_TOKEN_RES = [
    re.compile(r'("csrf_token":")[^"]+(")'),
    re.compile(r'("device_id":")[^"]+(")'),
    re.compile(r'("LSD",\[\],\{"token":")[^"]+(")'),
]


def sanitize_threads_html(html: str) -> str:
    for token_re in _THREADS_TOKEN_RES:
        html = token_re.sub(r"\1REDACTED\2", html)
    return html


async def capture_threads(url: str) -> None:
    """Threads post HTML with the embedded data-sjs JSON blocks."""
    from strategies.threads import _parse_threads_url, _unroll

    async with ClientSession(headers=BROWSER_HEADERS) as session:
        async with session.get(url, allow_redirects=True, timeout=30) as resp:
            assert resp.status == 200, f"threads: HTTP {resp.status}"
            html = await resp.text(errors="replace")
    html = sanitize_threads_html(html)
    code, user = _parse_threads_url(url)
    posts = _unroll(html, url_code=code, username_hint=user)
    assert posts, "threads: _unroll found no OP posts in the page"
    _save("threads_post.html", html)


async def capture_fxtwitter(url: str) -> None:
    """fxtwitter API JSON for a tweet with media."""
    m = re.search(r"(?:x|twitter)\.com/([^/\s]+)/status/(\d+)", url)
    assert m, f"not a tweet URL: {url}"
    async with ClientSession() as session:
        async with session.get(
            f"https://api.fxtwitter.com/{m.group(1)}/status/{m.group(2)}"
        ) as resp:
            assert resp.status == 200, f"fxtwitter: HTTP {resp.status}"
            body = await resp.text()
    json.loads(body)
    _save("fxtwitter_status.json", body)


async def capture_snaptik(url: str) -> None:
    """snaptik.pro landing page + /action JSON response."""
    async with ClientSession() as session:
        session.headers.update({"User-Agent": USER_AGENT})
        async with session.get("https://snaptik.pro/") as resp:
            assert resp.status == 200, f"snaptik page: HTTP {resp.status}"
            page = await resp.text()
        token = re.search('<input type="hidden" name="token" value="(.*?)">', page)
        assert token, "snaptik: no token on page"
        _save("snaptik_page.html", page)

        data = {"url": url, "token": token.group(1), "submit": "1"}
        async with session.post("https://snaptik.pro/action", data=data) as resp:
            assert resp.status == 200, f"snaptik action: HTTP {resp.status}"
            body = await resp.text()
    json.loads(body)
    _save("snaptik_action.json", body)


CAPTURES = {
    "fastdl": capture_fastdl,
    "threads": capture_threads,
    "fxtwitter": capture_fxtwitter,
    "snaptik": capture_snaptik,
}


async def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else None
    targets = [name] if name else list(CAPTURES)
    failures = []
    for target in targets:
        url = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_URLS[target]
        print(f"capturing {target} <- {url}")
        try:
            await CAPTURES[target](url)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            failures.append(target)
    if failures:
        sys.exit(f"failed: {', '.join(failures)}")


if __name__ == "__main__":
    asyncio.run(main())
