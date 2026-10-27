import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv()


# Suggest a safe patch idea without touching the actual source code.
def suggest_patch(
    file_path,
    metadata_path="indexes/metadata.json",
    output_path="outputs/suggested_patch.md",
):
    """Generate a review-style patch recommendation for one file without modifying source files.

    file_path: Repository-relative file path to review. metadata_path: Metadata file used to find the selected file's code chunks. output_path: Markdown file for the patch suggestion.
    """

    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        raise ValueError("GEMINI_API_KEY missing from .env")

    metadata_path = Path(metadata_path)

    if not metadata_path.exists():
        raise FileNotFoundError(
            "Metadata not found. Run the embed command first."
        )

    with metadata_path.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    normalized_path = file_path.replace("\\", "/")

    selected_chunks = [
        chunk for chunk in metadata
        if chunk.get("file_path", "").replace("\\", "/")
        == normalized_path
    ]

    if not selected_chunks:
        raise ValueError(
            f"No indexed code found for file: {file_path}"
        )

    def get_start_line(chunk):
        if "meta" in chunk:
            return chunk["meta"]["start_line"]
        return chunk["start_line"]

    selected_chunks.sort(key=get_start_line)

    code_parts = []

    for chunk in selected_chunks[:10]:
        start = chunk.get("start_line")
        end = chunk.get("end_line")

        if "meta" in chunk:
            start = chunk["meta"].get("start_line", start)
            end = chunk["meta"].get("end_line", end)

        code_parts.append(
            f"Lines {start}-{end}:\n{chunk['text'][:1500]}"
        )

    code_context = "\n\n".join(code_parts)

    prompt = f"""
You are helping a beginner improve an existing repository.

File: {file_path}

Code:
{code_context}

Suggest ONE small, useful improvement.

Use only these sections:

## Improvement
Explain the change in 1-2 sentences.

## Proposed Patch
Provide a unified diff in a fenced diff code block.

## Test
Give a relevant test command if confirmed by the provided code.
Otherwise say "Test command not confirmed".

## Limitation
Mention any important uncertainty in one sentence.

Rules:
- Keep the report under 200 words, excluding the diff.
- Modify only {file_path}.
- Use exact existing code context; do not invent surrounding lines.
- Make the diff syntactically consistent with the proposed change.
- If there is insufficient context, explain why instead of guessing.
- Never claim tests passed.
- Do not apply the patch or modify source files.
- Output Markdown only.
"""

    client = genai.Client(api_key=api_key)

    print(f"Generating a patch suggestion for {file_path}...")

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )

    result = response.text

    if not result:
        raise RuntimeError("Gemini returned an empty response.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8")

    print(f"Patch suggestion saved: {output_path}")
