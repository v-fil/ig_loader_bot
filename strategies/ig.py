import asyncio
import logging
import re
import tempfile
from os import getcwd, getenv, path

import dukpy
from aiohttp import ClientSession
import instaloader
from playwright.async_api import Error
from playwright.async_api import TimeoutError as PWTimeoutError
from playwright.async_api import async_playwright

from strategies.base import AbstractStrategy, ResultType, Answer
from strategies.utils import Link, FileType, USER_AGENT

DEBUG = getenv("DEBUG", "").lower() in ("1", "true", "yes")

logger = logging.getLogger()

SESSION_FILE = path.join(getcwd(), 'tmp', 'ig.session')


def check_session() -> None:
    """Log the Instagram session status so auth problems are visible at startup.

    Without a valid session instaloader falls back to anonymous requests, which
    Instagram rate-limits hard (429/500) - the most common cause of failed IG
    downloads. This makes that state obvious in the logs instead of silent.
    """
    loader = instaloader.Instaloader(iphone_support=False)
    try:
        loader.load_session_from_file(username='stub', filename=SESSION_FILE)
    except FileNotFoundError:
        logger.warning(f"IG session: no file at {SESSION_FILE} - running anonymously, downloads will be rate-limited")
        return

    sessionid = loader.context._session.cookies.get('sessionid')
    if not sessionid:
        logger.warning("IG session: file present but sessionid is empty - running anonymously, downloads will be rate-limited")
        return

    try:
        username = loader.test_login()
    except Exception as e:  # network/parse errors shouldn't block startup
        logger.error(f"IG session: could not validate sessionid ({e}) - continuing")
        return

    if username:
        logger.info(f"IG session: authenticated as @{username}")
    else:
        logger.warning("IG session: sessionid is invalid (expired or logged out) - re-authenticate")


class InstaloaderStrategy(AbstractStrategy):
    @staticmethod
    def _load_post(url: str) -> Answer | None:
        loader = instaloader.Instaloader(iphone_support=False)
        try:
            loader.load_session_from_file(username='stub', filename=SESSION_FILE)
        except FileNotFoundError:
            pass
        try:
            post = instaloader.Post.from_shortcode(loader.context, extract_id(url).removeprefix("IG:"))
            if post.is_video:
                video_url = post.video_url
                if video_url:
                    video_url_parts = video_url.split("/v/")
                    if len(video_url_parts) > 1:
                        video_url = 'https://scontent.cdninstagram.com/v/' + video_url_parts[1]
                    return Answer(
                        links=[Link(video_url, file_type=FileType.video, filename=post.shortcode + '.mp4')],
                        result_type=ResultType.video_url,
                    )
                logger.info(f"instaloader: video post {post.shortcode} has no video_url")
            elif post.typename == 'GraphSidecar':
                result = Answer(result_type=ResultType.items_list)
                for i, node in enumerate(post.get_sidecar_nodes()):
                    if node.is_video:
                        link = Link(node.video_url, file_type=FileType.video, filename=f"{post.shortcode}_{i}.mp4")
                    else:
                        link = Link(node.display_url, file_type=FileType.img, filename=f"{post.shortcode}_{i}.jpg")
                    result.links.append(link)
                return result
            elif post.typename == 'GraphImage':
                # Single photo: sent via sendPhoto (a one-item media group is
                # not allowed by Telegram).
                return Answer(
                    links=[Link(post.url, file_type=FileType.img, filename=post.shortcode + '.jpg')],
                    result_type=ResultType.image_url,
                )
            else:
                logger.info(f"instaloader: unhandled post type '{post.typename}' for {post.shortcode}")
        except instaloader.InstaloaderException as e:
            logger.error(f"InstaloaderException: {e}")

    async def run(self, url: str) -> Answer | None:
        return await asyncio.to_thread(self._load_post, url)


class FastDLSessionStrategy(AbstractStrategy):
    async def run(self, url: str) -> Answer | None:
        async with ClientSession() as session:
            # try to get correct headers
            async with session.get(
                'https://fastdown.to/en',
                headers={
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,'
                              'image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'accept-language': 'uk',
                    'priority': 'u=0, i',
                    'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'none',
                    'sec-fetch-user': '?1',
                    'upgrade-insecure-requests': '1',
                    'User-Agent': USER_AGENT,
                }
            ) as get_resp:
                if get_resp.status != 200:
                    return None

            async with session.post(
                'https://fastdown.to/api/ajaxSearch',
                data={
                    'q': url,
                    't': 'media',
                    'v': 'v2',
                    'lang': 'en',
                    'cftoken': ''
                }
            ) as resp:
                if resp.status != 200:
                    logger.error(await resp.text())
                    return None

                try:
                    data = await resp.json(content_type=None)
                except ValueError:
                    logger.error(f'fastdl: non-JSON response: {(await resp.text())[:500]}')
                    return None

            if not isinstance(data, dict) or 'data' not in data:
                logger.error(f'url loaded with incomplete result: {data}')
                return None

            code = data['data']
            preamble = (
                'var location = {hostname: "fastdown.to", href: "https://fastdown.to/en"};'
                'var __captured = {};'
                'function FakeEl() { this.innerHTML = ""; this.style = {}; this.children = []; this.appendChild = function(){}; this.setAttribute = function(){}; }'
                'var document = {location: location,'
                '  getElementById: function(id) { if(!__captured[id]) __captured[id] = new FakeEl(); return __captured[id]; },'
                '  querySelector: function() { return new FakeEl(); },'
                '  createElement: function() { return new FakeEl(); }'
                '};'
                'var window = {location: location, document: document};'
            )
            epilogue = 'var __vals = []; for(var k in __captured) __vals.push(__captured[k].innerHTML); __vals.join("|||");'
            # NOTE: this executes JS returned by fastdown.to. Duktape has no fs/network
            # bindings and document/window are stubbed above, so a malicious response
            # is contained by the interpreter sandbox.
            decoded = await asyncio.to_thread(dukpy.evaljs, f'{preamble} (function() {{ {code} }})(); {epilogue}')
            result = str(decoded).replace('\\', '')
            # Images/carousels: URLs in <option value="URL"> inside <li> items
            # Videos: URL in <a href="URL" title="Download Video"> (not inside <li>)
            links = []
            for item in re.split(r'<li>', result):
                dl_url = re.search(r'<option value="(https://dl\.snapcdn\.app/[^"]*)"', item)
                if dl_url:
                    ft = FileType.video if 'icon-dlvideo' in item else FileType.img
                    links.append(Link(dl_url.group(1), file_type=ft))

            if not links:
                dl_url = re.search(r'href="(https://dl\.snapcdn\.app/[^"]*)"[^>]*title="Download Video"', result)
                if not dl_url:
                    dl_url = re.search(r'title="Download Video"[^>]*href="(https://dl\.snapcdn\.app/[^"]*)"', result)
                if dl_url:
                    links.append(Link(dl_url.group(1), file_type=FileType.video))

            if not links:
                logger.error('fastdl: no download links found in result')
                return None

            if len(links) == 1:
                rt = ResultType.video_url if links[0].filetype == FileType.video else ResultType.image_url
                return Answer(links, result_type=rt)
            return Answer(links, result_type=ResultType.items_list)


class FastDLPlaywrightStrategy(AbstractStrategy):
    async def run(self, url: str) -> Answer | None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not DEBUG)
            page = await browser.new_page()
            try:
                await page.goto("https://fastdown.to/")
                await page.get_by_role("textbox").fill(url)

                await asyncio.sleep(0.5)
                await page.get_by_role("button").click()
                try:
                    await page.wait_for_selector("#closeModalBtn")
                    await (await page.query_selector("#closeModalBtn")).click()
                except (PWTimeoutError, Error):
                    try:
                        await page.screenshot(path=path.join(tempfile.gettempdir(), "close_modal_not_found.png"))
                    except Error:
                        pass
                    logger.info(
                        f'{self.__class__.__name__} failed to find "closeModalBtn"'
                    )

                try:
                    await page.wait_for_selector(
                        "#search-result > ul > li > div > div:nth-child(3) > a"
                    )
                    result_button = await page.query_selector(
                        "#search-result > ul > li > div > div:nth-child(3) > a"
                    )
                    _url = await result_button.get_attribute("href")
                    title = (await result_button.get_attribute("title")) or ""
                    if "video" in title.lower():
                        return Answer([Link(_url, file_type=FileType.video)])
                    return Answer([Link(_url, file_type=FileType.img)], result_type=ResultType.image_url)
                except PWTimeoutError:
                    await page.screenshot(path=path.join(tempfile.gettempdir(), "result_not_found.png"))
                    logger.info(
                        f"{self.__class__.__name__} failed to find search result"
                    )
                    return

            except (AttributeError, Error) as e:
                try:
                    await page.screenshot(path=path.join(tempfile.gettempdir(), "scr.png"))
                except Error:
                    pass
                logger.error(str(e))


def extract_id(text: str) -> str:
    match = re.search(r"https://[w.]*instagram\.com/(reels?|share|p)/([^/]*)/*", text)
    if not match:
        raise ValueError(f"Could not extract Instagram ID from: {text}")
    return f"IG:{match.group(2)}"


async def preprocess_url(url: str) -> str:
    if '/share/' in url:
        async with ClientSession() as session:
            async with session.get(url) as result:
                return str(result.url)
    return url
