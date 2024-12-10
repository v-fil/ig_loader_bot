import logging
import re
from asyncio import sleep
from os import getenv

from aiohttp import ClientSession
from playwright.async_api import Error, async_playwright
from playwright.async_api import TimeoutError as PWTimeoutError

from strategies.base import AbstractStrategy, StrategyType

DEBUG = getenv("DEBUG", False)

logger = logging.getLogger()


class SnapclipSessionStrategy(AbstractStrategy):
    strategy_type = StrategyType.video_url

    async def run(self, url: str) -> str | None:
        async with ClientSession() as session:
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
            data = await result.json()


        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not DEBUG)
            page = await browser.new_page()
            await page.goto("https://snapclip.app/en")

            await page.evaluate(
                "window.rd = function() {try{insertAndExecute;return true} catch (ReferenceError) {return false} }"
            )
            await page.wait_for_function("rd()")

            await page.evaluate(
                f"""
                n={data};
                insertAndExecute("js-result", "<script type='text/javascript'>" + n.data + "</script>");"""
            )

            result_button = await page.query_selector(
                "#search-result > ul > li > div > div:nth-child(3) > a"
            )
            return await result_button.get_attribute("href")


class SnapclipPlaywrightStrategy(AbstractStrategy):
    strategy_type = StrategyType.video_url

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
    _id = re.search(r"https://[w.]*instagram.com/reel[s]?/(\S*)/", text).group(1)
    return f"IG:{_id}"
