import logging
from asyncio import gather
from enum import Enum

from aiogram.exceptions import TelegramNetworkError
from aiogram.types import BufferedInputFile, Message, URLInputFile, InputMediaVideo, InputMediaPhoto, InputMedia
from aiogram.utils.formatting import TextLink
from aiohttp import ClientSession, ClientPayloadError


class FileType(Enum):
    img = 'img'
    video = 'video'


class UploadError(Exception):
    """"""


class Link:
    def __init__(self, url: str | None = None, file_type: FileType | None = None, filename: str | None = None):
        self.url: str = url
        self.filename: str = filename
        self.filetype: FileType = file_type

    def __repr__(self):
        return f'<Link {self.filetype}: {self.filename}>'


class Answer:
    links: list[Link]

    def __init__(self, links: list[Link] | None = None):
        self.links = links or []



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

    content = None
    async with ClientSession() as session:
        result = await session.get(url)
        if result.ok:
            content = await result.content.read()
        else:
            logging.info("Download failed")

    if content:
        tg_file = BufferedInputFile(content, "ig_file.mp4")
        try:
            await message.answer_video(tg_file, reply_to_message_id=message.message_id, supports_streaming=True)
            return
        except TelegramNetworkError as e:
            logging.error(f"Telegram Network Error: {e}")
            pass

    await answer_with_url(url, message)


async def download_file(url, file_type, filename, session):
    result = await session.get(url)
    if result.ok:
        try:
            content = await result.content.read()
        except ClientPayloadError as e:
            logging.error(f"Client PayloadError: {e}")
            return
    else:
        logging.info("Download failed")
        return
    if file_type == FileType.video:
        return InputMediaVideo(media=BufferedInputFile(content, filename))
    if file_type == FileType.img:
        return InputMediaPhoto(media=BufferedInputFile(content, filename))


async def answer_with_album(answer: Answer, message: Message) -> None:
    coroutines = []

    async with ClientSession() as session:
        for item in answer.links:
            coroutines.append(download_file(item.url, item.filetype, item.filename, session))
        resp = await gather(*coroutines)

        if not any((isinstance(i, InputMedia) for i in resp)):
            raise UploadError
    await message.reply_media_group(resp, reply_to_message_id=message.message_id)
