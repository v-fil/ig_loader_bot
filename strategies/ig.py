import logging
import re
from asyncio import sleep
from os import getenv

from playwright.async_api import Error, async_playwright
from playwright.async_api import TimeoutError as PWTimeoutError

from strategies.base import AbstractStrategy, StrategyType

DEBUG = getenv("DEBUG", False)

logger = logging.getLogger()


class SnapclipPlaywrightStrategy(AbstractStrategy):
    strategy_type = StrategyType.video_url

    async def run(self, url: str) -> str | None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not DEBUG)
            page = await browser.new_page()
            try:
                await page.goto("https://snapclip.app/en")
                await page.get_by_role("textbox").fill(url)

                await sleep(1)

                await (
                    await page.query_selector("#search-form > div > div > button")
                ).click()
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
    _id = re.search(r"https://[w.]*instagram.com/reel[s]?/(\S*)/", text).group(1)
    return f"IG:{_id}"
