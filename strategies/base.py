import logging
from abc import ABC, abstractmethod
from enum import EnumType

from aiogram import exceptions, types

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

        _id = registry_item.extract_id(message.text)

        for strategy in registry_item.strategies:
            logger.info(f"[{_id}] Running with {strategy.__class__.__name__}")
            result = await strategy.run(message.text)
            if result:
                logger.info(f"[{_id}] got result")
                if strategy.strategy_type == StrategyType.video_url:
                    try:
                        logger.info(f"[{_id}] trying to upload result")
                        await upload_video(result, message)
                        logger.info(f"[{_id}] successfully uploaded result, exiting")
                        return
                    except exceptions.TelegramNetworkError:
                        pass
                elif strategy.strategy_type == StrategyType.url:
                    logger.info(f"[{_id}] trying to upload result")
                    await answer_with_url(result, message)
                    return
        else:
            logger.info(f"[{_id}] No strategies left, exiting")
