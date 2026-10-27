import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv()


# The reading guide helps new contributors know which files matter first.
def generate_reading_guide(
    metadata_path="indexes/metadata.json",
    output_path="outputs/reading_guide.md",
):
    """Create a concise developer-oriented guide to the repository's most important files.

    metadata_path: JSON metadata file with repository chunks. output_path: Path for the generated reading-guide markdown.
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

    files = sorted({
        chunk["file_path"]
        for chunk in metadata
        if chunk.get("file_path")
    })

    file_list = "\n".join(f"- {path}" for path in files)

    code_samples = []

    for chunk in metadata[:10]:
        code_samples.append(
            f"File: {chunk.get('file_path', 'Unknown')}\n"
            f"Code:\n{chunk.get('text', '')[:500]}"
        )

    prompt = f"""
You are helping a beginner understand a code repository.

Create a SHORT developer reading guide in Markdown.

Use only these sections:

## 1. Start Here
Explain the project's purpose in 2 sentences, if confirmed.

## 2. Reading Order
Recommend up to 5 existing files in the best order.
Explain each file's role in one short sentence.

## 3. Execution Flow
Give 3-4 steps explaining how the application works.
Use only flow details supported by the code.

## 4. Next Steps
List up to 3 practical things a beginner should explore.

Available files:
{file_list}

Code samples:
{"".join(item + chr(10) + chr(10) for item in code_samples)}

Rules:
- Keep the guide under 250 words.
- Use simple, clear English.
- Recommend only files in the available file list.
- Do not invent functions, commands, features, or execution steps.
- If something is unclear, say "Not confirmed from provided code".
- Avoid repetition and long paragraphs.
"""

    client = genai.Client(api_key=api_key)

    print(f"Generating reading guide with {model_name}...")

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )

    guide = response.text

    if not guide:
        raise RuntimeError("Gemini returned an empty reading guide.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(guide, encoding="utf-8")

    print(f"Reading guide saved: {output_path}")
