import json
from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph, START, END

from backend.schemas.workflow_state import WorkflowState
from backend.nodes.summarize import generate_architecture_summary
from backend.nodes.reading_guide import generate_reading_guide
from backend.nodes.issue_generator import generate_good_first_issues
from backend.nodes.patch_suggester import suggest_patch

OUTPUT_DIR = Path("outputs")


# Check the metadata file before any report is generated, so the workflow fails early on bad input.
def validate_repository(state: WorkflowState) -> dict[str, Any]:
    """Validate indexed metadata before writing any onboarding reports.

    state: Workflow state containing the metadata file path and output targets.
    """

    metadata_path = Path(state["metadata_path"])

    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Metadata not found: {metadata_path}"
        )

    with metadata_path.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    if not isinstance(metadata, list) or not metadata:
        raise ValueError("Repository metadata is empty or invalid.")

    print(f"Validated {len(metadata)} metadata chunks.")

    return {"status": "validated"}


# Pick a stable Python file for the patch example so the suggestions are reproducible.
def select_patch_file(metadata_path: str) -> str:
    """Choose a realistic Python file to use for the suggested-patch example.

    metadata_path: Path to the JSON metadata index produced during ingestion and embedding.
    """

    with Path(metadata_path).open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    files = {
        item.get("file_path", "").replace("\\", "/")
        for item in metadata
        if item.get("file_path", "").lower().endswith(".py")
    }

    if not files:
        raise ValueError(
            "No indexed Python file found for patch generation."
        )

    # Prefer common application entry points when available.
    preferred = ("main.py", "app.py", "api.py")

    for filename in preferred:
        matches = sorted(
            path for path in files
            if Path(path).name.lower() == filename
        )
        if matches:
            return matches[0]

    # Otherwise select a deterministic, non-test Python file.
    candidates = sorted(
        path for path in files
        if not any(
            part.lower() in {"tests", "test", "examples"}
            for part in Path(path).parts
        )
    )

    return candidates[0] if candidates else sorted(files)[0]


# Create the architecture summary before the rest of the onboarding docs are generated.
def summarize_repository(state: WorkflowState) -> dict[str, Any]:
    """Generate the project overview summary and store it in the workflow state."""

    print("Generating architecture report...")

    generate_architecture_summary(
        metadata_path=state["metadata_path"],
        output_path=state["output_path"],
    )

    summary = Path(state["output_path"]).read_text(
        encoding="utf-8"
    )

    return {
        "summary": summary,
        "status": "summary_completed",
    }


def create_reading_guide(state: WorkflowState) -> dict[str, Any]:
    """Create the beginner-friendly reading guide from the indexed repository chunks."""

    print("Generating reading guide...")

    guide_path = OUTPUT_DIR / "reading_guide.md"

    generate_reading_guide(
        metadata_path=state["metadata_path"],
        output_path=str(guide_path),
    )

    guide = guide_path.read_text(encoding="utf-8")

    return {
        "reading_guide": guide,
        "status": "guide_completed",
    }


def create_issue_suggestions(state: WorkflowState) -> dict[str, Any]:
    """Generate beginner-friendly contribution ideas from the indexed codebase."""

    print("Generating good first issues...")

    issues_path = OUTPUT_DIR / "good_first_issues.md"

    generate_good_first_issues(
        metadata_path=state["metadata_path"],
        output_path=str(issues_path),
    )

    return {"status": "issues_completed"}


def create_suggested_patch(state: WorkflowState) -> dict[str, Any]:
    """Generate a patch suggestion for the best candidate file in the repository."""

    print("Generating suggested patch...")

    file_path = select_patch_file(state["metadata_path"])
    patch_path = OUTPUT_DIR / "suggested_patch.md"

    suggest_patch(
        file_path=file_path,
        metadata_path=state["metadata_path"],
        output_path=str(patch_path),
    )

    return {
        "patch_file": str(patch_path),
        "status": "completed",
    }


# Link each report step in order so each file depends on the previous one finishing.
def build_workflow():
    """Create the LangGraph workflow that runs each onboarding step in order."""

    graph = StateGraph(WorkflowState)

    graph.add_node("validate", validate_repository)
    graph.add_node("summarize", summarize_repository)
    graph.add_node("reading_guide", create_reading_guide)
    graph.add_node("issues", create_issue_suggestions)
    graph.add_node("patch", create_suggested_patch)

    graph.add_edge(START, "validate")
    graph.add_edge("validate", "summarize")
    graph.add_edge("summarize", "reading_guide")
    graph.add_edge("reading_guide", "issues")
    graph.add_edge("issues", "patch")
    graph.add_edge("patch", END)

    return graph.compile()


# Run the whole pipeline from a single function so the app can trigger all reports together.
def run_analysis_workflow(
    metadata_path="indexes/metadata.json",
    output_path="outputs/architecture_summary.md",
):
    """Run the full repository analysis pipeline and write the generated reports.

    metadata_path: Location of the repository metadata JSON produced by ingestion. output_path: File for the architecture summary.
    """

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    initial_state: WorkflowState = {
        "metadata_path": str(metadata_path),
        "output_path": str(output_path),
        "summary": "",
        "reading_guide": "",
        "status": "started",
    }

    result = build_workflow().invoke(initial_state)

    print(f"Workflow status: {result['status']}")
    print("Generated reports:")
    print(f"- Architecture: {output_path}")
    print("- Reading Guide: outputs/reading_guide.md")
    print("- Good First Issues: outputs/good_first_issues.md")
    print("- Suggested Patch: outputs/suggested_patch.md")

    return result
