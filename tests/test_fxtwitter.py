"""Phase 3: FxTwitterStrategy with mocked HTTP."""
import json

import pytest
from aioresponses import aioresponses

from strategies.types import FileType, ResultType
from strategies.x import FxTwitterStrategy
from tests.conftest import load_fixture

TWEET_URL = "https://x.com/someuser/status/123"
API_URL = "https://api.fxtwitter.com/someuser/status/123"


@pytest.fixture
def mock_http():
    with aioresponses() as m:
        yield m


def media_payload(*items: dict) -> dict:
    return {"tweet": {"media": {"all": list(items)}}}


async def test_fixture_photo_tweet(mock_http):
    mock_http.get(
        "https://api.fxtwitter.com/TheEllenShow/status/440322224407314432",
        payload=json.loads(load_fixture("fxtwitter_status.json")),
    )

    answer = await FxTwitterStrategy().run("https://twitter.com/TheEllenShow/status/440322224407314432")

    assert answer.result_type == ResultType.items_list
    assert len(answer.links) == 1
    assert answer.links[0].filetype == FileType.img
    assert answer.links[0].url == "https://pbs.twimg.com/media/BhxWutnCEAAtEQ6.jpg?name=orig"
    assert answer.links[0].filename == "x_440322224407314432_0.jpg"


@pytest.mark.parametrize("kind", ["video", "gif"])
async def test_single_video_or_gif(mock_http, kind):
    mock_http.get(API_URL, payload=media_payload(
        {"type": kind, "url": "https://video.twimg.com/v.mp4"},
    ))

    answer = await FxTwitterStrategy().run(TWEET_URL)

    assert answer.result_type == ResultType.video_url
    assert len(answer.links) == 1
    assert answer.links[0].url == "https://video.twimg.com/v.mp4"


async def test_mixed_media(mock_http):
    mock_http.get(API_URL, payload=media_payload(
        {"type": "photo", "url": "https://pbs.twimg.com/media/a.jpg"},
        {"type": "video", "url": "https://video.twimg.com/b.mp4"},
    ))

    answer = await FxTwitterStrategy().run(TWEET_URL)

    assert answer.result_type == ResultType.items_list
    assert [(link.filetype, link.filename) for link in answer.links] == [
        (FileType.img, "x_123_0.jpg"),
        (FileType.video, "x_123_1.mp4"),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"tweet": {}},
        {"tweet": {"media": {"all": []}}},
        {},
        # media entries without a url are skipped
        {"tweet": {"media": {"all": [{"type": "photo"}]}}},
    ],
    ids=["no-media", "empty-media", "no-tweet", "media-without-url"],
)
async def test_no_usable_media_returns_none(mock_http, payload):
    mock_http.get(API_URL, payload=payload)

    assert await FxTwitterStrategy().run(TWEET_URL) is None


async def test_404_returns_none(mock_http):
    mock_http.get(API_URL, status=404)

    assert await FxTwitterStrategy().run(TWEET_URL) is None


async def test_non_json_returns_none(mock_http):
    mock_http.get(API_URL, body="<html>down for maintenance</html>")

    assert await FxTwitterStrategy().run(TWEET_URL) is None


async def test_non_tweet_url_returns_none(mock_http):
    # no mock registered: the strategy must bail before any HTTP request
    assert await FxTwitterStrategy().run("https://x.com/someuser") is None
