
import json
from pathlib import Path

import faiss
import numpy as np


# Save both the vector index and the matching metadata so every search hit can be mapped back to code lines.
def save_faiss_index(vectors, index_path, metadata, metadata_path):
    """Persist embeddings and their metadata for later similarity search.

    vectors: Embedding matrix produced by the sentence-transformers model. index_path: Output FAISS file. metadata: Chunk metadata aligned with each embedding. metadata_path: JSON file storing the metadata.
    """

    # FAISS expects vectors in float32 format.
    vectors = np.asarray(vectors, dtype="float32")

    if len(vectors) == 0:
        raise ValueError("No embeddings available to index.")

    # Our embeddings are normalized, so inner product gives cosine similarity.
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    index_path = Path(index_path)
    metadata_path = Path(metadata_path)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(index_path))

    with metadata_path.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2, ensure_ascii=False)

    print(f"FAISS index saved: {index_path}")
    print(f"Metadata saved: {metadata_path}")


# Rebuild the in-memory search index from disk whenever the app needs to answer a query.
def load_faiss_index(index_path, metadata_path):
    """Reload the saved FAISS index and the metadata list used to interpret search hits.

    index_path: Location of the serialized FAISS index. metadata_path: JSON file containing the associated chunk metadata.
    """

    index = faiss.read_index(str(index_path))

    with open(metadata_path, "r", encoding="utf-8") as file:
        metadata = json.load(file)

    if index.ntotal != len(metadata):
        raise ValueError("Index and metadata sizes do not match.")

    return index, metadata
