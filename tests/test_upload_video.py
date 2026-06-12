"""Phase 4: _remote_size + upload_video + answer_with_photo, and the f0d4e8a encoded-URL regression.

The regression tests run against a real localhost aiohttp server instead of
aioresponses: aioresponses normalizes URLs before matching and recording, which
makes the byte-for-byte URL and the requoted (buggy) URL indistinguishable.
A real server exposes the wire bytes via request.raw_path.
"""
import asyncio
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import BufferedInputFile, InputMediaPhoto, URLInputFile
from aiohttp import ClientError, ClientSession, web
from aiohttp.test_utils import TestServer
from aioresponses import aioresponses
from yarl import URL

import strategies.utils as utils
from strategies.types import FileType
from strategies.utils import TG_SIZE_LIMIT, _remote_size, answer_with_photo, download_file, upload_video

VIDEO_URL = "https://cdn.example/v/video.mp4"
PHOTO_URL = "https://cdn.example/v/photo.jpg"


@pytest.fixture
def mock_http():
    with aioresponses() as m:
        yield m


@pytest.fixture
def message():
    msg = AsyncMock()
    msg.message_id = 42
    return msg


# --- _remote_size ---


async def test_remote_size_returns_content_length(mock_http):
    mock_http.head(VIDEO_URL, headers={"Content-Length": "12345"})

    assert await _remote_size(VIDEO_URL) == 12345


async def test_remote_size_without_content_length_returns_none(mock_http):
    mock_http.head(VIDEO_URL)

    assert await _remote_size(VIDEO_URL) is None


@pytest.mark.parametrize("exc", [asyncio.TimeoutError(), ClientError("boom")])
async def test_remote_size_request_failure_returns_none(mock_http, exc):
    mock_http.head(VIDEO_URL, exception=exc)

    assert await _remote_size(VIDEO_URL) is None


async def test_remote_size_malformed_content_length_returns_none(mock_http):
    mock_http.head(VIDEO_URL, headers={"Content-Length": "garbage"})

    assert await _remote_size(VIDEO_URL) is None


# --- upload_video ---


@pytest.mark.parametrize(
    "head_headers",
    [{"Content-Length": "1000"}, {}],
    ids=["size-under-limit", "size-unknown"],
)
async def test_url_upload_path_without_download(mock_http, message, head_headers):
    mock_http.head(VIDEO_URL, headers=head_headers)
    # no GET registered: a download attempt would raise a connection error

    assert await upload_video(VIDEO_URL, message) is True

    message.answer_video.assert_awaited_once()
    file = message.answer_video.await_args.args[0]
    assert isinstance(file, URLInputFile)
    assert file.url == VIDEO_URL
    assert not any(method == "GET" for method, _ in mock_http.requests)


async def test_oversized_remote_skips_url_upload_and_downloads(mock_http, message):
    mock_http.head(VIDEO_URL, headers={"Content-Length": str(TG_SIZE_LIMIT + 1)})
    mock_http.get(VIDEO_URL, body=b"VIDEODATA", content_type="video/mp4")

    assert await upload_video(VIDEO_URL, message) is True

    message.answer_video.assert_awaited_once()
    file = message.answer_video.await_args.args[0]
    assert isinstance(file, BufferedInputFile)
    assert file.data == b"VIDEODATA"


async def test_network_error_on_url_path_falls_back_to_download(mock_http, message):
    mock_http.head(VIDEO_URL, headers={"Content-Length": "1000"})
    mock_http.get(VIDEO_URL, body=b"VIDEODATA", content_type="video/mp4")
    message.answer_video.side_effect = [TelegramNetworkError(method=None, message="boom"), None]

    assert await upload_video(VIDEO_URL, message) is True

    assert message.answer_video.await_count == 2
    first, second = message.answer_video.await_args_list
    assert isinstance(first.args[0], URLInputFile)
    assert isinstance(second.args[0], BufferedInputFile)
    assert second.args[0].data == b"VIDEODATA"


@pytest.mark.parametrize("content_type", ["text/plain", "text/plain; charset=utf-8"])
async def test_text_plain_download_returns_false(mock_http, message, content_type):
    mock_http.head(VIDEO_URL, headers={"Content-Length": str(TG_SIZE_LIMIT + 1)})
    mock_http.get(VIDEO_URL, body=b"some error page", content_type=content_type)

    assert await upload_video(VIDEO_URL, message) is False

    message.answer_video.assert_not_awaited()


async def test_download_failure_returns_false(mock_http, message):
    mock_http.head(VIDEO_URL, headers={"Content-Length": str(TG_SIZE_LIMIT + 1)})
    mock_http.get(VIDEO_URL, status=404, body=b"not found", content_type="video/mp4")

    assert await upload_video(VIDEO_URL, message) is False

    message.answer_video.assert_not_awaited()


async def test_oversized_download_is_transcoded(mock_http, message, monkeypatch):
    monkeypatch.setattr(utils, "TG_SIZE_LIMIT", 10)
    transcode = AsyncMock(return_value=b"tiny")
    monkeypatch.setattr(utils, "transcode_video", transcode)
    mock_http.head(VIDEO_URL, headers={"Content-Length": "11"})
    mock_http.get(VIDEO_URL, body=b"x" * 20, content_type="video/mp4")

    assert await upload_video(VIDEO_URL, message) is True

    transcode.assert_awaited_once_with(b"x" * 20)
    file = message.answer_video.await_args.args[0]
    assert isinstance(file, BufferedInputFile)
    assert file.data == b"tiny"


async def test_failed_transcode_returns_false(mock_http, message, monkeypatch):
    monkeypatch.setattr(utils, "TG_SIZE_LIMIT", 10)
    monkeypatch.setattr(utils, "transcode_video", AsyncMock(return_value=None))
    mock_http.head(VIDEO_URL, headers={"Content-Length": "11"})
    mock_http.get(VIDEO_URL, body=b"x" * 20, content_type="video/mp4")

    assert await upload_video(VIDEO_URL, message) is False

    message.answer_video.assert_not_awaited()


# --- answer_with_photo ---


async def test_photo_downloads_and_sends(mock_http, message):
    mock_http.get(PHOTO_URL, body=b"IMGDATA", content_type="image/jpeg")

    assert await answer_with_photo(PHOTO_URL, message, "post.jpg") is True

    message.answer_photo.assert_awaited_once()
    file = message.answer_photo.await_args.args[0]
    assert isinstance(file, BufferedInputFile)
    assert file.data == b"IMGDATA"
    assert file.filename == "post.jpg"


async def test_photo_without_filename_uses_default(mock_http, message):
    mock_http.get(PHOTO_URL, body=b"IMGDATA", content_type="image/jpeg")

    assert await answer_with_photo(PHOTO_URL, message) is True

    assert message.answer_photo.await_args.args[0].filename == "photo.jpg"


@pytest.mark.parametrize("content_type", ["text/plain", "text/plain; charset=utf-8"])
async def test_photo_text_plain_download_returns_false(mock_http, message, content_type):
    mock_http.get(PHOTO_URL, body=b"URL signature mismatch", content_type=content_type)

    assert await answer_with_photo(PHOTO_URL, message) is False

    message.answer_photo.assert_not_awaited()


async def test_photo_download_failure_returns_false(mock_http, message):
    mock_http.get(PHOTO_URL, status=404, body=b"not found", content_type="image/jpeg")

    assert await answer_with_photo(PHOTO_URL, message) is False

    message.answer_photo.assert_not_awaited()


async def test_photo_network_error_returns_false(mock_http, message):
    mock_http.get(PHOTO_URL, body=b"IMGDATA", content_type="image/jpeg")
    message.answer_photo.side_effect = TelegramNetworkError(method=None, message="boom")

    assert await answer_with_photo(PHOTO_URL, message) is False


# --- f0d4e8a regression: signed CDN URLs must hit the wire byte-for-byte ---

# %2F, %21 and %2C in query values are exactly the escapes yarl's default
# requoting decodes, which breaks IG's CDN signature.
SIGNED_QUERY = "token=abc%2Fdef%21ghi%2Cjkl&_nc=AbC-123"
SIGNED_PATH = f"/v/video.mp4?{SIGNED_QUERY}"


def test_yarl_default_requoting_canary():
    # documents why encoded=True matters: with yarl's default requoting the
    # query escapes are decoded and the tests below would fail
    url = f"https://cdn.example{SIGNED_PATH}"
    assert str(URL(url)) != url
    assert str(URL(url, encoded=True)) == url


@pytest.fixture
async def raw_server():
    seen: list[tuple[str, str]] = []

    async def handler(request: web.Request) -> web.Response:
        seen.append((request.method, request.raw_path))
        return web.Response(body=b"0123456789", content_type="video/mp4")

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    server = TestServer(app)
    await server.start_server()
    yield server, seen
    await server.close()


def signed_url(server: TestServer) -> str:
    return f"http://{server.host}:{server.port}{SIGNED_PATH}"


async def test_remote_size_requests_url_byte_for_byte(raw_server):
    server, seen = raw_server

    size = await _remote_size(signed_url(server))

    assert size == 10
    assert seen == [("HEAD", SIGNED_PATH)]


async def test_upload_video_downloads_url_byte_for_byte(raw_server, message):
    server, seen = raw_server
    # fail the URL-upload path so upload_video falls back to downloading
    message.answer_video.side_effect = [TelegramNetworkError(method=None, message="boom"), None]

    assert await upload_video(signed_url(server), message) is True

    assert seen == [("HEAD", SIGNED_PATH), ("GET", SIGNED_PATH)]


async def test_download_file_requests_url_byte_for_byte(raw_server):
    server, seen = raw_server

    async with ClientSession() as session:
        media = await download_file(signed_url(server), FileType.img, "0.jpg", session)

    assert isinstance(media, InputMediaPhoto)
    assert seen == [("GET", SIGNED_PATH)]


async def test_answer_with_photo_downloads_url_byte_for_byte(raw_server, message):
    server, seen = raw_server

    assert await answer_with_photo(signed_url(server), message) is True

    assert seen == [("GET", SIGNED_PATH)]
