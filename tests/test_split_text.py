"""Phase 1: utils._split_text chunking behavior."""
import pytest

from strategies.utils import _split_text


def test_short_text_passes_through():
    assert _split_text("hello", 100) == ["hello"]


def test_exact_limit_single_chunk():
    assert _split_text("a" * 100, 100) == ["a" * 100]


def test_prefers_paragraph_break_over_newline():
    text = "A" * 20 + "\n" + "B" * 10 + "\n\n" + "C" * 40
    assert _split_text(text, 50) == ["A" * 20 + "\n" + "B" * 10, "C" * 40]


def test_prefers_newline_over_space():
    text = "A" * 20 + " " + "B" * 10 + "\n" + "C" * 40
    assert _split_text(text, 50) == ["A" * 20 + " " + "B" * 10, "C" * 40]


def test_splits_on_space():
    text = "A" * 30 + " " + "B" * 40
    assert _split_text(text, 50) == ["A" * 30, "B" * 40]


def test_hard_cut_when_separator_before_third_of_limit():
    # the only space sits before limit // 3, so the cut is mid-word at the limit
    text = "AB " + "C" * 40
    assert _split_text(text, 30) == [text[:30], text[30:]]


LONG_TEXT = (
    "\n\n".join(
        " ".join(f"word{i}" for i in range(30)) + "\nsecond line of paragraph"
        for _ in range(3)
    )
    + "\n\n"
    + "X" * 150  # unbroken run to force hard cuts
)


@pytest.mark.parametrize("limit", [40, 100, 4096])
def test_no_chunk_exceeds_limit(limit):
    chunks = _split_text(LONG_TEXT, limit)
    assert all(len(c) <= limit for c in chunks)


@pytest.mark.parametrize("limit", [40, 100, 4096])
def test_rejoined_text_loses_only_whitespace(limit):
    chunks = _split_text(LONG_TEXT, limit)
    assert "".join("".join(chunks).split()) == "".join(LONG_TEXT.split())
