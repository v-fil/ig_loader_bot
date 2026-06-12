"""Phase 2: Registry.run orchestration with stub strategies and mocked helpers."""
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import strategies.base as base
from strategies.base import AbstractStrategy, Registry, RegistryItem
from strategies.types import FileType, Provider, ResultType
from strategies.utils import Answer, Link, UploadError

URL = "https://www.instagram.com/p/ABC/"
PROVIDER = Provider.instagram


class StubStrategy(AbstractStrategy):
    """Returns a preset Answer and records the URLs it was called with."""

    def __init__(self, result: Answer | None = None):
        self.result = result
        self.calls: list[str] = []

    async def run(self, url: str) -> Answer | None:
        self.calls.append(url)
        return self.result


def video_answer(url: str = "https://cdn.example/video.mp4") -> Answer:
    return Answer(links=[Link(url=url, file_type=FileType.video)], result_type=ResultType.video_url)


def url_answer(url: str = "https://cdn.example/photo.jpg") -> Answer:
    return Answer(links=[Link(url=url, file_type=FileType.img)], result_type=ResultType.url)


def album_answer(url: str = "https://cdn.example/item1.jpg") -> Answer:
    return Answer(links=[Link(url=url, file_type=FileType.img)], result_type=ResultType.items_list)


def text_answer(text: str = "post text") -> Answer:
    return Answer(result_type=ResultType.text, text=text)


def make_registry(*strategies: AbstractStrategy, extract_id=None, preprocess_url=None) -> Registry:
    item = RegistryItem(
        strategies=list(strategies),
        extract_id=extract_id or (lambda url: "id123"),
        preprocess_url=preprocess_url,
    )
    return Registry({PROVIDER: item})


@pytest.fixture
def message():
    return AsyncMock()


@pytest.fixture(autouse=True)
def helpers(monkeypatch):
    # autouse so no test can accidentally hit the real upload/answer helpers
    mocks = SimpleNamespace(
        upload_video=AsyncMock(return_value=True),
        answer_with_url=AsyncMock(),
        answer_with_album=AsyncMock(),
        answer_with_text=AsyncMock(),
    )
    for name in ("upload_video", "answer_with_url", "answer_with_album", "answer_with_text"):
        monkeypatch.setattr(base, name, getattr(mocks, name))
    return mocks


async def test_none_result_tries_next_strategy(helpers, message):
    first = StubStrategy(None)
    second = StubStrategy(url_answer("https://cdn.example/2.jpg"))
    registry = make_registry(first, second)

    await registry.run(PROVIDER, message, URL)

    assert first.calls == [URL]
    assert second.calls == [URL]
    helpers.answer_with_url.assert_awaited_once_with("https://cdn.example/2.jpg", message)


async def test_video_upload_success_stops(helpers, message):
    first = StubStrategy(video_answer("https://cdn.example/v.mp4"))
    second = StubStrategy(url_answer())
    registry = make_registry(first, second)

    await registry.run(PROVIDER, message, URL)

    helpers.upload_video.assert_awaited_once_with("https://cdn.example/v.mp4", message)
    assert second.calls == []
    helpers.answer_with_url.assert_not_awaited()


async def test_video_upload_false_tries_next_strategy(helpers, message):
    helpers.upload_video.return_value = False
    first = StubStrategy(video_answer())
    second = StubStrategy(url_answer("https://cdn.example/2.jpg"))
    registry = make_registry(first, second)

    await registry.run(PROVIDER, message, URL)

    assert second.calls == [URL]
    helpers.answer_with_url.assert_awaited_once_with("https://cdn.example/2.jpg", message)


async def test_video_upload_raises_falls_back_to_url_and_stops(helpers, message):
    helpers.upload_video.side_effect = RuntimeError("boom")
    first = StubStrategy(video_answer("https://cdn.example/v.mp4"))
    second = StubStrategy(url_answer())
    registry = make_registry(first, second)

    await registry.run(PROVIDER, message, URL)

    helpers.answer_with_url.assert_awaited_once_with("https://cdn.example/v.mp4", message)
    assert second.calls == []


async def test_album_success_stops(helpers, message):
    answer = album_answer()
    first = StubStrategy(answer)
    second = StubStrategy(url_answer())
    registry = make_registry(first, second)

    await registry.run(PROVIDER, message, URL)

    helpers.answer_with_album.assert_awaited_once_with(answer, message)
    assert second.calls == []
    helpers.answer_with_url.assert_not_awaited()


async def test_album_upload_error_tries_next_strategy(helpers, message):
    helpers.answer_with_album.side_effect = UploadError
    first = StubStrategy(album_answer())
    second = StubStrategy(url_answer("https://cdn.example/2.jpg"))
    registry = make_registry(first, second)

    await registry.run(PROVIDER, message, URL)

    assert second.calls == [URL]
    helpers.answer_with_url.assert_awaited_once_with("https://cdn.example/2.jpg", message)


async def test_url_result_answers_with_url(helpers, message):
    registry = make_registry(StubStrategy(url_answer("https://cdn.example/p.jpg")))

    await registry.run(PROVIDER, message, URL)

    helpers.answer_with_url.assert_awaited_once_with("https://cdn.example/p.jpg", message)
    helpers.upload_video.assert_not_awaited()


async def test_text_result_answers_with_text(helpers, message):
    answer = text_answer("hello")
    registry = make_registry(StubStrategy(answer))

    await registry.run(PROVIDER, message, URL)

    helpers.answer_with_text.assert_awaited_once_with(answer, message)
    helpers.answer_with_url.assert_not_awaited()


async def test_trailing_fallback_after_video_upload_false(helpers, message):
    helpers.upload_video.return_value = False
    registry = make_registry(StubStrategy(video_answer("https://cdn.example/v.mp4")))

    await registry.run(PROVIDER, message, URL)

    helpers.answer_with_url.assert_awaited_once_with("https://cdn.example/v.mp4", message)


async def test_trailing_fallback_after_album_upload_error(helpers, message):
    helpers.answer_with_album.side_effect = UploadError
    registry = make_registry(StubStrategy(album_answer("https://cdn.example/a.jpg")))

    await registry.run(PROVIDER, message, URL)

    helpers.answer_with_url.assert_awaited_once_with("https://cdn.example/a.jpg", message)


async def test_no_fallback_when_no_strategy_produced_result(helpers, message):
    registry = make_registry(StubStrategy(None), StubStrategy(None))

    await registry.run(PROVIDER, message, URL)

    helpers.answer_with_url.assert_not_awaited()


async def test_no_fallback_when_last_strategy_returns_none(helpers, message):
    # pins current behavior: an earlier strategy's result is forgotten once a
    # later strategy returns None, so no trailing fallback fires
    helpers.upload_video.return_value = False
    first = StubStrategy(video_answer())
    second = StubStrategy(None)
    registry = make_registry(first, second)

    await registry.run(PROVIDER, message, URL)

    helpers.answer_with_url.assert_not_awaited()


@pytest.mark.parametrize("exc", [ValueError, AttributeError])
async def test_extract_id_failure_falls_back_to_url(helpers, message, caplog, exc):
    def extract_id(url):
        raise exc("bad url")

    strategy = StubStrategy(url_answer())
    registry = make_registry(strategy, extract_id=extract_id)

    with caplog.at_level(logging.INFO):
        await registry.run(PROVIDER, message, URL)

    assert strategy.calls == [URL]
    assert f"[{PROVIDER}] got url '{URL}', could not extract id" in caplog.text
    # the URL itself is used as the id in subsequent log lines
    assert f"[{URL}] Running with StubStrategy" in caplog.text


async def test_preprocess_url_awaited_and_result_passed_to_strategies(helpers, message):
    preprocess = AsyncMock(return_value="https://final.example/post")
    strategy = StubStrategy(url_answer())
    registry = make_registry(strategy, preprocess_url=preprocess)

    await registry.run(PROVIDER, message, URL)

    preprocess.assert_awaited_once_with(URL)
    assert strategy.calls == ["https://final.example/post"]


async def test_no_preprocess_passes_original_url(helpers, message):
    strategy = StubStrategy(url_answer())
    registry = make_registry(strategy)

    await registry.run(PROVIDER, message, URL)

    assert strategy.calls == [URL]
