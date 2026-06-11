import json
import logging
import re
from typing import Any, Iterator, Optional

from aiohttp import ClientSession

from strategies.base import AbstractStrategy
from strategies.types import FileType, ResultType
from strategies.utils import Answer, Link, USER_AGENT

logger = logging.getLogger()

THREADS_URL_RE = re.compile(
    r"https?://(?:www\.)?threads\.(?:net|com)/"
    r"(?:t/(?P<code1>[\w-]+)"
    r"|@(?P<user>[\w.\-]+)/post/(?P<code2>[\w-]+))/?",
    re.I,
)

SCRIPT_BLOCK_RE = re.compile(
    r'<script[^>]*\btype="application/json"[^>]*\bdata-sjs\b[^>]*>(.*?)</script>',
    re.S | re.I,
)

BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}


def _parse_threads_url(url: str) -> tuple[str, Optional[str]]:
    m = THREADS_URL_RE.search(url.strip())
    if not m:
        raise ValueError(f"Not a Threads post URL: {url!r}")
    return (m.group("code1") or m.group("code2"), m.group("user"))


def _iter_json_blocks(html: str) -> Iterator[dict]:
    for m in SCRIPT_BLOCK_RE.finditer(html):
        raw = m.group(1).strip()
        if not raw:
            continue
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            continue


def _nested_lookup(key: str, data: Any) -> list:
    hits: list = []
    stack: list = [data]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k == key:
                    hits.append(v)
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return hits


def _parse_post(item: Any) -> Optional[dict]:
    if not isinstance(item, dict):
        return None
    post = item.get("post")
    if not isinstance(post, dict):
        return None

    caption = post.get("caption") or {}
    text = caption.get("text") if isinstance(caption, dict) else None
    user = post.get("user") or {}
    username = user.get("username") if isinstance(user, dict) else None
    code = post.get("code")
    taken_at = post.get("taken_at")
    pk = post.get("pk") or post.get("id")

    image_urls: list[str] = []
    carousel = post.get("carousel_media")
    if isinstance(carousel, list):
        for c in carousel:
            cand = (((c or {}).get("image_versions2") or {}).get("candidates")) or []
            if cand and cand[0].get("url"):
                image_urls.append(cand[0]["url"])
    else:
        cand = ((post.get("image_versions2") or {}).get("candidates")) or []
        if cand and cand[0].get("url"):
            image_urls.append(cand[0]["url"])

    return {
        "pk": pk,
        "code": code,
        "username": username,
        "taken_at": taken_at,
        "text": text,
        "image_urls": image_urls,
    }


def _unroll(html: str, url_code: str, username_hint: Optional[str]) -> list[dict]:
    # Collect every thread_items array as a list of parsed posts (order preserved).
    arrays: list[list[dict]] = []
    for blob in _iter_json_blocks(html):
        for thread_items in _nested_lookup("thread_items", blob):
            if not isinstance(thread_items, list):
                continue
            parsed_arr = [p for p in (_parse_post(i) for i in thread_items) if p]
            if parsed_arr:
                arrays.append(parsed_arr)

    if not arrays:
        return []

    # Identify the OP from the post matching the URL code, falling back to the hint.
    target_user = username_hint
    if not target_user:
        for arr in arrays:
            for p in arr:
                if p["code"] == url_code:
                    target_user = p["username"]
                    break
            if target_user:
                break
    if not target_user:
        target_user = arrays[0][0]["username"]

    # The OP chain = leading consecutive OP posts of every thread_items array.
    # Reply chains start with the commenter, so they're naturally excluded.
    seen: set = set()
    op_posts: list[dict] = []
    for arr in arrays:
        for p in arr:
            if p["username"] != target_user:
                break
            key = p.get("pk") or (p.get("username"), p.get("code"))
            if key in seen:
                continue
            seen.add(key)
            op_posts.append(p)

    op_posts.sort(key=lambda p: p.get("taken_at") or 0)
    return op_posts


def _format_text(posts: list[dict], source_url: str) -> str:
    handle = posts[0].get("username") or "unknown"
    total = len(posts)
    header = f"🧵 @{handle} on Threads — {total} post{'s' if total != 1 else ''}"

    parts: list[str] = []
    for i, p in enumerate(posts, 1):
        body = (p.get("text") or "").strip() or "(no text)"
        prefix = f"{i}/{total}\n" if total > 1 else ""
        parts.append(f"{prefix}{body}")

    return f"{header}\n\n" + "\n\n———\n\n".join(parts) + f"\n\n{source_url}"


class ThreadsStrategy(AbstractStrategy):
    async def run(self, url: str) -> Answer | None:
        try:
            code, user_hint = _parse_threads_url(url)
        except ValueError:
            return None

        async with ClientSession(headers=BROWSER_HEADERS) as session:
            async with session.get(url, allow_redirects=True, timeout=30) as resp:
                if resp.status != 200:
                    logger.error(f"threads: HTTP {resp.status} fetching {url}")
                    return None
                html = await resp.text(errors="replace")

        posts = _unroll(html, url_code=code, username_hint=user_hint)
        if not posts:
            logger.error(
                "threads: no thread data found - page may be JS-only shell"
            )
            return None

        text = _format_text(posts, url)

        links: list[Link] = []
        for p in posts:
            code_part = p.get("code") or "x"
            for idx, img_url in enumerate(p.get("image_urls") or []):
                links.append(Link(img_url, FileType.img, f"threads_{code_part}_{idx}.jpg"))

        if not links:
            return Answer(result_type=ResultType.text, text=text)

        return Answer(links=links, result_type=ResultType.items_list, text=text)


def extract_id(text: str) -> str:
    m = THREADS_URL_RE.search(text)
    if not m:
        raise ValueError(f"Could not extract Threads ID from: {text}")
    return f"Threads:{m.group('code1') or m.group('code2')}"
