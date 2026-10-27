import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv()


# This summary gives a beginner a quick picture of the project before they read the code deeply.
def generate_architecture_summary(
    metadata_path="indexes/metadata.json",
    output_path="outputs/architecture_summary.md",
    max_chunks=18,
):
    """Produce a short architecture overview from the repository metadata.

    metadata_path: JSON file created by the repository ingestion workflow. output_path: Markdown file to receive the generated summary. max_chunks: Maximum number of metadata chunks to include in the prompt context.
    """

    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY missing. Add it to your .env file."
        )

    metadata_path = Path(metadata_path)

    if not metadata_path.exists():
        raise FileNotFoundError(
            "Metadata not found. Run the embed command first."
        )

    with metadata_path.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    if not metadata:
        raise ValueError("No code chunks found.")

    # Give important project files higher priority.
    def file_priority(record):
        path = record["file_path"].lower()
        name = Path(path).name

        if name.startswith("readme"):
            return 0
        if name in ("main.py", "app.py", "__main__.py"):
            return 1
        if name in ("requirements.txt", "setup.py", "pyproject.toml"):
            return 2
        return 3

    selected_chunks = sorted(metadata, key=file_priority)[:max_chunks]

    # Prepare code context for Gemini.
    context = []
    for chunk in selected_chunks:
        context.append(
            f"File: {chunk['file_path']}\n"
            f"Lines: {chunk['start_line']}-{chunk['end_line']}\n"
            f"Code:\n{chunk['text'][:1200]}"
        )


    prompt = f"""
You are a senior developer explaining a repository to a beginner.

Create a SHORT architecture report in Markdown.

Use these 4 sections only:
## 1. Project Overview
Explain the project's purpose in 2-3 sentences.

## 2. Tech Stack
List the technologies and libraries confirmed by the provided files.

## 3. Key Files
List up to 6 important files and explain each in one short sentence.

## 4. How It Works
Explain the execution flow in 3-5 numbered steps.

Rules:
- Keep the entire report under 300 words.
- Use simple, clear English.
- Use only the provided code and file information.
- Do not invent files, features, APIs, or execution steps.
- If information is missing, clearly say "Not confirmed from provided code".
- Avoid repeated explanations and unnecessary introductions.

Repository files and code:

{"".join(item + chr(10) + chr(10) for item in context)}
"""


    client = genai.Client(api_key=api_key)

    print(f"Generating architecture summary with {model_name}...")

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )

    summary = response.text

    if not summary:
        raise RuntimeError("Gemini returned an empty response.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary, encoding="utf-8")

    print(f"Architecture summary saved: {output_path}")
