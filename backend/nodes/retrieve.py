from sentence_transformers import SentenceTransformer

from backend.nodes.embed import MODEL_NAME
from backend.utils.faiss_index import load_faiss_index


# Search the saved index with a text query to find the most relevant repo chunks.
def search_code(query, index_path, metadata_path, top_k=3):
    """Find the most relevant indexed chunks for a natural-language code query.

    query: User-facing text describing the code to find. index_path: Saved FAISS database path. metadata_path: Metadata file aligned with the index. top_k: Maximum number of hits to return.
    """

    if not query.strip():
        raise ValueError("Search query cannot be empty.")

    index, metadata = load_faiss_index(index_path, metadata_path)

    # Use the same model that created the saved embeddings.
    model = SentenceTransformer(MODEL_NAME)

    query_vector = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    # Do not request more results than the index contains.
    top_k = max(1, min(top_k, index.ntotal))

    scores, positions = index.search(query_vector, top_k)

    results = []

    for score, position in zip(scores[0], positions[0]):
        if position < 0:
            continue

        result = metadata[int(position)].copy()
        result["score"] = float(score)
        results.append(result)

    return results
