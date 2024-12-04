import logging
from abc import ABC, abstractmethod
from enum import EnumType

from aiogram import exceptions, types

from handlers.utils import answer_with_url, upload_video

logger = logging.getLogger()


class StrategyType(EnumType):
    url = "url"
    video_url = "video_url"


class AbstractStrategy(ABC):
    strategy_type: StrategyType

    @abstractmethod
    async def run(self, url: str) -> str | None:
        pass


class AbstractRunner(ABC):
    strategies: list[AbstractStrategy]

    @abstractmethod
    def extract_id(self, text: str) -> str:
        return text

    async def run(self, message: types.Message) -> None:
        text = self.extract_id(message.text)

        for strategy in self.strategies:
            logger.info(f"[{text}] Running with {strategy.__class__.__name__}")
            result = await strategy.run(message.text)
            if result:
                logger.info(f"[{text}] got result")
                if strategy.strategy_type == StrategyType.video_url:
                    try:
                        logger.info(f"[{text}] trying to upload result")
                        await upload_video(result, message)
                        logger.info(f"[{text}] successfully uploaded result, exiting")
                        return
                    except exceptions.TelegramNetworkError:
                        pass
                elif strategy.strategy_type == StrategyType.url:
                    logger.info(f"[{text}] trying to upload result")
                    await answer_with_url(result, message)
                    return
        else:
            logger.info(f"[{text}] No strategies left, exiting")
