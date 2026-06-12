"""Phase 1: Threads pure parsing functions with synthetic data."""
import json

import pytest

from strategies.threads import _format_text, _parse_post, _parse_threads_url, _unroll


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.threads.net/t/Abc-123", ("Abc-123", None)),
        ("https://threads.com/t/Abc-123/", ("Abc-123", None)),
        ("https://www.threads.com/@my.user-name/post/Xyz_9", ("Xyz_9", "my.user-name")),
        ("  https://www.threads.net/@u/post/C1/  ", ("C1", "u")),
    ],
)
def test_parse_threads_url(url, expected):
    assert _parse_threads_url(url) == expected


def test_parse_threads_url_invalid():
    with pytest.raises(ValueError):
        _parse_threads_url("https://www.threads.net/@user")


# --- synthetic post builders -------------------------------------------------

def make_post(user="op", code="CODE", pk="1", taken_at=100, text="hi",
              images=None, carousel=None):
    post = {
        "pk": pk,
        "code": code,
        "taken_at": taken_at,
        "user": {"username": user},
        "caption": {"text": text} if text is not None else None,
    }
    if carousel is not None:
        post["carousel_media"] = [
            {"image_versions2": {"candidates": [{"url": u}, {"url": u + "_small"}]}}
            for u in carousel
        ]
    elif images is not None:
        post["image_versions2"] = {"candidates": [{"url": u} for u in images]}
    return {"post": post}


def make_html(*thread_item_arrays):
    blobs = [{"require": [{"data": {"thread_items": list(arr)}}]} for arr in thread_item_arrays]
    return "<html><body>" + "".join(
        f'<script type="application/json" data-content-len="1" data-sjs>'
        f"{json.dumps(b)}</script>"
        for b in blobs
    ) + "</body></html>"


# --- _parse_post --------------------------------------------------------------

def test_parse_post_single_image_takes_first_candidate():
    parsed = _parse_post(make_post(images=["full.jpg", "thumb.jpg"]))
    assert parsed["image_urls"] == ["full.jpg"]


def test_parse_post_carousel_takes_first_candidate_of_each():
    parsed = _parse_post(make_post(carousel=["a.jpg", "b.jpg", "c.jpg"]))
    assert parsed["image_urls"] == ["a.jpg", "b.jpg", "c.jpg"]


def test_parse_post_no_media_and_no_caption():
    parsed = _parse_post(make_post(text=None))
    assert parsed["text"] is None
    assert parsed["image_urls"] == []


def test_parse_post_empty_candidates():
    parsed = _parse_post(make_post(images=[]))
    assert parsed["image_urls"] == []


def test_parse_post_pk_falls_back_to_id():
    item = make_post()
    item["post"]["pk"] = None
    item["post"]["id"] = "fallback-id"
    assert _parse_post(item)["pk"] == "fallback-id"


@pytest.mark.parametrize("item", [None, "string", 42, {}, {"post": "not a dict"}])
def test_parse_post_garbage_returns_none(item):
    assert _parse_post(item) is None


# --- _unroll ------------------------------------------------------------------

def test_unroll_orders_by_taken_at_and_dedupes_by_pk():
    op_b = make_post(code="CB", pk="2", taken_at=200)
    op_c = make_post(code="CC", pk="3", taken_at=300)
    op_a = make_post(code="CA", pk="1", taken_at=100)
    html = make_html([op_b, op_c], [op_a], [op_b])  # op_b appears twice
    posts = _unroll(html, url_code="CB", username_hint=None)
    assert [p["code"] for p in posts] == ["CA", "CB", "CC"]


def test_unroll_excludes_reply_chains():
    op_main = make_post(user="op", code="X1", pk="1", taken_at=100)
    reply = make_post(user="rando", code="R1", pk="9", taken_at=200)
    op_after_reply = make_post(user="op", code="X2", pk="2", taken_at=300)
    op_second = make_post(user="op", code="X3", pk="3", taken_at=150)
    # arr 2 starts with a commenter: the whole array is a reply chain, so even
    # the OP post buried behind the reply must not be collected
    html = make_html([op_main], [reply, op_after_reply], [op_second])
    posts = _unroll(html, url_code="X1", username_hint="op")
    assert [p["code"] for p in posts] == ["X1", "X3"]


def test_unroll_resolves_username_from_url_code_without_hint():
    commenter = make_post(user="commenter", code="R1", pk="9", taken_at=50)
    target = make_post(user="alice", code="TARGET", pk="1", taken_at=10)
    follow_up = make_post(user="alice", code="T2", pk="2", taken_at=20)
    # the commenter's array comes first, so naive "first post wins" would fail
    html = make_html([commenter], [target, follow_up])
    posts = _unroll(html, url_code="TARGET", username_hint=None)
    assert [p["code"] for p in posts] == ["TARGET", "T2"]
    assert all(p["username"] == "alice" for p in posts)


def test_unroll_falls_back_to_first_post_when_code_not_found():
    post = make_post(user="bob", code="B1")
    html = make_html([post])
    posts = _unroll(html, url_code="UNKNOWN", username_hint=None)
    assert [p["code"] for p in posts] == ["B1"]


def test_unroll_empty_page():
    assert _unroll("<html><body>no data</body></html>", "X", None) == []


# --- _format_text ---------------------------------------------------------------

def test_format_text_single_post():
    posts = [{"username": "alice", "text": "hello world"}]
    url = "https://www.threads.net/t/C1"
    assert _format_text(posts, url) == (
        f"🧵 @alice on Threads — 1 post\n\nhello world\n\n{url}"
    )


def test_format_text_multi_post_numbers_parts_and_marks_empty():
    posts = [
        {"username": "alice", "text": "first"},
        {"username": "alice", "text": None},
    ]
    url = "https://www.threads.net/t/C1"
    text = _format_text(posts, url)
    assert text.startswith("🧵 @alice on Threads — 2 posts\n\n")
    assert "1/2\nfirst" in text
    assert "2/2\n(no text)" in text
    assert "\n\n———\n\n" in text
    assert text.endswith(f"\n\n{url}")
