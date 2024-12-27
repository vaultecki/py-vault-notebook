import git
import logging
import os
import shutil


logger = logging.getLogger(__name__)


class NoteGit:
    def __init__(self, project_path):
        logger.info("init git wrapper for path {}".format(project_path))
        try:
            self.repo = git.Repo(project_path)
            self.repo_load_ok = True
        except git.exc.InvalidGitRepositoryError:
            self.repo_load_ok = False
            self.init_git(project_path)
        if not self.repo:
            raise ImportError
        if self.repo:
            logger.info("repo exists")
            for remote in self.repo.remotes:
                try:
                    self.repo.remote(remote.name).pull()
                except git.exc.GitCommandError:
                    logger.warning("git error for remote {}".format(remote.name))
            self.__dirty_git()

    def __dirty_git(self):
        logger.info("check if git is dirty")
        if self.repo.is_dirty():
            logger.warning("git is dirty")
            # todo integrate unstaged files
            #unstaged_files = self.repo.untracked_files
            #for file_name in unstaged_files:
            #    print(file_name)
            diffs = self.repo.index.diff(None)
            for diff in diffs:
                self.update_file(diff.a_path)


    def init_git(self, project_path):
        logger.info("init git in path {}".format(project_path))
        self.repo = git.Repo.init(project_path)
        script_dir = os.path.abspath(os.path.dirname(__file__))
        template_dir = "data"
        template_gitignore = "template_gitignore"
        template_gitignore_abs_path = os.path.join(script_dir, template_dir)
        template_gitignore_abs_path = os.path.join(template_gitignore_abs_path, template_gitignore)
        target_gitignore = ".gitignore"
        target_gitignore_abs_path = os.path.join(project_path, target_gitignore)
        logger.info("copy gitignore {} -> {}".format(template_gitignore_abs_path, target_gitignore_abs_path))
        shutil.copy(template_gitignore_abs_path, target_gitignore_abs_path)
        self.repo_load_ok = True
        self.repo.index.add([target_gitignore])
        self.repo.index.commit("initial commit")

    def add_file(self, file_name):
        logger.info("add file {} to git".format(file_name))
        self.repo.index.add([file_name])
        self.repo.index.commit("add file {}".format(file_name))
        self.__push()

    def update_file(self, file_name):
        logger.info("update file {}".format(file_name))
        self.repo.index.add([file_name])
        self.repo.index.commit("update file {}".format(file_name))
        self.__push()

    def __push(self):
        for remote in self.repo.remotes:
            try:
                self.repo.remote(remote.name).push()
            except git.exc.GitCommandError:
                logger.warning("git error for remote {}".format(remote.name))

    def list_all_files(self):
        commits = self.repo.iter_commits(rev=self.repo.head.reference)
        files = []
        for commit in commits:
            # print(commit)
            git_files = self.repo.git.show("--pretty=", "--name-only", commit)
            git_files = git_files.split("\n")
            for file in git_files:
                if file not in files:
                    files.append(file)
        return files


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)

    logger.info("moin")

    gittest = NoteGit("/home/ecki/temp/notebooks/private")
