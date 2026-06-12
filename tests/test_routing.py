"""Phase 1: get_provider_by_url routes each provider's URLs correctly."""
import pytest

from strategies.base import get_provider_by_url


@pytest.mark.parametrize(
    "url, provider",
    [
        ("https://www.instagram.com/p/ABC/", "instagram"),
        ("https://www.instagram.com/reel/ABC/", "instagram"),
        # regression: the /reels/ share format was not routed at all
        ("https://www.instagram.com/reels/ABC/", "instagram"),
        ("https://www.instagram.com/share/reel/ABC", "instagram"),
        ("https://instagram.com/p/ABC/", "instagram"),
        ("https://www.tiktok.com/@user/video/123", "tiktok"),
        ("https://vt.tiktok.com/ZSabc/", "tiktok"),
        ("https://x.com/user/status/123", "twitter"),
        # regression: twitter.com was dropped from the filter at one point
        ("https://twitter.com/user/status/123", "twitter"),
        ("https://www.youtube.com/shorts/abc", "youtube"),
        ("https://youtube.com/shorts/abc", "youtube"),
        ("https://www.threads.net/t/Code123", "threads"),
        ("https://threads.com/t/Code123", "threads"),
        ("https://www.threads.com/@user.name/post/Code-123?x=1", "threads"),
    ],
)
def test_routes_to_provider(url, provider):
    assert get_provider_by_url(url) == provider


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/video/123",
        # regression: unescaped dot in the twitter regex matched any character
        "https://xXcom/user/status/123",
        "https://www.instagram.com/stories/user/123/",
        "http://www.instagram.com/p/ABC/",
        "https://instagram.com.evil.example/p/ABC/",
        "https://www.threads.net/@user",
        "not a url",
    ],
)
def test_unknown_url_returns_none(url):
    assert get_provider_by_url(url) is None
