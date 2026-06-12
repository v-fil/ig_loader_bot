"""Phase 3: InstaloaderStrategy with instaloader.Post.from_shortcode monkeypatched."""
import logging

import instaloader
import pytest

from strategies.ig import InstaloaderStrategy
from strategies.types import FileType, ResultType

POST_URL = "https://www.instagram.com/p/C0dE/"


class StubNode:
    def __init__(self, is_video=False, video_url=None, display_url=None):
        self.is_video = is_video
        self.video_url = video_url
        self.display_url = display_url


class StubPost:
    def __init__(self, shortcode="C0dE", typename="GraphVideo", is_video=False,
                 video_url=None, url=None, nodes=()):
        self.shortcode = shortcode
        self.typename = typename
        self.is_video = is_video
        self.video_url = video_url
        self.url = url
        self._nodes = nodes

    def get_sidecar_nodes(self):
        return iter(self._nodes)


@pytest.fixture
def install_post(monkeypatch, tmp_path):
    """Patch from_shortcode to return a stub (or raise); record shortcodes passed."""
    # point SESSION_FILE away from the repo so no real session is loaded
    monkeypatch.setattr("strategies.ig.SESSION_FILE", str(tmp_path / "missing.session"))
    shortcodes = []

    def install(post_or_exc):
        def from_shortcode(context, shortcode):
            shortcodes.append(shortcode)
            if isinstance(post_or_exc, Exception):
                raise post_or_exc
            return post_or_exc

        monkeypatch.setattr(instaloader.Post, "from_shortcode", from_shortcode)
        return shortcodes

    return install


async def test_video_with_cdn_host_rewrite(install_post):
    shortcodes = install_post(StubPost(
        is_video=True,
        video_url="https://scontent-waw2-1.cdninstagram.com/o1/v/t16/f2/clip.mp4?efg=abc&_nc_ht=x",
    ))

    answer = await InstaloaderStrategy().run(POST_URL)

    assert answer.result_type == ResultType.video_url
    assert answer.links[0].url == "https://scontent.cdninstagram.com/v/t16/f2/clip.mp4?efg=abc&_nc_ht=x"
    assert answer.links[0].filetype == FileType.video
    assert answer.links[0].filename == "C0dE.mp4"
    # the IG: prefix from extract_id must be stripped before hitting instaloader
    assert shortcodes == ["C0dE"]


async def test_video_url_without_v_segment_kept_as_is(install_post):
    install_post(StubPost(is_video=True, video_url="https://cdn.example/plain.mp4"))

    answer = await InstaloaderStrategy().run(POST_URL)

    assert answer.links[0].url == "https://cdn.example/plain.mp4"


async def test_video_without_video_url_returns_none(install_post, caplog):
    install_post(StubPost(is_video=True, video_url=None))

    with caplog.at_level(logging.INFO):
        assert await InstaloaderStrategy().run(POST_URL) is None

    assert "has no video_url" in caplog.text


async def test_sidecar_mixed_items(install_post):
    install_post(StubPost(typename="GraphSidecar", nodes=(
        StubNode(display_url="https://cdn.example/a.jpg"),
        StubNode(is_video=True, video_url="https://cdn.example/b.mp4"),
    )))

    answer = await InstaloaderStrategy().run(POST_URL)

    assert answer.result_type == ResultType.items_list
    assert [(link.url, link.filetype, link.filename) for link in answer.links] == [
        ("https://cdn.example/a.jpg", FileType.img, "C0dE_0.jpg"),
        ("https://cdn.example/b.mp4", FileType.video, "C0dE_1.mp4"),
    ]


async def test_single_image_answers_with_url(install_post):
    install_post(StubPost(typename="GraphImage", url="https://cdn.example/photo.jpg"))

    answer = await InstaloaderStrategy().run(POST_URL)

    assert answer.result_type == ResultType.url
    assert answer.links[0].url == "https://cdn.example/photo.jpg"
    assert answer.links[0].filetype == FileType.img


async def test_unknown_typename_returns_none(install_post, caplog):
    install_post(StubPost(typename="GraphStory"))

    with caplog.at_level(logging.INFO):
        assert await InstaloaderStrategy().run(POST_URL) is None

    assert "unhandled post type 'GraphStory'" in caplog.text


async def test_instaloader_exception_returns_none(install_post, caplog):
    install_post(instaloader.InstaloaderException("Fetching Post metadata failed"))

    with caplog.at_level(logging.ERROR):
        assert await InstaloaderStrategy().run(POST_URL) is None

    assert "InstaloaderException" in caplog.text
