import datetime
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
    nav_link_clicked_internal_signal = PySignal.Signal()
    nav_link_clicked_external_signal = PySignal.Signal()

    def acceptNavigationRequest(self, url, _type, isMainFrame):
        if _type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            logger.debug("url clicked: {}".format(url))
            if not url.isValid() or url.isEmpty():
                logger.warning("url error")
                return False
            if url.isLocalFile():
                logger.debug("emit signal to handle local file")
                self.nav_link_clicked_internal_signal.emit(url)
                return False
            logger.debug("emit signal for external url")
            self.nav_link_clicked_external_signal.emit(url)
            return False
        return super().acceptNavigationRequest(url, _type, isMainFrame)


class Notebook(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # init later used variables
        self.config_filename = False
        self.data = {}
        # init up elements
        self.project_drop_down = QtWidgets.QComboBox()
        self.search_box = QtWidgets.QComboBox()
        #
        self.setWindowTitle('Notebook')
        # todo icon ?
        # config
        self.read_config()
        # web
        self.web_engine_view = QWebEngineView()
        self.web_page = NotebookPage(self)
        self.web_page.nav_link_clicked_internal_signal.connect(self.on_internal_url)
        self.web_page.nav_link_clicked_external_signal.connect(self.on_external_url)
        self.web_engine_view.setPage(self.web_page)
        # init
        self.init_ui()
        while not self.data.get("projects", {}):
            self.create_new_project()
        if not self.data.get("last_project"):
            self.data.update({"last_project": list(self.data.get("projects").keys())[0]})
        project_name = self.data.get("last_project")
        self.load_page(self.data.get("projects", {}).get(project_name, {}).get("last_ascii_file", None))
        self.edit_page_window = EditPage(project_data=self.data.get("projects", {}).get(project_name, {}), project_name=project_name,
                                         file_name=self.data.get("projects", {}).get(project_name, {}).get("last_ascii_file", None))

    def on_external_url(self, url):
        reply = QtWidgets.QMessageBox.question(self, "Proceed",
                    "Are you sure you want to open the url '{}' in an external browser".format(url),
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            logger.debug("open link in external browser")
            QtGui.QDesktopServices.openUrl(url)
        return

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
        vbox = QtWidgets.QVBoxLayout()
        hbox = QtWidgets.QHBoxLayout()
        hbox2 = QtWidgets.QHBoxLayout()
        # projects from conf
        self.project_drop_down.setMinimumWidth(130)
        hbox.addWidget(self.project_drop_down)
        project_highlight = self.data.get("last_project", "")
        for project_name in list(self.data.get("projects",{}).keys()):
            if not project_highlight:
                project_highlight = project_name
            self.project_drop_down.addItem(project_name)
        # todo: highlight right project in dropdown box
        # search box
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
        export_button = QtWidgets.QPushButton("Export", self)
        hbox2.addWidget(export_button)
        export_button.clicked.connect(self.on_export_pdf)
        # edit btn
        edit_page_button = QtWidgets.QPushButton("Edit Page", self)
        hbox2.addWidget(edit_page_button)
        edit_page_button.clicked.connect(self.on_click_edit_page)
        # update page
        page_back_btn = QtWidgets.QPushButton("Back", self)
        hbox2.addWidget(page_back_btn)
        page_back_btn.clicked.connect(self.on_back_btn)
        # settings
        vbox.addLayout(hbox)
        vbox.addLayout(hbox2)
        #vbox.addLayout(breadcrumb_widget)
        vbox.addWidget(self.web_engine_view)
        main_widget = QtWidgets.QWidget()
        main_widget.setLayout(vbox)
        self.setCentralWidget(main_widget)
        self.setGeometry(300, 300, 350, 250)
        self.resize(900, 500)
        logger.info("Main window widgets created")

    def load_page(self, file_name=None):
        if not file_name:
            file_name = self.data.get("index_file", "index.asciidoc")
        project_name = self.project_drop_down.currentText()
        logger.info("Loading page {} from project {}".format(file_name, project_name))
        project = self.data.get("projects").get(project_name)
        if file_name.split(".")[-1].lower() not in ["adoc", "asciidoc"]:
            return
        ascii_file_name = os.path.join(project.get("path"), file_name)
        logger.info("Loading page {}".format(ascii_file_name))
        try:
            with open(ascii_file_name, "r") as ascii_file:
                text_in = ascii_file.read()
        except FileNotFoundError:
            logger.warning("file {} not found".format(ascii_file_name))
            text_in = "== empty page\n"
            try:
                with open(ascii_file_name, "w") as ascii_file:
                    ascii_file.write(text_in)
            except FileNotFoundError:
                logger.error("problem writing new file {}".format(ascii_file_name))
                return
        html_text = text_2_html(text_in)
        html_file_name = "{}.html".format(ascii_file_name)
        try:
            with open(html_file_name, "w") as html_file:
                html_file.write(html_text)
        except FileNotFoundError:
            logger.error("problem writing new file {}".format(html_file_name))
            return
        self.web_page.load(QUrl("file://{}".format(html_file_name)))
        #
        # todo: check for later to include other files like html/ pdf in direct loading
        # or open in external program
        #
        # if file_name.split(".")[-1].lower() in ["htm", "html", "txt", "pdf"]:
        #     chrome_file_name = os.path.join(project.get("path"), file_name)
        #     logger.info("other files than adoc: {}".format(chrome_file_name))
        #     self.web_page.load(QUrl("file://{}".format(chrome_file_name)))

    def on_click_edit_page(self):
        logger.info("edit clicked")
        project_name = self.project_drop_down.currentText()
        project = self.data.get("projects").get(project_name)
        file_name = self.web_page.url().fileName()
        if file_name.endswith(".html"):
            file_name = file_name[:-5]
        path_project = self.data.get("projects", {}).get(self.project_drop_down.currentText(), {}).get("path", "")
        path_url_str = str(os.path.split(self.web_page.url().path())[0])
        if path_url_str.startswith(path_project):
            logger.info("url starts with {}".format(path_project))
            if path_url_str > path_project:
                logger.info("recreate relative project path")
                cut_length = len(path_project) + 1
                if path_project.endswith("/"):
                    cut_length = cut_length - 1
                prefix = path_url_str[cut_length:]
                file_name = "{}/{}".format(prefix, file_name)
            if file_name.split(".")[-1] in ["adoc", "asciidoc"]:
                logger.info("edit page {}".format(file_name))
                self.edit_page_window.ascii_file_changed.disconnect(self.load_page)
                self.edit_page_window.project_data_changed.disconnect(self.project_data_update)
                self.edit_page_window = EditPage(project_data=project, project_name=project_name, file_name=file_name)
                self.edit_page_window.show()
                self.edit_page_window.ascii_file_changed.connect(self.load_page)
                self.edit_page_window.project_data_changed.connect(self.project_data_update)
        else:
            logger.error("path {} <-mismatch-> url {}".format(path_project, path_url_str))

    def project_data_update(self, project_data):
        project_name = self.project_drop_down.currentText()
        logger.info("update project data for {}".format(project_name))
        self.data.get("projects").update({project_name: project_data})

    def on_internal_url(self, url):
        logger.info("open new local url {}".format(url))
        file_name = url.fileName()
        path = url.path()
        path_project = self.data.get("projects", {}).get(self.project_drop_down.currentText(), {}).get("path", "")
        path_url_str = str(os.path.split(path)[0])
        if path_url_str.startswith(path_project):
            logger.info("starts with")
            if path_url_str > path_project:
                logger.info("recreate relative project path")
                cut_length = len(path_project)+1
                if path_project.endswith("/"):
                    cut_length = cut_length -1
                prefix = path_url_str[cut_length:]
                file_name = "{}/{}".format(prefix, file_name)
            logger.info("load page")
            self.load_page(file_name)
        else:
            logger.error("path {} <-mismatch-> url {}".format(path_project, path_url_str))

    def on_back_btn(self):
        logger.info("hit back btn")
        self.web_page.triggerAction(QWebEnginePage.WebAction.Back)

    def on_export_pdf(self):
        logger.info("hit export")
        file_name = self.web_page.url().fileName()
        export_dir = os.path.expanduser("~")
        if os.name in ["nt", "windows"]:
            export_dir = os.path.join(export_dir, "Downloads")
        else:
            export_dir = os.path.join(export_dir, "Downloads")
        export_dir = self.data.get("export_dir", export_dir)
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        file_name = "{}_{}.pdf".format(date_str, file_name)
        file_name = os.path.join(export_dir, file_name)
        pdf_file = QtWidgets.QFileDialog.getSaveFileName(self, "Save PDF file", file_name, "PDF (*.pdf)")
        if pdf_file:
            pdf_file = pdf_file[0]
            if pdf_file:
                self.web_engine_view.page().printToPdf(pdf_file)
                logger.info("page exported to {}".format(pdf_file))
                self.data.update({"export_dir": os.path.split(pdf_file)[0]})
            else:
                logger.warning("could not export")
        else:
            logger.warning("could not export")

    @pyqtSlot(QtGui.QCloseEvent)
    def closeEvent(self, event):
        logger.info("Closing the notebook window")
        self.write_config()
        self.web_engine_view.setPage(None)
        self.web_engine_view = None
        self.web_page = None
        self.edit_page_window.close()
        self.edit_page_window = None


def text_2_html(text_in):
    # print("convert asciidoc text")
    text_out = io.StringIO()
    test = asciidoc.AsciiDocAPI()
    test.execute(io.StringIO(text_in), text_out, backend="html5")
    return text_out.getvalue()

class NotebookApp:
    def __init__(self):
        self.app = QtWidgets.QApplication(sys.argv)
        self.notes = Notebook()

    def run(self):
        self.notes.show()
        self.app.exec()


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)

    logger.info("moin")

    multi_window = NotebookApp()
    multi_window.run()
