import os
import logging
import shutil

import git


logger = logging.getLogger(__name__)


class NoteGit:
    def __init__(self, project_path):
        logger.info("init git wrapper for path {}".format(project_path))
        try:
            self.repo = git.Repo(project_path)
            self.repo_load_ok = True
        except git.exc.InvalidGitRepositoryError:
            self.repo = None
            self.repo_load_ok = False
            self.init_git(project_path)

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
        self.repo.index.add(target_gitignore)
        self.repo.index.commit("initial commit")

    def add_file(self, file_name):
        logger.info("add file {} to git".format(file_name))
        self.repo.index.add(file_name)
        self.repo.index.commit("add file {}".format(file_name))

    def update_file(self, file_name):
        logger.info("update file {}".format(file_name))
        self.repo.index.commit("update file {}".format(file_name))


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)

    logger.info("moin")

    gittest = NoteGit("/home/ecki/tmp2/notebooks/test1")
    gittest.update_file(".gitignore")
