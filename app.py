
import json
import subprocess
import sys
from pathlib import Path

import streamlit as st


# -----------------------------
# Basic project settings
# -----------------------------

# Set the app page layout so the dashboard feels clean and easy to use.
st.set_page_config(
    page_title="Codebase Onboarding Assistant",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Use the project root as the base path so the app can find repo data and output files.
BASE_DIR = Path(__file__).resolve().parent

CHUNKS_FILE = BASE_DIR / "samples" / "chunks.jsonl"
METADATA_FILE = BASE_DIR / "indexes" / "metadata.json"

SUMMARY_FILE = BASE_DIR / "outputs" / "architecture_summary.md"
GUIDE_FILE = BASE_DIR / "outputs" / "reading_guide.md"
ISSUES_FILE = BASE_DIR / "outputs" / "good_first_issues.md"
PATCH_FILE = BASE_DIR / "outputs" / "suggested_patch.md"


# -----------------------------
# Custom CSS - no sidebar
# -----------------------------

# Hide the sidebar and keep the interface focused on the repository insights.
st.markdown(
    """
    <style>
    .stApp {
        background-color: #f8fafc;
    }

    [data-testid="stSidebar"] {
        display: none;
    }

    header[data-testid="stHeader"] {
        background: transparent;
    }

    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1450px;
    }

    .navbar {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 15px 20px;
        margin-bottom: 24px;
    }

    .brand {
        color: #0f172a;
        font-size: 21px;
        font-weight: 700;
    }

    .welcome-box {
        background: linear-gradient(110deg, #effcf6, #ffffff);
        border: 1px solid #d1fae5;
        border-radius: 14px;
        padding: 25px;
        margin-bottom: 20px;
    }

    .welcome-title {
        color: #0f172a;
        font-size: 25px;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .welcome-text {
        color: #475569;
        font-size: 14px;
        line-height: 1.7;
    }

    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #e2e8f0;
        padding: 17px;
        border-radius: 12px;
    }

    div.stButton > button[kind="primary"] {
        background: #07875b;
        border: none;
        color: white;
        border-radius: 8px;
        font-weight: 600;
        min-height: 42px;
    }

    div.stButton > button[kind="primary"]:hover {
        background: #066c49;
        color: white;
    }

    .section-heading {
        font-size: 19px;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 12px;
    }

    div[data-testid="stTabs"] button {
        font-weight: 600;
    }

    .hint {
        color: #64748b;
        font-size: 13px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Helper functions
# -----------------------------

# Reuse the backend CLI so the Streamlit UI can trigger the same repo analysis steps.
def run_command(arguments):
    """Invoke a backend CLI command from the Streamlit app.

    arguments: CLI arguments to pass through to backend.main without altering the app logic.
    """

    result = subprocess.run(
        [sys.executable, "-m", "backend.main", *arguments],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=1800,
    )

    if result.returncode != 0:
        error = result.stderr or result.stdout
        raise RuntimeError(error or "Backend command failed.")

    return result.stdout


# Read the generated markdown file so the app can display the report in the dashboard.
def read_report(file_path):
    """Load the contents of a generated Markdown report if it exists."""

    if file_path.exists():
        return file_path.read_text(encoding="utf-8")

    return "Report abhi generate nahi hui hai."


def read_metadata():
    """Load the repository metadata produced by ingestion and embedding."""

    if not METADATA_FILE.exists():
        return []

    data = json.loads(METADATA_FILE.read_text(encoding="utf-8"))

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("metadata", [])

    return []


def get_value(item, possible_keys, default=""):
    """Return the first available metadata value across a set of common field names.

    item: Metadata dictionary for one code chunk. possible_keys: Alternative field names used by different ingestion formats. default: Value to return when none match.
    """

    for key in possible_keys:
        if key in item and item[key] is not None:
            return item[key]

    return default


def get_repository_stats():
    """Calculate a simple summary of files, ranges, and technologies from the indexed metadata."""

    metadata = read_metadata()

    files = set()
    last_lines = {}
    technologies = set()

    for item in metadata:
        if not isinstance(item, dict):
            continue

        path = get_value(
            item,
            ["file_path", "path", "source", "file"],
            "",
        )

        if isinstance(path, str) and path:
            files.add(path)

            start_line = get_value(
                item,
                ["start_line"],
                1,
            )
            end_line = get_value(
                item,
                ["end_line"],
                start_line,
            )

            try:
                last_lines[path] = max(
                    last_lines.get(path, 0),
                    int(end_line),
                )
            except (TypeError, ValueError):
                pass

            suffix = Path(path).suffix.lower()

            if suffix == ".py":
                technologies.add("Python")
            elif suffix in {".yml", ".yaml"}:
                technologies.add("YAML")
            elif suffix == ".json":
                technologies.add("JSON")
            elif suffix in {".md", ".rst"}:
                technologies.add("Documentation")

    total_lines = sum(last_lines.values())

    return {
        "files": len(files),
        "lines": total_lines,
        "technologies": sorted(technologies),
    }


# Show each generated report in the page and allow the user to download it locally.
def display_report(file_path):
    """Display and provide download for a Markdown report."""

    report = read_report(file_path)

    st.markdown(report)

    if file_path.exists():
        st.download_button(
            label="Download Markdown",
            data=report,
            file_name=file_path.name,
            mime="text/markdown",
            key=f"download_{file_path.name}",
        )


# -----------------------------
# Top navbar
# -----------------------------

left, right = st.columns([3, 2])

with left:
    st.markdown(
        '<div class="brand">💻 Codebase Onboarding Assistant</div>',
        unsafe_allow_html=True,
    )

with right:
    page = st.radio(
        "Navigation",
        [
            "Home",
            "Architecture",
            "Reading Guide",
            "Issues",
            "Patch",
            "Search",
        ],
        horizontal=True,
        label_visibility="collapsed",
        key="navigation",
    )

st.divider()


# -----------------------------
# Welcome section
# -----------------------------

st.markdown(
    """
    <div class="welcome-box">
        <div class="welcome-title">
            Welcome to Codebase Onboarding Assistant
        </div>
        <div class="welcome-text">
            Analyze a Python repository and get AI-powered architecture
            summaries, beginner reading guides, contribution ideas
            and safe patch suggestions.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Repository input
# -----------------------------

st.markdown("### Analyze your repository")

repo_input = st.text_input(
    "GitHub repository URL or local folder path",
    placeholder="https://github.com/username/repository",
    help="Public GitHub URL ya apne computer par repository ka folder path do.",
)

analyze_clicked = st.button(
    "▶  Analyze Repository",
    type="primary",
    use_container_width=True,
)


# -----------------------------
# Analyze pipeline
# -----------------------------

# Run the repo analysis workflow only after the user submits a valid repository path.
if analyze_clicked:
    if not repo_input.strip():
        st.warning("Pehle GitHub URL ya local repository path enter karo.")

    else:
        try:
            with st.status(
                "Repository analyze ho rahi hai...",
                expanded=True,
            ) as status:

                st.write("1. Repository files read ho rahi hain...")

                run_command([
                    "ingest",
                    "--repo",
                    repo_input.strip(),
                    "--out",
                    "samples/chunks.jsonl",
                ])

                st.write("2. Code embeddings aur search index ban raha hai...")

                run_command(["embed"])

                st.write("3. LangGraph workflow run ho raha hai...")

                run_command(["analyze"])

                status.update(
                    label="Repository analysis complete!",
                    state="complete",
                    expanded=False,
                )

            st.session_state["analyzed"] = True
            st.session_state["repo_input"] = repo_input.strip()

            st.success("Repository successfully analyze ho gayi!")

        except Exception as error:
            st.error("Analysis complete nahi ho payi.")
            st.code(str(error))


# -----------------------------
# Dashboard statistics
# -----------------------------

# Build a quick overview from the indexed files so the page feels informative even before the detailed reports open.
stats = get_repository_stats()

st.markdown("### Repository Overview")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Total Files", stats["files"])

with c2:
    st.metric("Estimated Lines", f'{stats["lines"]:,}')

with c3:
    tech = ", ".join(stats["technologies"][:3])
    st.metric("Key Technologies", tech or "Not available")

with c4:
    st.metric(
        "Project Type",
        "Python Project" if stats["files"] else "Not analyzed",
    )


st.write("")


# -----------------------------
# Main content and quick actions
# -----------------------------

# Split the page into a main content area and a smaller side panel for shortcuts.
main_col, side_col = st.columns([3, 1])

with main_col:
    st.markdown("### Repository Insights")

    if page in ["Home", "Architecture"]:
        st.markdown("#### Architecture Summary")
        display_report(SUMMARY_FILE)

    elif page == "Reading Guide":
        st.markdown("#### Developer Reading Guide")
        display_report(GUIDE_FILE)

    elif page == "Issues":
        st.markdown("#### Good First Issues")
        display_report(ISSUES_FILE)

    elif page == "Patch":
        st.markdown("#### Suggested Patch")
        st.caption(
            "Suggestions ko review karo. Original source files automatically "
            "modify nahi ki jaati hain."
        )

        target_file = st.text_input(
            "File path",
            placeholder="backend/main.py",
            key="patch_target",
        )

        if st.button("Generate Patch Suggestion"):
            if not target_file.strip():
                st.warning("Pehle file path enter karo.")

            else:
                try:
                    with st.spinner("Patch suggestion generate ho rahi hai..."):
                        output = run_command([
                            "patch",
                            "--file",
                            target_file.strip(),
                        ])

                    st.session_state["patch_output"] = output
                    st.success("Patch suggestion ready hai.")

                except Exception as error:
                    st.error("Patch generate nahi ho payi.")
                    st.code(str(error))

        if "patch_output" in st.session_state:
            st.code(
                st.session_state["patch_output"],
                language="diff",
            )

        if PATCH_FILE.exists():
            display_report(PATCH_FILE)

    elif page == "Search":
        st.markdown("#### Search Codebase")

        query = st.text_input(
            "Ask a question about the code",
            placeholder="Where are HTTP requests sent?",
            key="search_query",
        )

        top_k = st.slider(
            "Number of results",
            min_value=1,
            max_value=10,
            value=5,
        )

        if st.button("Search Code"):
            if not query.strip():
                st.warning("Search question enter karo.")

            else:
                try:
                    with st.spinner("Code search ho raha hai..."):
                        output = run_command([
                            "search",
                            "--query",
                            query.strip(),
                            "--top-k",
                            str(top_k),
                        ])

                    st.markdown("##### Search Results")
                    st.code(output)

                except Exception as error:
                    st.error("Search nahi ho payi.")
                    st.code(str(error))


with side_col:
    st.markdown("### Quick Actions")

    if st.button("📘 Reading Guide", use_container_width=True):
        st.session_state["navigation"] = "Reading Guide"
        st.rerun()

    if st.button("💡 Good First Issues", use_container_width=True):
        st.session_state["navigation"] = "Issues"
        st.rerun()

    if st.button("🔎 Search Code", use_container_width=True):
        st.session_state["navigation"] = "Search"
        st.rerun()

    st.write("")

    st.markdown("### Recent Activity")

    if st.session_state.get("analyzed"):
        st.success("Repository analyzed")
        st.caption(st.session_state.get("repo_input", ""))
        st.success("Search index created")
        st.success("Analysis reports generated")
    else:
        st.info("Abhi koi repository analyze nahi hui.")

    st.write("")

    st.markdown("### Need Help?")
    st.caption(
        "GitHub repository URL enter karo aur Analyze Repository par click "
        "karke shuru karo."
    )


# -----------------------------
# Footer
# -----------------------------

st.divider()

st.caption(
    "Codebase Onboarding Assistant | Built with Streamlit, LangGraph, "
    "Gemini and FAISS"
)
