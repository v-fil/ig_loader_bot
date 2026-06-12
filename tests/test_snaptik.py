"""Phase 3: SnaptikSessionStrategy with mocked HTTP.

Every failure shape must return None without raising (regression for the dead
`except IndexError` removed in ed4dbeb).
"""
import json

import pytest
from aioresponses import aioresponses

from strategies.tiktok import SnaptikSessionStrategy
from strategies.types import ResultType
from tests.conftest import load_fixture

LANDING = "https://snaptik.pro/"
ACTION = "https://snaptik.pro/action"
TIKTOK_URL = "https://www.tiktok.com/@zachking/video/6768504823336815877"


@pytest.fixture
def mock_http():
    with aioresponses() as m:
        yield m


async def test_happy_path(mock_http):
    mock_http.get(LANDING, body=load_fixture("snaptik_page.html"))
    mock_http.post(ACTION, body=load_fixture("snaptik_action.json"))

    answer = await SnaptikSessionStrategy().run(TIKTOK_URL)

    assert answer.result_type == ResultType.video_url
    assert len(answer.links) == 1
    assert answer.links[0].url.endswith("6768504823336815877_original.mp4")


async def test_page_without_token_returns_none(mock_http):
    mock_http.get(LANDING, body="<html><body>no token input here</body></html>")

    assert await SnaptikSessionStrategy().run(TIKTOK_URL) is None


async def test_error_true_returns_none(mock_http):
    mock_http.get(LANDING, body=load_fixture("snaptik_page.html"))
    mock_http.post(ACTION, body=json.dumps({"error": True, "html": ""}))

    assert await SnaptikSessionStrategy().run(TIKTOK_URL) is None


async def test_non_json_action_response_returns_none(mock_http):
    mock_http.get(LANDING, body=load_fixture("snaptik_page.html"))
    mock_http.post(ACTION, body="<html>rate limited</html>")

    assert await SnaptikSessionStrategy().run(TIKTOK_URL) is None


@pytest.mark.parametrize(
    "html",
    ["<div>no download button</div>", "", None],
    ids=["no-link", "empty", "missing"],
)
async def test_html_without_download_link_returns_none(mock_http, html):
    mock_http.get(LANDING, body=load_fixture("snaptik_page.html"))
    mock_http.post(ACTION, body=json.dumps({"error": False, "html": html}))

    assert await SnaptikSessionStrategy().run(TIKTOK_URL) is None
