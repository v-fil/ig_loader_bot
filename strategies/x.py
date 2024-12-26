import logging
import re
from os import getenv

from aiohttp import ClientSession
from playwright.async_api import Error, async_playwright

from strategies.base import AbstractStrategy, StrategyType

logger = logging.getLogger()
DEBUG = getenv("DEBUG", False)


class SSSPlaywrightStrategy(AbstractStrategy):
    async def run(self, url: str) -> str | None:
        load_button_selector = (
            "#mainpicture > div > a.pure-button.pure-button-primary.is-center.u-bl.dl-button."
            "download_link.without_watermark.vignette_active.quality-best"
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not DEBUG)
            page = await browser.new_page()
            try:
                await page.goto("https://ssstwitter.com/")
                await page.wait_for_selector("#main_page_text")
                await page.get_by_role("textbox").fill(url)
                await (await page.query_selector("#submit")).click()
                await page.wait_for_selector(load_button_selector)
                result_button = await page.query_selector(load_button_selector)

                onclick = await result_button.get_attribute("onclick")
                try:
                    return re.search(r"(http[a-zA-Z0-9/:.]*)", onclick).group(1)
                except IndexError:
                    return None

            except (AttributeError, Error) as e:
                await page.screenshot(path="/tmp/x.err.scr.png")
                logger.error(str(e))


class TwitterLoadStrategy(AbstractStrategy):
    async def run(self, url: str) -> str | None:
        try:
            url = re.findall(r"(https://x.com/\S*)\s?", url)[0]
        except IndexError:
            return

        async with ClientSession() as session:
            result = await (
                await session.get(f"https://twitsave.com/info?url={url}")
            ).text()
            try:
                return re.search(
                    r"<video class=[\S\s]{10,100} src=\"(.*?)\"", result
                ).group(1)
            except (AttributeError, IndexError) as e:
                logger.error(str(e))


def extract_id(text: str) -> str:
    _id = re.search(r"https://x.com/\S*/status/([a-zA-Z0-9]*)", text).group(1)
    return f"X:{_id}"
