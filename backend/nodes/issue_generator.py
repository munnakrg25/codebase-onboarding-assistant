import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv()


# This function turns the repo metadata into small contribution ideas for new contributors.
def generate_good_first_issues(
    metadata_path="indexes/metadata.json",
    output_path="outputs/good_first_issues.md",
):
    """Use the repository metadata to draft a short list of beginner-friendly issues.

    metadata_path: JSON metadata created during ingestion and embedding. output_path: Destination markdown file for the issue suggestions.
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

    if not metadata:
        raise ValueError("No repository chunks found.")

    file_paths = sorted({
        chunk["file_path"]
        for chunk in metadata
        if chunk.get("file_path")
    })

    file_list = "\n".join(f"- {path}" for path in file_paths)

    samples = []

    for chunk in metadata[:12]:
        samples.append(
            f"File: {chunk.get('file_path', 'Unknown')}\n"
            f"Lines: {chunk.get('start_line', '?')}-"
            f"{chunk.get('end_line', '?')}\n"
            f"Code:\n{chunk.get('text', '')[:500]}"
        )

    code_context = "\n\n".join(samples)

    prompt = f"""
You are an open-source maintainer helping a beginner contribute.

Suggest exactly 3 practical improvement tasks based on this repository.

For each task, use this format:

## 1. [Short issue title]
- **Why:** One sentence describing the improvement.
- **File:** An existing file from the list.
- **Steps:** Up to 3 short implementation steps.
- **Difficulty:** Easy, Medium, or Hard.
- **Done when:** One clear acceptance condition.
- **Test:** A relevant test to run, if identifiable.

Repository files:
{file_list}

Code samples:
{code_context}

Rules:
- Keep the complete report under 300 words.
- Use simple, clear English.
- Refer only to listed files.
- Base suggestions on available code.
- Do not invent confirmed bugs, functions, dependencies, or tests.
- Label uncertain findings as potential improvements.
- If no suitable test command is visible, say "Test command not confirmed".
- Output Markdown only. Do not create issues or modify files.
"""

    client = genai.Client(api_key=api_key)

    print(f"Generating contribution ideas with {model_name}...")

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

    print(f"Issue suggestions saved: {output_path}")
