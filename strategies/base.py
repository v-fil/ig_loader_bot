import logging
import re
from abc import ABC, abstractmethod
from typing import Optional

from aiogram import types

from strategies.utils import answer_with_url, upload_video, Answer, answer_with_album, UploadError

from .types import FilterUrlRegex, ResultType, Provider

logger = logging.getLogger()


def get_provider_by_url(url: str) -> str:
    for provider, member in FilterUrlRegex.__members__.items():
        if re.match(member.value, url):
            return provider


class AbstractStrategy(ABC):
    @abstractmethod
    async def run(self, url: str) -> Answer | None:
        pass


class RegistryItem:
    strategies: list[AbstractStrategy]
    extract_id: callable
    preprocess_url: Optional[callable]

    def __init__(
        self, strategies: list[AbstractStrategy], extract_id: callable, preprocess_url: Optional[callable] = None
    ) -> None:
        assert strategies is not None
        assert extract_id

        self.strategies = strategies
        self.extract_id = extract_id
        self.preprocess_url = preprocess_url


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

        if registry_item.preprocess_url:
            logger.info(f"[{provider}][{_id}] preprocessing url '{url}'")
            url = await registry_item.preprocess_url(url)
            logger.info(f"[{provider}][{_id}] preprocessed url '{url}'")

        result = None
        for strategy in registry_item.strategies:
            logger.info(f"[{_id}] Running with {strategy.__class__.__name__}")
            result = await strategy.run(url)
            if result:
                logger.info(f"[{_id}] got result url: {result.links}")
                if result.result_type == ResultType.video_url:
                    try:
                        logger.info(f"[{_id}] trying to upload result")
                        uploaded = await upload_video(result.links[0].url, message)
                        if uploaded:
                            logger.info(f"[{_id}] successfully uploaded result, exiting")
                            return
                        continue
                    except Exception as e:
                        logger.error(f'[{_id}] {str(e)}')
                        await answer_with_url(result.links[0].url, message)
                        return

                elif result.result_type == ResultType.url:
                    logger.info(f"[{_id}] trying to upload result")
                    await answer_with_url(result.links[0].url, message)
                    return

                elif result.result_type == ResultType.items_list:
                    logger.info(f"[{_id}] trying to upload album")
                    try:
                        await answer_with_album(result, message)
                    except UploadError:
                        continue
                    return
        else:
            if result:
                await answer_with_url(result.links[0].url, message)
            logger.info(f"[{_id}] No strategies left, exiting")
