import os
import json
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.nodes.ingest import ingest_repository
from backend.nodes.embed import build_embeddings
from backend.nodes.retrieve import search_code
from backend.nodes.workflow import run_analysis_workflow


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
SAMPLES_DIR = BASE_DIR / "samples"
INDEX_DIR = BASE_DIR / "indexes"
OUTPUT_DIR = BASE_DIR / "outputs"

CHUNKS_PATH = SAMPLES_DIR / "chunks.jsonl"
INDEX_PATH = INDEX_DIR / "faiss.index"
METADATA_PATH = INDEX_DIR / "metadata.json"
STATS_PATH = OUTPUT_DIR / "repository_stats.json"
SUMMARY_PATH = OUTPUT_DIR / "architecture_summary.md"

REPORT_FILES = {
    "architecture": OUTPUT_DIR / "architecture_summary.md",
    "guide": OUTPUT_DIR / "reading_guide.md",
    "issues": OUTPUT_DIR / "good_first_issues.md",
    "patch": OUTPUT_DIR / "suggested_patch.md",
}

IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    "coverage",
}

TECH_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "React",
    ".ts": "TypeScript",
    ".tsx": "React + TypeScript",
    ".html": "HTML",
    ".css": "CSS",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C/C++",
    ".hpp": "C++",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".rb": "Ruby",
    ".sql": "SQL",
    ".ipynb": "Jupyter Notebook",
    ".vue": "Vue",
    ".svelte": "Svelte",
}

# This FastAPI app exposes the repo analysis and report endpoints for the frontend.
app = FastAPI(
    title="Codebase Onboarding Assistant",
    description="AI-powered repository onboarding API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    """Input payload for a repository analysis request.

    repo: GitHub URL or local project path to inspect.
    """

    repo: str = Field(min_length=1, max_length=1000)


class SearchRequest(BaseModel):
    """Input payload for semantic code search.

    query: Natural-language description of the code being searched.
    top_k: Maximum number of matching chunks to return.
    """

    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)


# Start from a safe empty summary so the frontend can still render a valid response.
def empty_stats():
    """Return the default empty repository statistics structure."""

    return {
        "total_files": 0,
        "indexed_files": 0,
        "total_lines": 0,
        "repository_size": 0,
        "technologies": [],
        "project_type": "Not analyzed",
    }


# Save the latest repo summary to disk so the dashboard can read it without re-running analysis.
def save_stats(stats):
    """Persist the repository summary JSON to disk for the frontend API."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# Read the saved summary back when the app reloads or asks for the repository overview.
def load_stats():
    """Read saved repository stats, falling back to empty values on errors."""

    if not STATS_PATH.exists():
        return empty_stats()

    try:
        stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))

        if not isinstance(stats, dict):
            return empty_stats()

        result = empty_stats()
        result.update(stats)
        return result

    except (OSError, json.JSONDecodeError):
        return empty_stats()


# Only expose report URLs that were actually generated, so the frontend does not show broken links.
def report_links():
    """Build a list of generated report endpoints that are currently available."""

    return {
        name: f"/api/reports/{name}"
        for name, path in REPORT_FILES.items()
        if path.exists() and path.stat().st_size > 0
    }


# Use a local filesystem scan as the backup path when the repo is not a GitHub URL or when the AI metadata is incomplete.
def calculate_python_stats(repo, base_stats=None):
    """Compute a fallback repository summary using the local filesystem.

    repo: GitHub URL or local repository path. base_stats: ingestion-derived counts.
    """
    stats = dict(base_stats or {})

    is_github_url = str(repo).startswith(
        ("https://github.com/", "http://github.com/")
    )

    if is_github_url:
        stats.setdefault("total_files", 0)
        stats.setdefault("indexed_files", 0)
        stats.setdefault("total_lines", 0)
        stats.setdefault("repository_size", 0)
        stats.setdefault("technologies", [])
        stats.setdefault("project_type", "Unknown")
        stats["stats_source"] = "python_fallback"
        return stats

    root = Path(repo).expanduser().resolve()

    if not root.is_dir():
        stats["stats_source"] = "python_fallback"
        return stats

    total_files = 0
    total_lines = 0
    total_size = 0
    technologies = set()
    has_python = False
    has_package_json = False
    has_dockerfile = False

    for current_dir, dirs, filenames in os.walk(root):
        dirs[:] = [
            directory
            for directory in dirs
            if directory not in IGNORED_DIRS
        ]

        for filename in filenames:
            path = Path(current_dir) / filename

            try:
                file_size = path.stat().st_size
            except OSError:
                continue

            total_files += 1
            total_size += file_size

            suffix = path.suffix.lower()
            name = path.name.lower()

            if suffix in TECH_MAP:
                technologies.add(TECH_MAP[suffix])

            if suffix == ".py":
                has_python = True

            if name == "package.json":
                has_package_json = True

            if name == "dockerfile":
                has_dockerfile = True
                technologies.add("Docker")

            text_file = (
                suffix in TECH_MAP
                or suffix in {
                    ".txt", ".md", ".json", ".yaml", ".yml",
                    ".toml", ".ini", ".cfg", ".sh", ".bat",
                    ".ps1", ".xml", ".sql",
                }
                or name in {
                    "dockerfile",
                    "requirements.txt",
                    "pyproject.toml",
                    "package.json",
                    "readme",
                    "makefile",
                    ".gitignore",
                    ".env.example",
                }
            )

            if text_file:
                try:
                    with path.open(
                        "r",
                        encoding="utf-8",
                        errors="ignore",
                    ) as file:
                        total_lines += sum(1 for _ in file)
                except OSError:
                    pass

    if has_package_json and has_python:
        project_type = "Full-stack / Multi-language"
    elif has_package_json:
        project_type = "JavaScript / Node.js"
    elif has_python:
        project_type = "Python"
    elif len(technologies) > 1:
        project_type = "Multi-language"
    elif technologies:
        project_type = next(iter(technologies))
    else:
        project_type = "Unknown"

    # Keep ingestion-provided values if available, otherwise use local scan.
    stats.setdefault("total_files", total_files)
    stats.setdefault("total_lines", total_lines)
    stats.setdefault("repository_size", total_size)
    stats.setdefault("technologies", sorted(technologies))
    stats.setdefault("project_type", project_type)
    stats.setdefault("indexed_files", 0)

    # Ensure local measurements are accurate.
    stats["total_files"] = total_files
    stats["total_lines"] = total_lines
    stats["repository_size"] = total_size
    stats["technologies"] = sorted(technologies)
    stats["project_type"] = project_type
    stats["stats_source"] = "python_fallback"

    return stats


# Try the AI summary only when we already have reliable local counts, and fall back safely if Gemini is unavailable.
def get_stats_with_gemini(repo, python_stats):
    """Ask Gemini for a richer project summary while keeping the Python counts as fallback.

    repo: Repository path or URL to describe. python_stats: locally computed metrics for validation.
    """
    fallback_stats = {
        **python_stats,
        "stats_source": "python_fallback",
    }

    try:
        # Load .env if python-dotenv is installed.
        try:
            from dotenv import load_dotenv
            load_dotenv(BASE_DIR / ".env")
        except ImportError:
            pass

        api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )

        if not api_key:
            raise RuntimeError(
                "Gemini API key not found. Set GEMINI_API_KEY in .env."
            )

        import google.generativeai as genai

        genai.configure(api_key=api_key)

        model_name = os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash",
        )
        model = genai.GenerativeModel(model_name)

        prompt = f"""
You are analyzing a software repository.

Repository URL/path: {repo}

Python-measured statistics:
{json.dumps(python_stats, ensure_ascii=False)}

Identify the main technologies and project type using the supplied
statistics. Do not invent technologies unsupported by the data.

Return ONLY valid JSON in this format:
{{
  "technologies": ["Python", "FastAPI"],
  "project_type": "Web Application"
}}

The technologies field must be an array of strings.
The project_type field must be a non-empty string.
"""

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[-1]
            if response_text.endswith("```"):
                response_text = response_text[:-3].strip()
            if response_text.lower().startswith("json"):
                response_text = response_text[4:].strip()

        ai_stats = json.loads(response_text)

        technologies = ai_stats.get("technologies")
        project_type = ai_stats.get("project_type")

        if (
            not isinstance(technologies, list)
            or not all(isinstance(item, str) for item in technologies)
        ):
            raise ValueError("Gemini returned invalid technologies.")

        if not isinstance(project_type, str) or not project_type.strip():
            raise ValueError("Gemini returned an invalid project type.")

        result = {
            **python_stats,
            "technologies": technologies,
            "project_type": project_type.strip(),
            "stats_source": "gemini",
        }

        result.pop("stats_warning", None)
        return result

    except Exception as error:
        print(
            "Gemini stats request failed. "
            f"Using Python fallback instead: {error}"
        )

        fallback_stats["stats_warning"] = str(error)
        return fallback_stats


# Serve the frontend entry page so the browser can open the app UI.
@app.get("/")
def home():
    """Serve the frontend entry page for the onboarding app."""

    index_file = FRONTEND_DIR / "index.html"

    if not index_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend index.html was not found.",
        )

    return FileResponse(index_file)


# Health checks help confirm the API is running before the frontend sends repo work.
@app.get("/api/health")
def health_check():
    """Return a lightweight status response for uptime monitoring."""

    return {
        "status": "ok",
        "message": "FastAPI is running",
    }


# Return the most recent saved summary so the UI can show quick repo metrics immediately.
@app.get("/api/stats")
def repository_stats():
    """Return the saved repository summary from the last analysis run."""

    # Reading saved stats does not call Gemini.
    return load_stats()


# This is the main analysis endpoint: it validates the repo, builds the index, and generates reports.
@app.post("/api/analyze")
def analyze_repository(request: AnalyzeRequest):
    """Analyze a repository end-to-end and return generated reports and stats.

    request: Validate the repo path, ingest code chunks, create embeddings, and run the workflow.
    """
    repo = request.repo.strip()

    is_github_url = repo.startswith(
        ("https://github.com/", "http://github.com/")
    )

    if is_github_url:
        parsed = urlparse(repo)

        if (
            parsed.hostname != "github.com"
            or len(parsed.path.strip("/").split("/")) < 2
        ):
            raise HTTPException(
                status_code=400,
                detail="Enter a valid GitHub repository URL.",
            )
    else:
        local_path = Path(repo).expanduser()

        if not local_path.is_dir():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Enter a valid GitHub repository URL "
                    "or an existing local folder path."
                ),
            )

        repo = str(local_path.resolve())

    for folder in (SAMPLES_DIR, INDEX_DIR, OUTPUT_DIR):
        folder.mkdir(parents=True, exist_ok=True)

    # Remove reports from the previous repository so they cannot
    # accidentally appear as reports for the newly selected repository.
    for report_path in REPORT_FILES.values():
        report_path.unlink(missing_ok=True)

    # STEP 1: Ingest the repository.
    # If ingestion fails, return an error; don't claim analysis succeeded.
    try:
        stats_from_ingest = ingest_repository(
            repo,
            str(CHUNKS_PATH),
        )

        if not isinstance(stats_from_ingest, dict):
            stats_from_ingest = {}

        if not CHUNKS_PATH.exists():
            raise RuntimeError(
                "Ingestion did not create samples/chunks.jsonl."
            )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Repository ingestion failed: {error}",
        ) from error

    # STEP 2: Calculate fallback stats and try Gemini.
    # Stats are saved BEFORE embedding/report generation.
    try:
        python_stats = calculate_python_stats(
            repo,
            stats_from_ingest,
        )
        stats = get_stats_with_gemini(repo, python_stats)
        save_stats(stats)

    except Exception as error:
        # Even if stats handling fails, try to preserve available ingestion data.
        stats = {
            **empty_stats(),
            **(
                stats_from_ingest
                if isinstance(stats_from_ingest, dict)
                else {}
            ),
            "stats_source": "python_fallback",
            "stats_warning": str(error),
        }
        save_stats(stats)

    # STEP 3: Build embeddings and generate the four reports.
    try:
        # Prevent stale index files from being mistaken for new ones.
        INDEX_PATH.unlink(missing_ok=True)
        METADATA_PATH.unlink(missing_ok=True)

        build_embeddings(
            str(CHUNKS_PATH),
            str(INDEX_PATH),
            str(METADATA_PATH),
        )

        if not INDEX_PATH.exists() or not METADATA_PATH.exists():
            raise RuntimeError(
                "Embedding or indexing did not complete."
            )

        run_analysis_workflow(
            metadata_path=str(METADATA_PATH),
            output_path=str(SUMMARY_PATH),
        )

        missing_reports = [
            name
            for name, path in REPORT_FILES.items()
            if not path.exists() or path.stat().st_size == 0
        ]

        if missing_reports:
            raise RuntimeError(
                "These reports were not generated: "
                + ", ".join(missing_reports)
            )

        return {
            "status": "completed",
            "message": "Repository statistics and AI reports generated.",
            "stats": stats,
            "reports": report_links(),
        }

    except Exception as error:
        # Stats are already saved, even if Gemini report generation fails.
        print(f"Repository report/index generation failed: {error}")

        return {
            "status": "partial",
            "message": (
                "Repository statistics are available, but indexing "
                "or AI report generation failed."
            ),
            "error": str(error),
            "stats": stats,
            "reports": report_links(),
        }


# Fetch one generated report by name when the frontend opens a specific tab or file.
@app.get("/api/reports/{report_name}")
def get_report(report_name: str):
    """Return one generated onboarding report by name.

    report_name: Report slug such as architecture, guide, issues, or patch.
    """
    if report_name not in REPORT_FILES:
        raise HTTPException(
            status_code=404,
            detail="Report not found.",
        )

    path = REPORT_FILES[report_name]

    if not path.exists() or path.stat().st_size == 0:
        raise HTTPException(
            status_code=404,
            detail="This report has not been generated yet.",
        )

    return {
        "name": report_name,
        "content": path.read_text(encoding="utf-8"),
    }


# Search is useful for asking natural-language questions about the indexed repository.
@app.post("/api/search")
def search_repository(request: SearchRequest):
    """Search the indexed repository using a semantic code query.

    request: The search text and number of results requested by the client.
    """
    if not INDEX_PATH.exists() or not METADATA_PATH.exists():
        raise HTTPException(
            status_code=400,
            detail="Index the repository before searching.",
        )

    try:
        results = search_code(
            request.query,
            str(INDEX_PATH),
            str(METADATA_PATH),
            request.top_k,
        )

        return {
            "query": request.query,
            "results": results,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Code search failed: {error}",
        ) from error


app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static",
)
