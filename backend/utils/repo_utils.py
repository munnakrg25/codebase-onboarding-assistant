
import tempfile
from contextlib import contextmanager
from pathlib import Path

from git import Repo


# This helper makes local folders and remote Git repos behave like the same repository object.
@contextmanager
def open_repository(repo_input):
    """Open a local repository or clone a remote Git URL into a temporary folder.

    repo_input: Local filesystem path or remote Git repository URL to inspect.
    """

    repo_input = str(repo_input)

    # Use the folder directly when a local path is provided.
    local_path = Path(repo_input).expanduser()

    if local_path.is_dir():
        yield local_path.resolve()
        return

    # Otherwise, treat the input as a Git repository URL.
    if not (
        repo_input.startswith("https://")
        or repo_input.startswith("http://")
        or repo_input.startswith("git@")
    ):
        raise ValueError("Provide a valid local folder or Git URL.")

    # TemporaryDirectory automatically cleans up the cloned repository.
    with tempfile.TemporaryDirectory() as temp_dir:
        clone_path = Path(temp_dir) / "repository"

        Repo.clone_from(
            repo_input,
            clone_path,
            depth=1
        )

        yield clone_path
