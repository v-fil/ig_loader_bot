"""Phase 3: ThreadsStrategy end-to-end with mocked HTTP (parsing units are Phase 1)."""
import json

import pytest
from aioresponses import aioresponses

from strategies.threads import ThreadsStrategy
from strategies.types import FileType, ResultType
from tests.conftest import load_fixture

POST_URL = "https://www.threads.com/@zuck/post/DPCXhCwkqEe"


@pytest.fixture
def mock_http():
    with aioresponses() as m:
        yield m


def synthetic_page(*thread_items: dict) -> str:
    blob = json.dumps({"data": {"thread_items": list(thread_items)}})
    return f'<html><body><script type="application/json" data-sjs>{blob}</script></body></html>'


async def test_fixture_unrolls_to_text_and_images(mock_http):
    mock_http.get(POST_URL, body=load_fixture("threads_post.html"))

    answer = await ThreadsStrategy().run(POST_URL)

    assert answer.result_type == ResultType.items_list
    # 3-post OP chain with 5 carousel images, all on the second post
    assert len(answer.links) == 5
    assert all(link.filetype == FileType.img for link in answer.links)
    assert [link.filename for link in answer.links] == [
        f"threads_DPCXlwWEtwE_{i}.jpg" for i in range(5)
    ]
    assert answer.text.startswith("🧵 @zuck on Threads — 3 posts")
    assert "1/3" in answer.text and "3/3" in answer.text
    assert "Introducing Vibes" in answer.text
    assert answer.text.endswith(POST_URL)


async def test_text_only_post(mock_http):
    url = "https://www.threads.com/@zuck/post/ABC"
    mock_http.get(url, body=synthetic_page(
        {"post": {"pk": "1", "code": "ABC", "user": {"username": "zuck"},
                  "taken_at": 100, "caption": {"text": "hello world"}}},
    ))

    answer = await ThreadsStrategy().run(url)

    assert answer.result_type == ResultType.text
    assert answer.links == []
    assert "hello world" in answer.text


async def test_js_shell_page_returns_none(mock_http):
    mock_http.get(POST_URL, body='<html><head></head><body><div id="root"></div></body></html>')

    assert await ThreadsStrategy().run(POST_URL) is None


async def test_non_200_returns_none(mock_http):
    mock_http.get(POST_URL, status=404)

    assert await ThreadsStrategy().run(POST_URL) is None


async def test_op_not_leading_fixture_returns_none(mock_http):
    # pins current behavior: when the OP never leads a thread_items array
    # (appears mid-array after a quoting reply), _unroll yields nothing —
    # flip this test if _unroll learns that shape (see fixtures/README.md)
    url = "https://www.threads.com/@zuck/post/DTTnkzwkdSx"
    mock_http.get(url, body=load_fixture("threads_post_op_not_leading.html"))

    assert await ThreadsStrategy().run(url) is None


async def test_non_threads_url_returns_none(mock_http):
    # no mock registered: the strategy must bail before any HTTP request
    assert await ThreadsStrategy().run("https://example.com/post/123") is None
