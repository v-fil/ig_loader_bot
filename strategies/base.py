import logging
import re
from abc import ABC, abstractmethod
from enum import Enum

from aiogram import types
from aiohttp import ClientSession

from strategies.utils import answer_with_url, upload_video, Answer, answer_with_album

logger = logging.getLogger()


class StrategyType(Enum):
    url = "url"
    video_url = "video_url"
    items_list = "items_list"


class Provider(Enum):
    instagram = "instagram"
    tiktok = "tiktok"
    twitter = "twitter"
    youtube = "youtube"


class FilterUrlRegex(Enum):
    instagram = r"https://[w.]*instagram\.com/[reel|share|p]*/\S*"
    tiktok = r"https://vm.tiktok.com/\S*/"
    twitter = r"https://x.com/\S*"
    youtube = r"https://[w.]*youtube.com/shorts/\S*"


def get_provider_by_url(url: str) -> str:
    for provider, member in FilterUrlRegex.__members__.items():
        if re.match(member.value, url):
            return provider


class AbstractStrategy(ABC):
    strategy_type: StrategyType = StrategyType.video_url

    @abstractmethod
    async def run(self, url: str) -> str | Answer | None:
        pass


class RegistryItem:
    strategies: list[AbstractStrategy]
    extract_id: callable

    def __init__(self, strategies: list[AbstractStrategy], extract_id: callable):
        assert strategies
        assert extract_id

        self.strategies = strategies
        self.extract_id = extract_id


class Registry:
    items: dict[Provider, RegistryItem]

    def __init__(self, items: dict[Provider, RegistryItem]):
        self.items = items

    async def run(self, provider: Provider, message: types.Message, url: str) -> None:
        registry_item = self.items[provider]

        try:
            _id = registry_item.extract_id(url)
        except AttributeError:
            logger.info(f"[{provider}] got url '{url}', could not extract id")
            _id = url

        for strategy in registry_item.strategies:
            logger.info(f"[{_id}] Running with {strategy.__class__.__name__}")
            result = await strategy.run(url)
            if result:
                logger.info(f"[{_id}] got result")
                if strategy.strategy_type == StrategyType.video_url:
                    try:
                        logger.info(f"[{_id}] trying to upload result")
                        await upload_video(result, message)
                        logger.info(f"[{_id}] successfully uploaded result, exiting")
                        return
                    except Exception as e:
                        logger.error(f'[{_id}] {str(e)}')
                        await answer_with_url(result, message)
                        return

                elif strategy.strategy_type == StrategyType.url:
                    logger.info(f"[{_id}] trying to upload result")
                    await answer_with_url(result, message)
                    return

                elif strategy.strategy_type == StrategyType.items_list:
                    logger.info(f"[{_id}] trying to upload album")
                    await answer_with_album(result, message)
                    return
        else:
            logger.info(f"[{_id}] No strategies left, exiting")
