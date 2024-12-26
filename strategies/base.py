import logging
import re
from abc import ABC, abstractmethod
from enum import EnumType

from aiogram import types

from filters import FilterUrlRegex
from strategies.utils import answer_with_url, upload_video

logger = logging.getLogger()


class StrategyType(EnumType):
    url = "url"
    video_url = "video_url"


class Provider(EnumType):
    instagram = "instagram"
    tiktok = "tiktok"
    twitter = "twitter"
    youtube = "youtube"


class AbstractStrategy(ABC):
    strategy_type: StrategyType

    @abstractmethod
    async def run(self, url: str) -> str | None:
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

    async def run(self, provider: Provider, message: types.Message) -> None:
        registry_item = self.items[provider]

        url_regex = getattr(FilterUrlRegex, str(provider))
        result = re.findall(url_regex, message.text)
        if result:
            url = result[0]
        else:
            logger.info(f"[{provider}] got text '{message.text}', could not find url")
            return
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
        else:
            logger.info(f"[{_id}] No strategies left, exiting")
