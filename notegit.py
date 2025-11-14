import git
import logging
import pathlib
import shutil
import PyQt6.QtCore

logger = logging.getLogger(__name__)


class GitWorker(PyQt6.QtCore.QObject):
    """
    Dieser Worker lebt in einem separaten Thread und führt
    langsame Git-Netzwerkoperationen aus.
    """
    # Signale für die Ergebnisse
    push_finished = PyQt6.QtCore.pyqtSignal()
    push_failed = PyQt6.QtCore.pyqtSignal(str)
    pull_finished = PyQt6.QtCore.pyqtSignal()
    pull_failed = PyQt6.QtCore.pyqtSignal(str)

    @PyQt6.QtCore.pyqtSlot(str)
    def do_pull(self, project_path):
        """ Führt 'git pull' für alle Remotes aus. """
        try:
            repo = git.Repo(project_path)
            for remote in repo.remotes:
                try:
                    logger.debug(f"Pulling from {remote.name} in background...")
                    repo.remote(remote.name).pull()
                except git.exc.GitCommandError as e:
                    logger.warning(f"Git pull error for remote {remote.name}: {e}")
                    # Fehler bei einem Remote muss nicht den ganzen Pull abbrechen
            self.pull_finished.emit()
        except Exception as e:
            logger.error(f"Failed to run background pull: {e}")
            self.pull_failed.emit(str(e))

    @PyQt6.QtCore.pyqtSlot(str)
    def do_push(self, project_path):
        """ Führt 'git push' für alle Remotes aus. """
        try:
            repo = git.Repo(project_path)
            for remote in repo.remotes:
                try:
                    logger.debug(f"Pushing to {remote.name} in background...")
                    repo.remote(remote.name).push()
                except git.exc.GitCommandError as e:
                    logger.warning(f"Git push error for remote {remote.name}: {e}")
            self.push_finished.emit()
        except Exception as e:
            logger.error(f"Failed to run background push: {e}")
            self.push_failed.emit(str(e))


class NoteGit(PyQt6.QtCore.QObject):
    # Signale, um den Worker im anderen Thread zu triggern
    trigger_push = PyQt6.QtCore.pyqtSignal(str)
    trigger_pull = PyQt6.QtCore.pyqtSignal(str)

    def __init__(self, project_path):
        # QObject __init__ aufrufen
        super().__init__()

        logger.info("init git wrapper for path {}".format(project_path))
        self.project_path = project_path  # Pfad speichern

        try:
            self.repo = git.Repo(project_path)
            self.repo_load_ok = True
        except git.exc.InvalidGitRepositoryError:
            self.repo_load_ok = False
            self.init_git(project_path)

        if not self.repo:
            raise ImportError

        self.git_thread = PyQt6.QtCore.QThread()
        self.git_worker = GitWorker()

        self.git_worker.moveToThread(self.git_thread)

        # Trigger-Signale mit den Slots des Workers verbinden
        self.trigger_pull.connect(self.git_worker.do_pull)
        self.trigger_push.connect(self.git_worker.do_push)

        # Ergebnis-Signale (optional) verbinden, z.B. für Logging
        self.git_worker.push_finished.connect(lambda: logger.info("Background push finished."))
        self.git_worker.push_failed.connect(lambda err: logger.error(f"Background push failed: {err}"))
        self.git_worker.pull_finished.connect(self.on_pull_finished)  # z.B. um __dirty_git zu starten

        # Thread starten
        self.git_thread.start()

        if self.repo_load_ok:
            logger.info("repo exists")
            # Starten Sie den ersten Pull asynchron
            self.trigger_pull.emit(self.project_path)
            # self.__dirty_git() wird jetzt von on_pull_finished aufgerufen

    def on_pull_finished(self):
        logger.info("Background pull finished.")
        self.__dirty_git()

    def __dirty_git(self):
        logger.info("check if git is dirty")
        if self.repo.is_dirty():
            logger.warning("git is dirty")
            diffs = self.repo.index.diff(None)
            for diff in diffs:
                self.update_file(diff.a_path)

    def init_git(self, project_path):
        logger.info("init git in path {}".format(project_path))
        self.repo = git.Repo.init(project_path)

        script_dir = pathlib.Path(__file__).parent.resolve()
        template_gitignore_abs_path = script_dir / "data" / "template_gitignore"
        target_gitignore_abs_path = pathlib.Path(project_path) / ".gitignore"

        logger.info(f"copy gitignore {template_gitignore_abs_path} -> {target_gitignore_abs_path}")
        shutil.copy(template_gitignore_abs_path, target_gitignore_abs_path)

        self.repo_load_ok = True
        self.repo.index.add([target_gitignore_abs_path])
        self.repo.index.commit("initial commit")

    def add_file(self, file_name):
        logger.info("add file {} to git".format(file_name))
        self.repo.index.add([file_name])
        self.repo.index.commit("add file {}".format(file_name))
        # Rufen Sie jetzt die asynchrone Push-Funktion auf
        self.push()  #

    def update_file(self, file_name):
        logger.info("update file {}".format(file_name))
        self.repo.index.add([file_name])
        self.repo.index.commit("update file {}".format(file_name))
        # Rufen Sie jetzt die asynchrone Push-Funktion auf
        self.push()  #

    def push(self):
        """ Umbenannt von __push. Löst den Background-Push aus. """
        logger.debug("Triggering background push...")
        self.trigger_push.emit(self.project_path)  #

    def list_all_files(self):
        files = self.repo.git.ls_files().split('\n')
        return files

    def cleanup(self):
        """ Diese Methode muss beim Schließen der App aufgerufen werden. """
        logger.info("Shutting down Git thread...")
        self.git_thread.quit()
        self.git_thread.wait()

    def get_commit_log(self, max_count=50):
        """ Ruft die letzten 'max_count' Commits als formatierten String ab. """
        if not self.repo_load_ok:
            return "Git-Repository nicht geladen."
        try:
            # --pretty=format:'...' ist ein Git-Befehl für schönes Logging
            log_format = "%h %ad | %s (%an)"
            date_format = "%Y-%m-%d %H:%M"
            log_string = self.repo.git.log(
                f"--pretty=format:{log_format}",
                f"--date=format:{date_format}",
                f"-n{max_count}"
            )
            return log_string
        except Exception as e:
            logger.error(f"Fehler beim Abrufen des Git-Logs: {e}")
            return f"Fehler beim Abrufen des Logs:\n{e}"


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)

    logger.info("moin")

    gittest = NoteGit("/home/ecki/temp/notebooks/private")
