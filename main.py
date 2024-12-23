import io
import json
import os
import sys
import time

import asciidoc
import PySignal

from PyQt6 import QtWidgets, QtGui
from PyQt6.QtCore import pyqtSlot, QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView
import logging

from editpage import EditPage


logger = logging.getLogger(__name__)


class NotebookPage(QWebEnginePage):
    """ Custom WebEnginePage to customize how we handle link navigation """
    nav_link_clicked_signal = PySignal.Signal()

    def acceptNavigationRequest(self, url, _type, isMainFrame):
        logger.info("accept navigation - type {}".format(_type))
        #logger.info("accept navigation - url {}".format(url))
        #logger.info("accept navigation - main {}".format(isMainFrame))

        if _type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            logger.info("url clicked: {}".format(url))
            if not url.isValid() or url.isEmpty():
                return False
            if url.isLocalFile():
                self.nav_link_clicked_signal.emit(url)
                return False
            # Keep reference to external window, so it isn't cleared up.
            # self.external_windows.append(w)
            QtGui.QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, _type, isMainFrame)


class Notebook(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        # init later used variables
        self.config_filename = False
        self.data = {}
        # init up elements
        self.project_drop_down = QtWidgets.QComboBox()
        self.search_box = QtWidgets.QComboBox()
        self.breadcrumb_label = QtWidgets.QLabel()
        # config
        self.read_config()
        # web
        self.web_engine_view = QWebEngineView()
        self.web_page = NotebookPage(self)
        self.web_page.nav_link_clicked_signal.connect(self.on_click_nav_link)
        self.web_engine_view.setPage(self.web_page)
        # init
        self.init_ui()
        while not self.data.get("projects", {}):
            self.create_new_project()
        if not self.data.get("last_project"):
            self.data.update({"last_project": list(self.data.get("projects").keys())[0]})
        project_name = self.data.get("last_project")
        self.load_page(self.data.get("projects", {}).get(project_name, {}).get("last_ascii_file", None))

    def read_config(self):
        home_dir = os.path.expanduser("~")
        if os.name in ["nt", "windows"]:
            home_dir = os.path.join(home_dir, "AppData\\Local\\ThaNote")
        else:
            home_dir = os.path.join(home_dir, ".config/ThaNote")
        if not os.path.exists(home_dir):
            os.makedirs(home_dir)
        self.config_filename = os.path.join(home_dir, "config.json")
        logger.debug("open {}".format(self.config_filename))
        try:
            with open(self.config_filename, "r") as config_file:
                data = json.load(config_file)
        except IOError as err:
            logger.warning("Oops, error: {}".format(err))
            data = {}
        self.data = data

    def write_config(self):
        with open(self.config_filename, "w") as config_file:
            json.dump(self.data, config_file, indent=4)

    def create_new_project(self):
        logger.debug("create new project")
        project_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory")
        if project_path:
            project_name = os.path.split(project_path)[1]
            if self.data.get("projects", {}).get(project_name, False):
                QtWidgets.QMessageBox.information(self, "Add Project", "Das Projekt is bereits in der Liste")
                logger.error("Das Projekt is bereits in der Liste")
                return
            else:
                index_file = self.data.get("index_file", "index.asciidoc")
                self.data.update({"index_file": index_file})
                filepath = os.path.join(project_path, index_file)
                if os.path.exists(filepath):
                    logger.info("filepath {} found, opening index {}".format(filepath, index_file))
                else:
                    with open(filepath, "w") as text_file:
                        text_str = "== new project {}\n\nasciidoc format\n".format(project_name)
                        text_file.write(text_str)
                        logger.error("new index file created {}".format(filepath))
            projects = self.data.get("projects", {})
            projects.update({project_name: {"path": project_path, "create_date": time.time(),
                                            "last_ascii_file": self.data.get("index_file", "index.asciidoc")}})
            self.data.update({"projects": projects})
            self.data.update({"last_project": project_name})
            self.project_drop_down.addItem(project_name)
            self.load_page(self.data.get("index_file", "index.asciidoc"))

    def init_ui(self):
        vbox = QtWidgets.QVBoxLayout(self)
        hbox = QtWidgets.QHBoxLayout()
        hbox2 = QtWidgets.QHBoxLayout()
        # projects from conf
        self.project_drop_down = QtWidgets.QComboBox()
        self.project_drop_down.setMinimumWidth(130)
        hbox.addWidget(self.project_drop_down)
        project_highlight = self.data.get("last_project", "")
        for project_name in list(self.data.get("projects",{}).keys()):
            if not project_highlight:
                project_highlight = project_name
            self.project_drop_down.addItem(project_name)
        # todo: highlight right project in dropdown box
        # search box
        self.search_box = QtWidgets.QComboBox()
        self.search_box.setEditable(True)
        hbox.addWidget(self.search_box)
        # search btn
        search_button = QtWidgets.QPushButton("🔎")
        hbox.addWidget(search_button)
        # search_button.clicked.connect(self.on_click_search)
        # open git btn
        open_git_button = QtWidgets.QPushButton("Commits")
        hbox.addWidget(open_git_button)
        # open_git_button.clicked.connect(self.open_git)
        # add btn
        add_project_button = QtWidgets.QPushButton('Add Project', self)
        hbox2.addWidget(add_project_button)
        # add_project_button.clicked.connect(self.on_click_add_project)
        # new btn
        new_project_button = QtWidgets.QPushButton('New Project', self)
        hbox2.addWidget(new_project_button)
        # new_project_button.clicked.connect(self.on_click_new_project)
        # export btn
        export_button = QtWidgets.QPushButton('Export', self)
        hbox2.addWidget(export_button)
        # export_button.clicked.connect(self.on_export_pdf)
        # edit btn
        edit_page_button = QtWidgets.QPushButton('Edit Page', self)
        hbox2.addWidget(edit_page_button)
        edit_page_button.clicked.connect(self.on_click_edit_page)
        # update page
        update_current_page_btn = QtWidgets.QPushButton("🔄")
        hbox2.addWidget(update_current_page_btn)
        # update_current_page_btn.clicked.connect(self.update_current_page)
        # settings
        self.breadcrumb_label = QtWidgets.QLabel()
        breadcrumb_widget = QtWidgets.QHBoxLayout()
        breadcrumb_widget.addWidget(self.breadcrumb_label)
        vbox.addLayout(hbox)
        vbox.addLayout(hbox2)
        #vbox.addLayout(breadcrumb_widget)
        vbox.addWidget(self.web_engine_view)
        self.setLayout(vbox)
        self.setGeometry(300, 300, 350, 250)
        self.resize(900, 500)
        self.setWindowTitle('QWebEngineView')
        self.show()
        logger.info("Main window widgets created")

    def load_page(self, file_name=None):
        if not file_name:
            file_name = self.data.get("index_file", "index.asciidoc")
        project_name = self.project_drop_down.currentText()
        logger.info("Loading page {} from project {}".format(project_name, file_name))
        project = self.data.get("projects").get(project_name)
        ascii_file_name = os.path.join(project.get("path"), file_name)
        logger.info("Loading page {}".format(ascii_file_name))
        try:
            with open(ascii_file_name, "r") as ascii_file:
                text_in = ascii_file.read()
        except FileNotFoundError:
            text_in = "== empty page\n"
            with open(ascii_file_name, "w") as ascii_file:
                ascii_file.write(text_in)
        html_text = text_2_html(text_in)
        html_file_name = "{}.html".format(ascii_file_name)
        with open(html_file_name, "w") as html_file:
            html_file.write(html_text)
        self.web_page.load(QUrl("file://{}".format(html_file_name)))

    def on_click_edit_page(self):
        project_name = self.project_drop_down.currentText()
        project = self.data.get("projects").get(project_name)
        file_name = "index.asciidoc"
        path_project = self.data.get("projects", {}).get(self.project_drop_down.currentText(), {}).get("path", "")
        path_url_str = str(self.web_page.url().path())
        if path_url_str.startswith(path_project):
            logger.info("starts with")
            if path_url_str > path_project:
                logger.info("recreate relative project path")
                suffix = path_url_str[len(path_project):]
                file_name = "{}/{}".format(suffix, file_name)
            if file_name.split(".")[-1] in ["adoc", "asciidoc"]:
                logger.info("load page")
                # edit_page_window = EditPage(project_data=project, project_name=project_name, file_name=file_name)
                # edit_page_window.show()
                # self.edit_page_window.window_closed_sygnal.connect(self.update_current_page)
                # self.edit_page_window.show()
        else:
            logger.error("path {} <-mismatch-> url {}".format(path_project, path_url_str))

    def on_click_nav_link(self, url):
        logger.info("open new local url {}".format(url))
        file_name = url.fileName()
        path = url.path()
        path_project = self.data.get("projects", {}).get(self.project_drop_down.currentText(), {}).get("path", "")
        path_url_str = str(os.path.split(path)[0])
        if path_url_str.startswith(path_project):
            logger.info("starts with")
            if path_url_str > path_project:
                logger.info("recreate relative project path")
                suffix = path_url_str[len(path_project):]
                file_name = "{}/{}".format(suffix, file_name)
            if file_name.split(".")[-1] in ["adoc", "asciidoc"]:
                logger.info("load page")
                self.load_page(file_name)
        else:
            logger.error("path {} <-mismatch-> url {}".format(path_project, path_url_str))

    @pyqtSlot(QtGui.QCloseEvent)
    def closeEvent(self, event):
        logger.info("Closing the window")
        self.write_config()
        self.web_engine_view.setPage(None)
        self.web_engine_view = None
        self.web_page = None


def text_2_html(text_in):
    # print("convert asciidoc text")
    text_out = io.StringIO()
    test = asciidoc.AsciiDocAPI()
    test.execute(io.StringIO(text_in), text_out, backend="html5")
    return text_out.getvalue()


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)

    logger.info("moin")

    app = QtWidgets.QApplication(sys.argv)
    ex = Notebook()
    sys.exit(app.exec())
