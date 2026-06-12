"""Phase 1: extract_id for every provider (pure functions, no network)."""
import pytest

from strategies import ig, threads, tiktok, x, yt


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.instagram.com/p/Bxyz_R3kAb-/", "IG:Bxyz_R3kAb-"),
        ("https://www.instagram.com/reel/Cabc123/", "IG:Cabc123"),
        # regression: the /reels/ share format raised ValueError
        ("https://www.instagram.com/reels/DPsO-jwjMJm/", "IG:DPsO-jwjMJm"),
        ("https://www.instagram.com/share/r9pXyzAb/", "IG:r9pXyzAb"),
        ("https://instagram.com/p/Cabc123/", "IG:Cabc123"),
        ("https://www.instagram.com/p/Cabc123", "IG:Cabc123"),
        ("https://www.instagram.com/p/Cabc123/?igsh=token", "IG:Cabc123"),
        ("look at this https://www.instagram.com/p/Cabc123/ 😂", "IG:Cabc123"),
    ],
)
def test_ig(url, expected):
    assert ig.extract_id(url) == expected


@pytest.mark.parametrize("code", ["IGabc", "Iabc", "Gabc", "GIGIcode"])
def test_ig_shortcode_survives_removeprefix_roundtrip(code):
    # Regression: lstrip("IG:") used to eat leading I/G/: chars of the
    # shortcode itself; InstaloaderStrategy relies on this round-trip.
    _id = ig.extract_id(f"https://www.instagram.com/p/{code}/")
    assert _id.removeprefix("IG:") == code


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.tiktok.com/@zachking/video/6768504823336815877",
         "TIKTOK:6768504823336815877"),
        ("https://www.tiktok.com/@user.name/video/123?is_from_webapp=1", "TIKTOK:123"),
        ("https://vt.tiktok.com/ZSabc123/", "TIKTOK:ZSabc123"),
        ("https://vm.tiktok.com/XYZ987/", "TIKTOK:XYZ987"),
        ("watch https://vt.tiktok.com/ZSabc123/ now", "TIKTOK:ZSabc123"),
    ],
)
def test_tiktok(url, expected):
    assert tiktok.extract_id(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://x.com/user/status/1234567890", "X:1234567890"),
        ("https://twitter.com/user/status/1234567890", "X:1234567890"),
        ("https://x.com/user/status/123?s=20&t=abc", "X:123"),
        ("lol https://x.com/user/status/123/photo/1", "X:123"),
    ],
)
def test_x(url, expected):
    assert x.extract_id(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "YTShorts:dQw4w9WgXcQ"),
        ("https://youtube.com/shorts/abc123", "YTShorts:abc123"),
    ],
)
def test_yt(url, expected):
    assert yt.extract_id(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.threads.net/t/CuXFPIeLLod", "Threads:CuXFPIeLLod"),
        ("https://www.threads.com/t/CuXFPIeLLod/", "Threads:CuXFPIeLLod"),
        ("https://www.threads.com/@zuck/post/DPCXhCwkqEe", "Threads:DPCXhCwkqEe"),
        ("https://threads.net/@some.user-name/post/AB_c-12/", "Threads:AB_c-12"),
        ("https://www.threads.com/t/XyZ-123?igshid=1", "Threads:XyZ-123"),
    ],
)
def test_threads(url, expected):
    assert threads.extract_id(url) == expected


@pytest.mark.parametrize(
    "extract_id",
    [ig.extract_id, tiktok.extract_id, x.extract_id, yt.extract_id, threads.extract_id],
    ids=["ig", "tiktok", "x", "yt", "threads"],
)
@pytest.mark.parametrize("text", ["", "no url here", "https://example.com/p/123"])
def test_invalid_input_raises(extract_id, text):
    with pytest.raises(ValueError):
        extract_id(text)
