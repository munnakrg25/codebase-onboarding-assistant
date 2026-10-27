# These tests confirm the chunking logic keeps line ranges predictable.
from backend.utils.chunker import split_into_chunks


def test_split_into_chunks():
    text = "line1\nline2\nline3\nline4\nline5"

    chunks = split_into_chunks(
        text,
        chunk_size=3,
        overlap=1,
    )

    assert len(chunks) == 2
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 3
    assert chunks[1]["start_line"] == 3
    assert chunks[1]["end_line"] == 5


def test_empty_text():
    chunks = split_into_chunks("")

    assert chunks == []
