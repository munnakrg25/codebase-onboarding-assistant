import json
from pathlib import Path

from sentence_transformers import SentenceTransformer

from backend.utils.faiss_index import save_faiss_index


# A small model suitable for our first semantic search implementation.
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


# Convert each code chunk into an embedding so the app can do semantic code search later.
def build_embeddings(chunks_file, index_path, metadata_path):
    """Convert ingested code chunks into embeddings and save the FAISS search index.

    chunks_file: JSONL file produced by the ingestion phase. index_path: Output FAISS database path. metadata_path: JSON file containing chunk metadata for each vector.
    """

    chunks_file = Path(chunks_file)

    if not chunks_file.exists():
        raise FileNotFoundError(f"Chunks file not found: {chunks_file}")

    records = []

    # Each line in JSONL contains one chunk and its metadata.
    with chunks_file.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                records.append(json.loads(line))

    if not records:
        raise ValueError("No chunks found. Run Phase 1 ingestion first.")

    # Include the filename so searches can use file-level context too.
    texts = [
        f"File: {record['meta']['file_path']}\n{record['text']}"
        for record in records
    ]

    print(f"Loading embedding model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    print(f"Creating embeddings for {len(texts)} chunks...")

    # Normalization allows us to use inner product as cosine similarity.
    vectors = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    metadata = []

    for record in records:
        metadata.append({
            "file_path": record["meta"]["file_path"],
            "chunk_index": record["meta"]["chunk_index"],
            "start_line": record["meta"]["start_line"],
            "end_line": record["meta"]["end_line"],
            "extension": record["meta"]["extension"],
            "text": record["text"]
        })

    save_faiss_index(
        vectors,
        index_path,
        metadata,
        metadata_path
    )

    print("Embedding and indexing completed!")
