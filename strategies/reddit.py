import logging
import re
import subprocess
import tempfile
from pathlib import Path

import requests
from aiohttp import ClientSession

from .base import AbstractStrategy
from .utils import Answer, Link
from .types import ResultType, FileType

logger = logging.getLogger()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def extract_id(text: str) -> str:
    match = re.search(r"reddit\.com/r/\S*/comments/([a-z0-9]*)/", text)
    if match:
        return f"REDDIT:{match.group(1)}"
    return f"REDDIT:{text}"


def get_reddit_video_url(reddit_url: str) -> tuple[str, list[str], str]:
    if not reddit_url.endswith('.json'):
        json_url = reddit_url.rstrip('/') + '.json'
    else:
        json_url = reddit_url

    response = requests.get(json_url, headers=HEADERS)
    response.raise_for_status()

    data = response.json()
    post_data = data[0]['data']['children'][0]['data']

    title = post_data.get('title', 'reddit_video')
    filename = re.sub(r'[<>:"/\\|?*]', '', title)[:50]

    if 'secure_media' in post_data and post_data['secure_media']:
        reddit_video = post_data['secure_media'].get('reddit_video', {})
    elif 'media' in post_data and post_data['media']:
        reddit_video = post_data['media'].get('reddit_video', {})
    else:
        raise ValueError("No video in this post")

    video_url = reddit_video.get('fallback_url') or reddit_video.get('scrubber_media_url')

    if not video_url:
        raise ValueError("No video in url")

    clean_url = video_url.split('?')[0]
    base_url = clean_url.rsplit('/', 1)[0] + '/'

    audio_urls = [
        base_url + 'DASH_AUDIO_128.mp4',
        base_url + 'DASH_audio.mp4',
        base_url + 'DASH_AUDIO_64.mp4',
        base_url + 'audio.mp4',
        base_url + 'audio',
        base_url + 'CMAF_AUDIO_128.mp4',
        base_url + 'HLS_AUDIO_128.m4a',
    ]

    return video_url, audio_urls, filename


class RedditStrategy(AbstractStrategy):
    async def run(self, url: str) -> Answer | None:
        try:
            video_url, audio_urls, filename = get_reddit_video_url(url)

            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                video_file = tmp_path / f"{filename}_video.mp4"
                audio_file = tmp_path / f"{filename}_audio.mp4"
                output_file = tmp_path / f"{filename}.mp4"

                async with ClientSession() as session:
                    async with session.get(video_url, headers=HEADERS) as resp:
                        if resp.status != 200:
                            logger.error(f"Failed to download video: {resp.status}")
                            return None
                        content = await resp.read()
                        video_file.write_bytes(content)

                has_audio = False
                async with ClientSession() as session:
                    for audio_url in audio_urls:
                        try:
                            async with session.get(audio_url, headers=HEADERS) as resp:
                                if resp.status == 200:
                                    content = await resp.read()
                                    audio_file.write_bytes(content)
                                    has_audio = True
                                    logger.info(f"Audio found: {audio_url.split('/')[-1]}")
                                    break
                        except Exception as e:
                            logger.debug(f"Audio URL failed: {audio_url} - {e}")
                            continue

                if has_audio:
                    # Merge video and audio with ffmpeg
                    try:
                        subprocess.run([
                            'ffmpeg', '-y',
                            '-i', str(video_file),
                            '-i', str(audio_file),
                            '-c:v', 'copy',
                            '-c:a', 'aac',
                            '-strict', 'experimental',
                            str(output_file)
                        ], check=True, capture_output=True)
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        logger.warning(f"ffmpeg merge failed: {e}, using video only")
                        output_file = video_file
                else:
                    logger.info("No audio found, using video only")
                    output_file = video_file

                final_content = output_file.read_bytes()

                final_path = Path('/tmp') / f"reddit_{filename}.mp4"
                final_path.write_bytes(final_content)

                return Answer(
                    links=[Link(url=str(final_path), file_type=FileType.video)],
                    result_type=ResultType.video_url
                )

        except Exception as e:
            logger.error(f"Reddit strategy failed: {e}")
            return None


class RedditDirectStrategy(AbstractStrategy):
    async def run(self, url: str) -> Answer | None:
        try:
            video_url, _, _ = get_reddit_video_url(url)
            return Answer(
                links=[Link(url=video_url, file_type=FileType.video)],
                result_type=ResultType.video_url
            )
        except Exception as e:
            logger.error(f"Reddit direct strategy failed: {e}")
            return None
