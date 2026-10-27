
# Break large files into smaller windows so code search can keep context without losing track of the file.
def split_into_chunks(text, chunk_size=80, overlap=10):
    """Break a file into smaller text windows with a small overlap for context.

    text: Full file content being split into searchable chunks. chunk_size: Maximum number of lines per chunk. overlap: Number of previous lines to repeat in the next chunk.
    """

    lines = text.splitlines()
    chunks = []
    start = 0

    while start < len(lines):
        end = min(start + chunk_size, len(lines))

        chunk_text = "\n".join(lines[start:end])

        chunks.append({
            "text": chunk_text,
            "start_line": start + 1,
            "end_line": end
        })

        # Move forward, keeping some lines from the previous chunk.
        if end == len(lines):
            break

        start = end - overlap

    return chunks
