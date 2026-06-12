"""Phase 3: FastDLSessionStrategy with mocked HTTP.

The dukpy step runs real JS — the fixture test executes the actual obfuscated
payload captured from fastdown.to (the most fragile part of the strategy).
"""
import json

import pytest
from aioresponses import aioresponses

from strategies.ig import FastDLSessionStrategy
from strategies.types import FileType, ResultType
from tests.conftest import load_fixture

LANDING = "https://fastdown.to/en"
AJAX = "https://fastdown.to/api/ajaxSearch"
# synthetic: only ever sent to the mocked ajaxSearch endpoint, never fetched
POST_URL = "https://www.instagram.com/p/Cabc123xyz-/"

# The captured payload only writes its result while (+new Date())/1000 is below
# an expiry timestamp embedded at capture time (a few hours of validity).
# Freeze Date at the capture date so the fixture decodes forever; the shim is
# prepended to the payload, which the strategy evals inside a function scope,
# so only the fixture's JS sees it. Any re-captured payload expires later than
# this, so the constant never needs updating along with the fixture.
FROZEN_NOW_MS = 1_781_222_400_000  # 2026-06-12T00:00Z, the fixture capture date
DATE_SHIM = (
    f"var Date = function() {{ return {{ valueOf: function() {{ return {FROZEN_NOW_MS}; }} }}; }};"
)


@pytest.fixture
def mock_http():
    with aioresponses() as m:
        yield m


def js_payload(inner_html: str) -> dict:
    """ajaxSearch response whose JS payload writes inner_html into the page."""
    code = f'document.getElementById("search-result").innerHTML = {json.dumps(inner_html)};'
    return {"status": "ok", "data": code}


async def test_fixture_decodes_to_single_image(mock_http):
    payload = json.loads(load_fixture("fastdl_ajax_search.json"))
    payload["data"] = DATE_SHIM + payload["data"]
    mock_http.get(LANDING, status=200)
    mock_http.post(AJAX, payload=payload)

    answer = await FastDLSessionStrategy().run(POST_URL)

    assert answer.result_type == ResultType.url
    assert len(answer.links) == 1
    assert answer.links[0].filetype == FileType.img
    assert answer.links[0].url.startswith("https://dl.snapcdn.app/get?token=")


async def test_single_video_payload(mock_http):
    mock_http.get(LANDING, status=200)
    mock_http.post(AJAX, payload=js_payload(
        '<div class="download-items">'
        '<a href="https://dl.snapcdn.app/get?token=vid" rel="nofollow" title="Download Video">Download Video</a>'
        '</div>'
    ))

    answer = await FastDLSessionStrategy().run(POST_URL)

    assert answer.result_type == ResultType.video_url
    assert len(answer.links) == 1
    assert answer.links[0].filetype == FileType.video
    assert answer.links[0].url == "https://dl.snapcdn.app/get?token=vid"


async def test_carousel_payload_mixed_items(mock_http):
    mock_http.get(LANDING, status=200)
    mock_http.post(AJAX, payload=js_payload(
        '<ul>'
        '<li><span class="icon icon-dlimage"></span>'
        '<select><option value="https://dl.snapcdn.app/get?token=img1">Download Image</option></select></li>'
        '<li><span class="icon icon-dlvideo"></span>'
        '<select><option value="https://dl.snapcdn.app/get?token=vid1">Download Video</option></select></li>'
        '</ul>'
    ))

    answer = await FastDLSessionStrategy().run(POST_URL)

    assert answer.result_type == ResultType.items_list
    assert [(link.url, link.filetype) for link in answer.links] == [
        ("https://dl.snapcdn.app/get?token=img1", FileType.img),
        ("https://dl.snapcdn.app/get?token=vid1", FileType.video),
    ]


async def test_landing_non_200_returns_none(mock_http):
    mock_http.get(LANDING, status=503)

    assert await FastDLSessionStrategy().run(POST_URL) is None


async def test_ajax_non_200_returns_none(mock_http):
    mock_http.get(LANDING, status=200)
    mock_http.post(AJAX, status=500, body="server error")

    assert await FastDLSessionStrategy().run(POST_URL) is None


async def test_ajax_non_json_returns_none(mock_http):
    mock_http.get(LANDING, status=200)
    mock_http.post(AJAX, status=200, body="<html>captcha</html>")

    assert await FastDLSessionStrategy().run(POST_URL) is None


@pytest.mark.parametrize("payload", [{"status": "ok"}, ["not", "a", "dict"]])
async def test_ajax_json_without_data_returns_none(mock_http, payload):
    mock_http.get(LANDING, status=200)
    mock_http.post(AJAX, payload=payload)

    assert await FastDLSessionStrategy().run(POST_URL) is None


async def test_payload_without_download_links_returns_none(mock_http):
    mock_http.get(LANDING, status=200)
    mock_http.post(AJAX, payload=js_payload("<p>nothing to download here</p>"))

    assert await FastDLSessionStrategy().run(POST_URL) is None
