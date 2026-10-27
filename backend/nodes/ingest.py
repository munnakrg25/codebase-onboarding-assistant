import json
from pathlib import Path

from backend.utils.chunker import split_into_chunks
from backend.utils.repo_utils import open_repository


SUPPORTED_EXTENSIONS = {
    ".py", ".md", ".rst", ".yml", ".yaml", ".json"
}

SKIP_FOLDERS = {
    ".git", ".venv", "venv", "__pycache__",
    "node_modules", "dist", "build", ".pytest_cache",
    ".mypy_cache", ".next", "coverage"
}

MAX_FILE_SIZE = 1_000_000

TECH_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "React",
    ".ts": "TypeScript",
    ".tsx": "React / TypeScript",
    ".html": "HTML",
    ".css": "CSS",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".sql": "SQL",
    ".ipynb": "Jupyter Notebook",
}


# Count the files and languages first so the app can show quick project stats before the full analysis runs.
def collect_repository_stats(root):
    """Compute a lightweight inventory of project files and language signals.

    root: Local repository path to inspect for size, language, and line counts.
    """

    total_files = 0
    total_lines = 0
    total_bytes = 0
    indexed_files = set()
    technologies = set()
    has_python = False
    has_package_json = False

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if any(part in SKIP_FOLDERS for part in relative.parts):
            continue

        try:
            size = path.stat().st_size
        except OSError:
            continue

        total_files += 1
        total_bytes += size

        suffix = path.suffix.lower()
        filename = path.name.lower()

        if suffix in TECH_MAP:
            technologies.add(TECH_MAP[suffix])

        if suffix == ".py":
            has_python = True

        if filename == "package.json":
            has_package_json = True

        # Match the files that the ingestion pipeline supports.
        if suffix in SUPPORTED_EXTENSIONS and size <= MAX_FILE_SIZE:
            try:
                content = path.read_text(
                    encoding="utf-8",
                    errors="replace"
                )
                if content.strip():
                    indexed_files.add(relative.as_posix())
            except OSError:
                pass

        readable = (
            suffix in TECH_MAP
            or suffix in {
                ".md", ".rst", ".txt", ".json", ".yaml", ".yml",
                ".toml", ".ini", ".cfg", ".sh", ".xml"
            }
            or filename in {"dockerfile", "makefile"}
        )

        if readable and size <= MAX_FILE_SIZE:
            try:
                with path.open(
                    "r", encoding="utf-8", errors="replace"
                ) as file:
                    total_lines += sum(1 for _ in file)
            except OSError:
                pass

    if has_python and has_package_json:
        project_type = "Full-stack / Multi-language"
    elif has_package_json:
        project_type = "JavaScript / Node.js"
    elif has_python:
        project_type = "Python"
    elif len(technologies) == 1:
        project_type = next(iter(technologies))
    elif technologies:
        project_type = "Multi-language"
    else:
        project_type = "Unknown"

    return {
        "total_files": total_files,
        "indexed_files": len(indexed_files),
        "total_lines": total_lines,
        "repository_size": total_bytes,
        "technologies": sorted(technologies),
        "project_type": project_type,
    }


# This is the first step in the pipeline: turn repo files into searchable chunks that later get embedded.
def ingest_repository(repo_input, output_file):
    """Scan a repository, split files into chunks, and save them for later indexing.

    repo_input: Local path or remote Git URL to analyze. output_file: JSONL output file for the chunk records.
    """

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    total_files = 0
    total_chunks = 0

    with open_repository(repo_input) as repo_path:

        # Calculate stats while the repository is available.
        stats = collect_repository_stats(repo_path)

        with output_file.open("w", encoding="utf-8") as output:
            for file_path in repo_path.rglob("*"):

                if not file_path.is_file():
                    continue

                relative = file_path.relative_to(repo_path)

                if any(part in SKIP_FOLDERS for part in relative.parts):
                    continue

                if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue

                try:
                    if file_path.stat().st_size > MAX_FILE_SIZE:
                        continue

                    content = file_path.read_text(
                        encoding="utf-8",
                        errors="replace"
                    )
                except OSError:
                    continue

                if not content.strip():
                    continue

                relative_path = relative.as_posix()
                chunks = split_into_chunks(content)

                for chunk_index, chunk in enumerate(chunks):
                    record = {
                        "meta": {
                            "file_path": relative_path,
                            "chunk_index": chunk_index,
                            "start_line": chunk["start_line"],
                            "end_line": chunk["end_line"],
                            "extension": file_path.suffix.lower()
                        },
                        "text": chunk["text"]
                    }

                    output.write(
                        json.dumps(record, ensure_ascii=False) + "\n"
                    )
                    total_chunks += 1

                total_files += 1

    print(f"Files processed: {total_files}")
    print(f"Chunks created: {total_chunks}")
    print(f"Output saved to: {output_file}")
    print(f"Repository stats: {stats}")

    return stats
