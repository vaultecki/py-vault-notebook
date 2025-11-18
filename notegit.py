# Copyright [2025] [ecki]
# SPDX-License-Identifier: Apache-2.0

"""
Git wrapper for notebook application with thread-safe operations.
"""
import git
import logging
import pathlib
import shutil
from typing import List, Optional
import PyQt6.QtCore

logger = logging.getLogger(__name__)


class GitWorker(PyQt6.QtCore.QObject):
    """
    Worker that runs in a separate thread for slow Git network operations.
    """
    # Signals for results
    push_finished = PyQt6.QtCore.pyqtSignal()
    push_failed = PyQt6.QtCore.pyqtSignal(str)
    pull_finished = PyQt6.QtCore.pyqtSignal()
    pull_failed = PyQt6.QtCore.pyqtSignal(str)

    @PyQt6.QtCore.pyqtSlot(str)
    def do_pull(self, project_path: str) -> None:
        """
        Executes 'git pull' for all remotes.

        Args:
            project_path: Path to the git repository
        """
        try:
            repo = git.Repo(project_path)
            if not repo.remotes:
                logger.info("No remotes configured, skipping pull")
                self.pull_finished.emit()
                return

            for remote in repo.remotes:
                try:
                    logger.debug(f"Pulling from {remote.name} in background...")
                    remote.pull()
                except git.exc.GitCommandError as e:
                    logger.warning(f"Git pull error for remote {remote.name}: {e}")
                    # Error with one remote shouldn't abort the entire pull
            self.pull_finished.emit()
        except Exception as e:
            logger.error(f"Failed to run background pull: {e}")
            self.pull_failed.emit(str(e))

    @PyQt6.QtCore.pyqtSlot(str)
    def do_push(self, project_path: str) -> None:
        """
        Executes 'git push' for all remotes.

        Args:
            project_path: Path to the git repository
        """
        try:
            repo = git.Repo(project_path)
            if not repo.remotes:
                logger.info("No remotes configured, skipping push")
                self.push_finished.emit()
                return

            for remote in repo.remotes:
                try:
                    logger.debug(f"Pushing to {remote.name} in background...")
                    remote.push()
                except git.exc.GitCommandError as e:
                    logger.warning(f"Git push error for remote {remote.name}: {e}")
            self.push_finished.emit()
        except Exception as e:
            logger.error(f"Failed to run background push: {e}")
            self.push_failed.emit(str(e))


class NoteGit(PyQt6.QtCore.QObject):
    """
    Main Git wrapper class with thread-safe operations.

    Signals:
        trigger_push: Triggers a background push operation
        trigger_pull: Triggers a background pull operation
    """
    # Signals to trigger worker in other thread
    trigger_push = PyQt6.QtCore.pyqtSignal(str)
    trigger_pull = PyQt6.QtCore.pyqtSignal(str)

    def __init__(self, project_path: str):
        """
        Initialize Git wrapper for given project path.

        Args:
            project_path: Path to the project directory

        Raises:
            ImportError: If repository cannot be initialized
        """
        super().__init__()

        logger.info(f"Initializing git wrapper for path {project_path}")
        self.project_path = project_path
        self.repo: Optional[git.Repo] = None
        self.repo_load_ok = False

        try:
            self.repo = git.Repo(project_path)
            self.repo_load_ok = True
        except git.exc.InvalidGitRepositoryError:
            logger.info(f"No git repository found at {project_path}, initializing new one")
            self.init_git(project_path)

        if not self.repo:
            raise ImportError(f"Failed to initialize git repository at {project_path}")

        # Setup worker thread
        self.git_thread = PyQt6.QtCore.QThread()
        self.git_worker = GitWorker()
        self.git_worker.moveToThread(self.git_thread)

        # Connect trigger signals to worker slots
        self.trigger_pull.connect(self.git_worker.do_pull)
        self.trigger_push.connect(self.git_worker.do_push)

        # Connect result signals
        self.git_worker.push_finished.connect(
            lambda: logger.info("Background push finished")
        )
        self.git_worker.push_failed.connect(
            lambda err: logger.error(f"Background push failed: {err}")
        )
        self.git_worker.pull_finished.connect(self.on_pull_finished)
        self.git_worker.pull_failed.connect(
            lambda err: logger.error(f"Background pull failed: {err}")
        )

        # Start thread
        self.git_thread.start()

        if self.repo_load_ok:
            logger.info("Repository loaded successfully")
            # Start initial pull asynchronously
            self.trigger_pull.emit(self.project_path)

    def on_pull_finished(self) -> None:
        """Called when background pull completes."""
        logger.info("Background pull finished")
        self._check_dirty_git()

    def _check_dirty_git(self) -> None:
        """Check if git repository has uncommitted changes and commit them."""
        if not self.repo:
            return

        logger.info("Checking if git is dirty")
        if self.repo.is_dirty():
            logger.warning("Git repository has uncommitted changes")
            try:
                diffs = self.repo.index.diff(None)
                for diff in diffs:
                    if diff.a_path:
                        self.update_file(diff.a_path)
            except Exception as e:
                logger.error(f"Error checking dirty files: {e}")

    def init_git(self, project_path: str) -> None:
        """
        Initialize a new git repository.

        Args:
            project_path: Path where to initialize the repository
        """
        logger.info(f"Initializing git in path {project_path}")
        self.repo = git.Repo.init(project_path)

        # Copy template .gitignore
        script_dir = pathlib.Path(__file__).parent.resolve()
        template_gitignore = script_dir / "data" / "template_gitignore"
        target_gitignore = pathlib.Path(project_path) / ".gitignore"

        try:
            if template_gitignore.exists():
                logger.info(f"Copying gitignore {template_gitignore} -> {target_gitignore}")
                shutil.copy(template_gitignore, target_gitignore)
                self.repo.index.add([str(target_gitignore)])
            else:
                logger.warning(f"Template gitignore not found at {template_gitignore}")

            self.repo.index.commit("Initial commit")
            self.repo_load_ok = True
        except Exception as e:
            logger.error(f"Error during git initialization: {e}")
            raise

    def add_file(self, file_name: str) -> None:
        """
        Add a new file to git and commit.

        Args:
            file_name: Relative path of the file to add
        """
        if not self.repo:
            logger.error("Repository not initialized")
            return

        logger.info(f"Adding file {file_name} to git")
        try:
            self.repo.index.add([file_name])
            self.repo.index.commit(f"Add file {file_name}")
            self.push()
        except Exception as e:
            logger.error(f"Error adding file {file_name}: {e}")

    def update_file(self, file_name: str) -> None:
        """
        Update an existing file in git and commit.

        Args:
            file_name: Relative path of the file to update
        """
        if not self.repo:
            logger.error("Repository not initialized")
            return

        logger.info(f"Updating file {file_name}")
        try:
            self.repo.index.add([file_name])
            self.repo.index.commit(f"Update file {file_name}")
            self.push()
        except Exception as e:
            logger.error(f"Error updating file {file_name}: {e}")

    def push(self) -> None:
        """Trigger background push operation."""
        logger.debug("Triggering background push...")
        self.trigger_push.emit(self.project_path)

    def list_all_files(self) -> List[str]:
        """
        List all files tracked by git.

        Returns:
            List of file paths relative to repository root
        """
        if not self.repo:
            logger.error("Repository not initialized")
            return []

        try:
            files = self.repo.git.ls_files().split('\n')
            return [f for f in files if f]  # Filter empty strings
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []

    def get_commit_log(self, max_count: int = 50) -> str:
        """
        Get formatted commit log.

        Args:
            max_count: Maximum number of commits to retrieve

        Returns:
            Formatted string with commit history
        """
        if not self.repo_load_ok or not self.repo:
            return "Git repository not loaded."

        try:
            log_format = "%h %ad | %s (%an)"
            date_format = "%Y-%m-%d %H:%M"
            log_string = self.repo.git.log(
                f"--pretty=format:{log_format}",
                f"--date=format:{date_format}",
                f"-n{max_count}"
            )
            return log_string
        except Exception as e:
            logger.error(f"Error retrieving git log: {e}")
            return f"Error retrieving log:\n{e}"

    def cleanup(self) -> None:
        """
        Clean shutdown of git thread. Must be called when closing the application.
        """
        logger.info("Shutting down Git thread...")

        # Disconnect all signals to prevent further operations
        try:
            self.trigger_pull.disconnect()
            self.trigger_push.disconnect()
        except TypeError:
            pass  # Already disconnected

        # Request thread to quit
        self.git_thread.quit()

        # Wait with timeout
        if not self.git_thread.wait(5000):  # 5 seconds timeout
            logger.warning("Git thread did not stop gracefully, terminating...")
            self.git_thread.terminate()
            self.git_thread.wait(1000)  # Wait 1 more second after terminate

        logger.info("Git thread shut down successfully")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Testing NoteGit...")

    # Example usage
    test_path = "/tmp/test_notebook"
    pathlib.Path(test_path).mkdir(exist_ok=True)

    git_wrapper = NoteGit(test_path)
    print(f"Files: {git_wrapper.list_all_files()}")

    # Cleanup
    git_wrapper.cleanup()
