import asyncio
import logging
import os
import tempfile

import requests
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import BufferedInputFile, Message, URLInputFile, InputMediaVideo, InputMediaPhoto, InputMedia
from aiogram.utils.formatting import TextLink
from aiohttp import ClientSession, ClientPayloadError, ClientResponse

from .types import FileType, ResultType


logger = logging.getLogger()

# Telegram bots may upload files up to 50 MB; aim a bit lower to leave headroom.
TG_SIZE_LIMIT = 50 * 1024 * 1024
TRANSCODE_TARGET = 45 * 1024 * 1024


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
    result_type: ResultType
    links: list[Link]
    text: str | None

    def __init__(
        self,
        links: list[Link] | None = None,
        result_type: ResultType = ResultType.video_url,
        text: str | None = None,
    ):
        self.result_type = result_type
        self.links = links or []
        self.text = text


async def get_content(result: ClientResponse) -> bytes | None:
    if result.ok:
        try:
            content = await result.content.read()
            return content
        except TimeoutError as e:
            logger.error(f"Time out reading content: {e}")
        except ClientPayloadError as e:
            logger.error(f"Client PayloadError: {e}")

    else:
        text = await result.content.read()
        logger.info(f"Download failed status:{result.status} reason: {result.reason} text: {text}")


async def _ffprobe_duration(path: str) -> float | None:
    proc = await asyncio.create_subprocess_exec(
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip())
    except (ValueError, AttributeError):
        return None


async def transcode_video(content: bytes) -> bytes | None:
    """Re-encode an oversized video so it fits under Telegram's upload limit."""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'src.mp4')
        dst = os.path.join(tmp, 'out.mp4')
        with open(src, 'wb') as f:
            f.write(content)

        duration = await _ffprobe_duration(src)
        if not duration:
            logger.error('transcode: could not determine video duration')
            return None

        # Pick a video bitrate that, together with the audio, lands under the target size.
        audio_bitrate = 128_000
        video_bitrate = max(int(TRANSCODE_TARGET * 8 / duration) - audio_bitrate, 100_000)
        logger.info(f'transcode: duration={duration:.0f}s, video bitrate={video_bitrate}')

        proc = await asyncio.create_subprocess_exec(
            'ffmpeg', '-y', '-i', src,
            '-c:v', 'libx264', '-preset', 'veryfast',
            '-b:v', str(video_bitrate), '-maxrate', str(video_bitrate),
            '-bufsize', str(video_bitrate * 2),
            '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            dst,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f'transcode: ffmpeg failed: {err.decode(errors="replace")[-500:]}')
            return None

        with open(dst, 'rb') as f:
            result = f.read()
        logger.info(f'transcode: {len(content)} -> {len(result)} bytes')
        if len(result) > TG_SIZE_LIMIT:
            logger.error('transcode: result still exceeds Telegram limit')
            return None
        return result


async def answer_with_url(url: str, message: Message) -> None:
    content = TextLink("url", url=url)
    await message.answer(**content.as_kwargs(), reply_to_message_id=message.message_id)


async def _remote_size(url: str) -> int | None:
    """Return Content-Length for a URL via a HEAD request, or None if unknown."""
    try:
        async with ClientSession() as session:
            async with session.head(url, allow_redirects=True) as resp:
                length = resp.headers.get('Content-Length')
                return int(length) if length else None
    except (ClientPayloadError, ValueError, OSError) as e:
        logger.info(f"HEAD request failed for {url}: {e}")
        return None


async def upload_video(url: str, message: Message) -> bool:
    # Letting Telegram fetch the URL itself is the cheap path, but it fails for
    # oversized files - skip straight to download + transcode if we know it's too big.
    size = await _remote_size(url)
    if size is None or size <= TG_SIZE_LIMIT:
        file = URLInputFile(url)
        try:
            await message.answer_video(file, reply_to_message_id=message.message_id, supports_streaming=True)
            return True
        except TelegramNetworkError as e:
            logger.error(f"Telegram Network Error: {e}")
    else:
        logger.info(f"{size} bytes exceeds Telegram limit, skipping URL upload")

    logger.info(f"Trying to download {url}")

    # TODO: find out why instagram returns URL mismatch if load using asyncio
    if 'instagram' in url:
        resp = await asyncio.to_thread(requests.get, url)
        content = resp.content
        if resp.headers['Content-Type'] == 'text/plain':
            logger.info('Got invalid content type')
            return False
    else:
        async with ClientSession() as session:
            result = await session.get(url)
            content = await get_content(result)

    if content and len(content) > TG_SIZE_LIMIT:
        logger.info(f"{len(content)} bytes exceeds Telegram limit, transcoding")
        content = await transcode_video(content)

    if content:
        tg_file = BufferedInputFile(content, "ig_file.mp4")
        try:
            await message.answer_video(tg_file, reply_to_message_id=message.message_id, supports_streaming=True)
            return True
        except TelegramNetworkError as e:
            logger.error(f"Telegram Network Error: {e}")

    return False


async def download_file(
        url: str, file_type: str, filename: str, session: ClientSession
) -> InputMediaVideo | InputMediaPhoto | None:
    result = await session.get(url)
    content = await get_content(result)
    if not content:
        return
    if file_type == FileType.video:
        return InputMediaVideo(media=BufferedInputFile(content, filename))
    if file_type == FileType.img:
        return InputMediaPhoto(media=BufferedInputFile(content, filename))


TG_CAPTION_LIMIT = 1024
TG_TEXT_LIMIT = 4096


def _split_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        window = remaining[:limit]
        for sep in ("\n\n", "\n", " "):
            idx = window.rfind(sep)
            if idx >= limit // 3:
                cut = idx + len(sep)
                chunks.append(remaining[:cut].rstrip())
                remaining = remaining[cut:].lstrip()
                break
        else:
            chunks.append(remaining[:limit])
            remaining = remaining[limit:]
    if remaining:
        chunks.append(remaining)
    return chunks


async def answer_with_text(answer: Answer, message: Message) -> None:
    text = (answer.text or "").strip()
    if not text:
        return
    for chunk in _split_text(text, TG_TEXT_LIMIT):
        await message.answer(
            chunk,
            reply_to_message_id=message.message_id,
            disable_web_page_preview=True,
        )


async def answer_with_album(answer: Answer, message: Message) -> None:
    coroutines = []

    async with ClientSession() as session:
        for item in answer.links:
            coroutines.append(download_file(item.url, item.filetype, item.filename, session))
        resp = await asyncio.gather(*coroutines)

        # Filter out None results from failed downloads
        media_items = [i for i in resp if isinstance(i, InputMedia)]

        if not media_items:
            raise UploadError

    text = (answer.text or "").strip()
    leftover_text: str | None = None
    if text:
        if len(text) <= TG_CAPTION_LIMIT:
            media_items[0].caption = text
        else:
            # Caption too long; send the full text as a follow-up reply.
            leftover_text = text

    # Telegram limits media groups to 10 items, split into chunks
    chunk_size = 10
    for i in range(0, len(media_items), chunk_size):
        chunk = media_items[i:i + chunk_size]
        await message.reply_media_group(chunk, reply_to_message_id=message.message_id)

    if leftover_text:
        for chunk in _split_text(leftover_text, TG_TEXT_LIMIT):
            await message.answer(
                chunk,
                reply_to_message_id=message.message_id,
                disable_web_page_preview=True,
            )
