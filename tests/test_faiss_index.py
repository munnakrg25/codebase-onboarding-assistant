# These checks make sure the FAISS index saves and reloads the metadata correctly.
import numpy as np
import pytest

from backend.utils.faiss_index import (
    save_faiss_index,
    load_faiss_index,
)


def test_save_and_load_index(tmp_path):
    index_path = tmp_path / "test.index"
    metadata_path = tmp_path / "metadata.json"

    vectors = np.array(
        [
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        dtype="float32",
    )

    metadata = [
        {"file_path": "main.py", "text": "First chunk"},
        {"file_path": "utils.py", "text": "Second chunk"},
    ]

    save_faiss_index(
        vectors,
        index_path,
        metadata,
        metadata_path,
    )

    index, loaded_metadata = load_faiss_index(
        index_path,
        metadata_path,
    )

    assert index.ntotal == 2
    assert len(loaded_metadata) == 2
    assert loaded_metadata[0]["file_path"] == "main.py"


def test_empty_vectors_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="No embeddings"):
        save_faiss_index(
            np.empty((0, 3), dtype="float32"),
            tmp_path / "empty.index",
            [],
            tmp_path / "metadata.json",
        )
