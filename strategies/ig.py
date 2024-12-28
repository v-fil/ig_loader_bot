import ctypes
import logging
import re
from asyncio import sleep
from os import getcwd, getenv, path, remove

from aiohttp import ClientSession
from playwright.async_api import Error
from playwright.async_api import TimeoutError as PWTimeoutError
from playwright.async_api import async_playwright

from strategies.base import AbstractStrategy, StrategyType

DEBUG = getenv("DEBUG", False)

logger = logging.getLogger()


class SnapclipSessionStrategy(AbstractStrategy):
    @staticmethod
    def _hash(url):
        def hash_fn(word):
            return ctypes.c_uint64(hash(word)).value

        return str(hash_fn(url).to_bytes(8, "big").hex())

    async def run(self, url: str) -> str | None:
        hashed_url = self._hash(url)
        file_path = path.join(getcwd(), 'tmp', f'{hashed_url}.html')
        async with ClientSession() as session:
            # try to get correct headers
            get_resp = await session.get(
                'https://snapclip.app/en',
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
                'https://snapclip.app/api/ajaxSearch',
                data={
                    'q': url,
                    't': 'media',
                    'v': 'v2',
                    'lang': 'en',
                    'cftoken': ''
                }
            )
            if result.status != 200:
                print(await result.text())
                return None

            data = await result.json()
            if 'data' not in data:
                logger.error(f'url loaded with incomplete result: {data}')
                return None
            code = data['data'].replace('return decodeURIComponent', 'document.res = decodeURIComponent')
            with open(file_path, 'w') as f:
                f.write(f'''<!DOCTYPE html><html lang="en"><body><script>{code}</script></body></html>''')
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not DEBUG)
            page = await browser.new_page()
            await page.goto(f'file://{file_path}')
            result = (await page.evaluate('() => document.res')).replace('\\', '')

            remove(file_path)

            try:
                video_url = re.search(
                    r'<a href=\"(\S*)\" class=\"abutton is-success is-fullwidth btn-premium mt-3\" rel=\"nofollow\" title=\"Download Video\">',
                    result,
                ).group(1)
                return video_url
            except IndexError as e:
                logger.error(e)
                return


class SnapclipPlaywrightStrategy(AbstractStrategy):
    async def run(self, url: str) -> str | None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not DEBUG)
            page = await browser.new_page()
            try:
                await page.goto("https://snapclip.app/en")
                await page.get_by_role("textbox").fill(url)

                await sleep(0.5)
                await page.get_by_role("button").click()
                try:
                    await page.wait_for_selector("#closeModalBtn")
                    await (await page.query_selector("#closeModalBtn")).click()
                except (PWTimeoutError, Error):
                    try:
                        await page.screenshot(path="/tmp/close_modal_not_found.png")
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
                    return await result_button.get_attribute("href")
                except PWTimeoutError:
                    await page.screenshot(path="/tmp/result_not_found.png")
                    logger.info(
                        f"{self.__class__.__name__} failed to find search result"
                    )
                    return

            except (AttributeError, Error) as e:
                try:
                    await page.screenshot(path="/tmp/scr.png")
                except Error:
                    pass
                logger.error(str(e))


class DDInstaStrategy(AbstractStrategy):
    strategy_type = StrategyType.url

    async def run(self, url: str) -> str | None:
        dd_url = re.sub("https://([w.]*)?", "https://d.dd", url)
        return dd_url


def extract_id(text: str) -> str:
    _id = re.search(r"https://[w.]*instagram\.com/[reel|share]*/([^/]*)/*", text).group(1)
    return f"IG:{_id}"
