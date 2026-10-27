# This test checks that empty search input is rejected before running the model.
import pytest

from backend.nodes.retrieve import search_code


def test_empty_query_is_rejected():
    with pytest.raises(
        ValueError,
        match="Search query cannot be empty",
    ):
        search_code(
            query="   ",
            index_path="indexes/faiss.index",
            metadata_path="indexes/metadata.json",
        )
