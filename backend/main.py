import argparse

from backend.nodes.ingest import ingest_repository
from backend.nodes.embed import build_embeddings
from backend.nodes.retrieve import search_code
from backend.nodes.summarize import generate_architecture_summary
from backend.nodes.workflow import run_analysis_workflow
from backend.nodes.reading_guide import generate_reading_guide
from backend.nodes.issue_generator import generate_good_first_issues
from backend.nodes.patch_suggester import suggest_patch


# This CLI entry point lets a developer run each repo analysis step manually.
def main():
    """Parse the command-line entry points for the onboarding pipeline."""

    parser = argparse.ArgumentParser(
        description="Codebase Onboarding Assistant"
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # Each subcommand maps to one phase of the onboarding pipeline.
    ingest_parser = commands.add_parser("ingest")
    ingest_parser.add_argument("--repo", required=True)
    ingest_parser.add_argument(
        "--out", default="samples/chunks.jsonl"
    )

    # Create embeddings and FAISS index.
    embed_parser = commands.add_parser("embed")
    embed_parser.add_argument(
        "--chunks", default="samples/chunks.jsonl"
    )
    embed_parser.add_argument(
        "--index", default="indexes/faiss.index"
    )
    embed_parser.add_argument(
        "--meta", default="indexes/metadata.json"
    )

    # Search repository code.
    search_parser = commands.add_parser("search")
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument(
        "--index", default="indexes/faiss.index"
    )
    search_parser.add_argument(
        "--meta", default="indexes/metadata.json"
    )
    search_parser.add_argument(
        "--top-k", type=int, default=3
    )

    # Issue Parser
    issues_parser = commands.add_parser(
        "issues",
        help="Generate beginner-friendly contribution ideas",
    )

    issues_parser.add_argument(
        "--meta",
        default="indexes/metadata.json",
    )

    issues_parser.add_argument(
        "--out",
        default="outputs/good_first_issues.md",
    )

    # Generate a suggested patch.
    patch_parser = commands.add_parser(
        "patch",
        help="Generate a suggested patch for a file",
    )
    patch_parser.add_argument(
        "--file",
        required=True,
        help="Repository-relative path of the file to review",
    )

    patch_parser.add_argument(
        "--meta",
        default="indexes/metadata.json",
    )

    patch_parser.add_argument(
        "--out",
        default="outputs/suggested_patch.md",
    )

    # Generate architecture summary.
    summary_parser = commands.add_parser("summarize")
    summary_parser.add_argument(
        "--meta", default="indexes/metadata.json"
    )
    summary_parser.add_argument(
        "--out", default="outputs/architecture_summary.md"
    )
    summary_parser.add_argument(
        "--max-chunks", type=int, default=18
    )

    # Run LangGraph workflow.
    analyze_parser = commands.add_parser(
        "analyze",
        help="Analyze a repository using LangGraph",
    )
    analyze_parser.add_argument(
        "--meta", default="indexes/metadata.json"
    )
    analyze_parser.add_argument(
        "--out", default="outputs/architecture_summary.md"
    )
    guide_parser = commands.add_parser(
        "guide",
        help="Generate a beginner-friendly developer reading guide",
    )

    guide_parser.add_argument(
        "--meta",
        default="indexes/metadata.json",
    )

    guide_parser.add_argument(
        "--out",
        default="outputs/reading_guide.md",
    )

    args = parser.parse_args()

    try:
        if args.command == "ingest":
            ingest_repository(args.repo, args.out)

        elif args.command == "embed":
            build_embeddings(
                args.chunks,
                args.index,
                args.meta,
            )

        elif args.command == "search":
            results = search_code(
                args.query,
                args.index,
                args.meta,
                args.top_k,
            )

            for number, result in enumerate(results, start=1):
                print(f"\nResult {number}")
                print(f"File: {result['file_path']}")
                print(
                    f"Lines: {result['start_line']}-"
                    f"{result['end_line']}"
                )
                print(f"Score: {result['score']:.4f}")
                print("Code:")
                print(result["text"][:1000])

        elif args.command == "summarize":
            generate_architecture_summary(
                args.meta,
                args.out,
                args.max_chunks,
            )

        elif args.command == "issues":
            generate_good_first_issues(
                metadata_path=args.meta,
                output_path=args.out,
            )

        elif args.command == "patch":
            suggest_patch(
                file_path=args.file,
                metadata_path=args.meta,
                output_path=args.out,
            )

        elif args.command == "analyze":
            run_analysis_workflow(
                metadata_path=args.meta,
                output_path=args.out,
            )
        elif args.command == "guide":
            generate_reading_guide(
                metadata_path=args.meta,
                output_path=args.out,
            )

    except Exception as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
