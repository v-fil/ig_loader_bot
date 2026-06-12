"""Phase 4: answer_with_album chunking, captions and failure handling."""
import re
from unittest.mock import AsyncMock

import pytest
from aiogram.types import InputMediaPhoto, InputMediaVideo
from aioresponses import aioresponses

from strategies.types import FileType, ResultType
from strategies.utils import Answer, Link, UploadError, answer_with_album

CDN = re.compile(r"^https://cdn\.example/.*$")


@pytest.fixture
def mock_http():
    with aioresponses() as m:
        yield m


@pytest.fixture
def message():
    msg = AsyncMock()
    msg.message_id = 42
    return msg


def make_answer(count: int, text: str | None = None) -> Answer:
    links = [
        Link(url=f"https://cdn.example/item{i}", file_type=FileType.img, filename=f"{i}.jpg")
        for i in range(count)
    ]
    return Answer(links=links, result_type=ResultType.items_list, text=text)


async def test_23_items_sent_in_chunks_of_10_10_3(mock_http, message):
    mock_http.get(CDN, body=b"IMG", content_type="image/jpeg", repeat=True)

    await answer_with_album(make_answer(23), message)

    sizes = [len(call.args[0]) for call in message.reply_media_group.await_args_list]
    assert sizes == [10, 10, 3]


async def test_media_types_match_link_filetypes(mock_http, message):
    mock_http.get(CDN, body=b"DATA", content_type="application/octet-stream", repeat=True)
    answer = Answer(
        links=[
            Link(url="https://cdn.example/a", file_type=FileType.img, filename="a.jpg"),
            Link(url="https://cdn.example/b", file_type=FileType.video, filename="b.mp4"),
        ],
        result_type=ResultType.items_list,
    )

    await answer_with_album(answer, message)

    items = message.reply_media_group.await_args.args[0]
    assert isinstance(items[0], InputMediaPhoto)
    assert isinstance(items[1], InputMediaVideo)
    assert items[0].media.filename == "a.jpg"
    assert items[1].media.filename == "b.mp4"


async def test_short_caption_lands_on_first_item_only(mock_http, message):
    mock_http.get(CDN, body=b"IMG", content_type="image/jpeg", repeat=True)
    caption = "short caption"

    await answer_with_album(make_answer(12, text=caption), message)

    chunks = [call.args[0] for call in message.reply_media_group.await_args_list]
    items = [item for chunk in chunks for item in chunk]
    assert items[0].caption == caption
    assert all(item.caption is None for item in items[1:])
    message.answer.assert_not_awaited()


async def test_long_caption_sent_as_followup_text(mock_http, message):
    mock_http.get(CDN, body=b"IMG", content_type="image/jpeg", repeat=True)
    caption = "x" * 1500  # over the 1024 caption limit, under the 4096 text limit

    await answer_with_album(make_answer(2, text=caption), message)

    items = message.reply_media_group.await_args.args[0]
    assert all(item.caption is None for item in items)
    message.answer.assert_awaited_once()
    assert message.answer.await_args.args[0] == caption
    assert message.answer.await_args.kwargs["disable_web_page_preview"] is True


async def test_very_long_caption_split_into_multiple_messages(mock_http, message):
    mock_http.get(CDN, body=b"IMG", content_type="image/jpeg", repeat=True)
    caption = "word " * 2000  # ~10k chars, needs several 4096-char messages

    await answer_with_album(make_answer(2, text=caption), message)

    assert message.answer.await_count > 1
    sent = " ".join(call.args[0] for call in message.answer.await_args_list)
    assert sent.split() == caption.split()


async def test_single_image_sent_as_photo_not_media_group(mock_http, message):
    mock_http.get(CDN, body=b"IMG", content_type="image/jpeg")

    await answer_with_album(make_answer(1, text="caption"), message)

    message.reply_media_group.assert_not_awaited()
    message.answer_photo.assert_awaited_once()
    file = message.answer_photo.await_args.args[0]
    assert file.filename == "0.jpg"
    assert message.answer_photo.await_args.kwargs["caption"] == "caption"


async def test_single_video_sent_as_video_not_media_group(mock_http, message):
    mock_http.get(CDN, body=b"VID", content_type="video/mp4")
    answer = Answer(
        links=[Link(url="https://cdn.example/a", file_type=FileType.video, filename="a.mp4")],
        result_type=ResultType.items_list,
    )

    await answer_with_album(answer, message)

    message.reply_media_group.assert_not_awaited()
    message.answer_video.assert_awaited_once()
    assert message.answer_video.await_args.args[0].filename == "a.mp4"


async def test_single_item_long_caption_sent_as_followup_text(mock_http, message):
    mock_http.get(CDN, body=b"IMG", content_type="image/jpeg")
    caption = "x" * 1500  # over the 1024 caption limit

    await answer_with_album(make_answer(1, text=caption), message)

    assert message.answer_photo.await_args.kwargs["caption"] is None
    message.answer.assert_awaited_once()
    assert message.answer.await_args.args[0] == caption


async def test_downloads_collapsing_to_one_item_sent_as_photo(mock_http, message):
    answer = make_answer(3)
    mock_http.get(answer.links[0].url, status=404, body=b"gone")
    mock_http.get(answer.links[1].url, body=b"IMG", content_type="image/jpeg")
    mock_http.get(answer.links[2].url, status=404, body=b"gone")

    await answer_with_album(answer, message)

    message.reply_media_group.assert_not_awaited()
    message.answer_photo.assert_awaited_once()


async def test_all_downloads_failed_raises_upload_error(mock_http, message):
    mock_http.get(CDN, status=404, body=b"gone", repeat=True)

    with pytest.raises(UploadError):
        await answer_with_album(make_answer(3), message)

    message.reply_media_group.assert_not_awaited()


async def test_failed_downloads_are_dropped(mock_http, message):
    answer = make_answer(3)
    mock_http.get(answer.links[0].url, body=b"IMG", content_type="image/jpeg")
    mock_http.get(answer.links[1].url, status=404, body=b"gone")
    mock_http.get(answer.links[2].url, body=b"IMG", content_type="image/jpeg")

    await answer_with_album(answer, message)

    items = message.reply_media_group.await_args.args[0]
    assert len(items) == 2
