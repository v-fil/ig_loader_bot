import logging

from aiogram.exceptions import TelegramNetworkError
from aiogram.types import BufferedInputFile, Message, URLInputFile
from aiogram.utils.formatting import TextLink
from aiohttp import ClientSession


async def answer_with_url(url: str, message: Message) -> None:
    content = TextLink("url", url=url)
    await message.answer(**content.as_kwargs(), reply_to_message_id=message.message_id)


async def upload_video(url: str, message: Message) -> None:
    file = URLInputFile(url)
    try:
        await message.answer_video(file, reply_to_message_id=message.message_id)
        return
    except TelegramNetworkError as e:
        logging.error(f"Telegram Network Error: {e}")
        pass

    logging.info(f"Trying to download {url}")
    async with ClientSession() as session:
        result = await session.get(url)
        if not result.ok:
            return
        content = await result.content.read()

    tg_file = BufferedInputFile(content, "ig_file.mp4")
    try:
        await message.answer_video(tg_file, reply_to_message_id=message.message_id, supports_streaming=True)
        return
    except TelegramNetworkError as e:
        logging.error(f"Telegram Network Error: {e}")
        pass

    await answer_with_url(url, message)
