import asyncio
import logging
import re
import tempfile
from os import getcwd, getenv, path

import dukpy
import requests
from aiohttp import ClientSession
import instaloader
from playwright.async_api import Error
from playwright.async_api import TimeoutError as PWTimeoutError
from playwright.async_api import async_playwright

from strategies.base import AbstractStrategy, ResultType, Answer
from strategies.utils import Link, FileType

DEBUG = getenv("DEBUG", "").lower() in ("1", "true", "yes")

logger = logging.getLogger()


class InstaloaderStrategy(AbstractStrategy):
    @staticmethod
    def _load_post(url: str) -> Answer | None:
        loader = instaloader.Instaloader(iphone_support=False)
        try:
            loader.load_session_from_file(username='stub', filename=path.join(getcwd(), 'tmp', 'ig.session'))
        except FileNotFoundError:
            pass
        try:
            post = instaloader.Post.from_shortcode(loader.context, extract_id(url).lstrip("IG:"))
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
            elif post.typename == 'GraphSidecar':
                result = Answer(result_type=ResultType.items_list)
                for edge in post._field('edge_sidecar_to_children', 'edges'):
                    link = Link()
                    if edge['node']['is_video']:
                        link.url = edge['node']['video_url']
                        link.filetype = FileType.video
                        link.filename = edge['node']['shortcode'] + ".mp4"
                    else:
                        link.url = edge['node']['display_url']
                        link.filetype = FileType.img
                        link.filename = edge['node']['shortcode'] + ".jpg"
                    result.links.append(link)
                return result
        except instaloader.InstaloaderException as e:
            logger.error(f"InstaloaderException: {e}")

    async def run(self, url: str) -> Answer | None:
        return await asyncio.to_thread(self._load_post, url)


class FastDLSessionStrategy(AbstractStrategy):
    async def run(self, url: str) -> Answer | None:
        async with ClientSession() as session:
            # try to get correct headers
            get_resp = await session.get(
                'https://fastdl.dev/en',
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
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                                  '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
                }
            )
            if get_resp.status != 200:
                return None
            result = await session.post(
                'https://fastdl.dev/api/ajaxSearch',
                data={
                    'q': url,
                    't': 'media',
                    'v': 'v2',
                    'lang': 'en',
                    'cftoken': ''
                }
            )
            if result.status != 200:
                logger.error(await result.text())
                return None

            try:
                data = await result.json(content_type=None)
            except ValueError:
                logger.error(f'fastdl: non-JSON response: {(await result.text())[:500]}')
                return None
            if not isinstance(data, dict) or 'data' not in data:
                logger.error(f'url loaded with incomplete result: {data}')
                return None

            code = data['data']
            preamble = (
                'var location = {hostname: "fastdl.dev", href: "https://fastdl.dev/en"};'
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
                logger.error(f'fastdl: no download links found in result')
                return None

            if len(links) == 1:
                rt = ResultType.video_url if links[0].filetype == FileType.video else ResultType.url
                return Answer(links, result_type=rt)
            return Answer(links, result_type=ResultType.items_list)


class FastDLPlaywrightStrategy(AbstractStrategy):
    async def run(self, url: str) -> Answer | None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not DEBUG)
            page = await browser.new_page()
            try:
                await page.goto("https://fastdl.dev/")
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
                    return Answer([Link(_url)])
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


class DDInstaStrategy(AbstractStrategy):
    async def run(self, url: str) -> Answer | None:
        dd_url = re.sub("https://([w.]*)?", "https://d.dd", url)
        return Answer([Link(dd_url)], result_type=ResultType.url)


def extract_id(text: str) -> str:
    match = re.search(r"https://[w.]*instagram\.com/(reel|share|p)/([^/]*)/*", text)
    if not match:
        raise ValueError(f"Could not extract Instagram ID from: {text}")
    return f"IG:{match.group(2)}"


async def preprocess_url(url: str) -> str:
    if '/share/' in url:
        async with ClientSession() as session:
            result = await session.get(url)
            return str(result.url)
    return url
