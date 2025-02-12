import datetime
import hashlib
import json
import logging
import os
import pathlib
import sys
import time

import PySignal

import PyQt6
import PyQt6.QtCore
import PyQt6.QtGui
import PyQt6.QtWidgets
import PyQt6.QtWebEngineCore
import PyQt6.QtWebEngineWidgets

import editpage
import notegit
import notehelper


logger = logging.getLogger(__name__)


class NotebookPage(PyQt6.QtWebEngineCore.QWebEnginePage):
    """ Custom WebEnginePage to customize how we handle link navigation """
    nav_link_clicked_internal_signal = PySignal.Signal()
    nav_link_clicked_external_signal = PySignal.Signal()

    def acceptNavigationRequest(self, url, _type, isMainFrame):
        if _type == PyQt6.QtWebEngineCore.QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
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


class Notebook(PyQt6.QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # init later used variables
        self.config_filename = False
        self.data = {}
        # init up elements
        self.project_drop_down = PyQt6.QtWidgets.QComboBox()
        self.search_box = PyQt6.QtWidgets.QComboBox()
        self.setWindowTitle('Notebook')
        # todo icon ?
        # config
        self.read_config()
        # web
        self.web_engine_view = PyQt6.QtWebEngineWidgets.QWebEngineView()
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
        project_name = self.data.get("last_project", self.project_drop_down.currentText())
        try:
            self.repo = notegit.NoteGit(self.data.get("projects", {}).get(project_name, {}).get("path", ""))
        except ImportError:
            PyQt6.QtWidgets.QMessageBox("Error Project {} with Path {} not fould. Project removed from config".format(project_name, self.data.get("projects", {}).get(project_name, {}).get("path", "")))
            self.data.get("projects", {}).pop(project_name, None)
        self.load_page(self.data.get("projects", {}).get(project_name, {}).get("last_ascii_file", ""))
        self.edit_page_window = editpage.EditPage(project_data=self.data.get("projects", {}).get(project_name, {}), project_name=project_name,
                                         file_name=self.data.get("projects", {}).get(project_name, {}).get("last_ascii_file", ""))

    def on_external_url(self, url):
        reply = PyQt6.QtWidgets.QMessageBox.question(self, "Proceed",
                    "Are you sure you want to open the url '{}' in an external browser".format(url),
                    PyQt6.QtWidgets.QMessageBox.StandardButton.Yes | PyQt6.QtWidgets.QMessageBox.StandardButton.No,
                    PyQt6.QtWidgets.QMessageBox.StandardButton.No)
        if reply == PyQt6.QtWidgets.QMessageBox.StandardButton.Yes:
            logger.debug("open link {} in external browser".format(url))
            PyQt6.QtGui.QDesktopServices.openUrl(url)
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
            with open(self.config_filename, "r", encoding="utf-8") as config_file:
                data = json.load(config_file)
        except IOError as err:
            logger.warning("Oops, error: {}".format(err))
            data = {}
        self.data = data

    def write_config(self):
        logger.info("writing logs")
        try:
            with open(self.config_filename, "w", encoding="utf-8") as config_file:
                json.dump(self.data, config_file, indent=4)
        except Exception as e:
            logger.error("writing config to file error: {}".format(e))

    def create_new_project(self):
        logger.debug("create new project")
        project_path = PyQt6.QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory")
        if project_path:
            project_name = os.path.split(project_path)[1]
            if self.data.get("projects", {}).get(project_name, False):
                PyQt6.QtWidgets.QMessageBox.information(self, "Add Project", "Das Projekt is bereits in der Liste")
                logger.error("Das Projekt is bereits in der Liste")
                return
            else:
                index_file = self.data.get("index_file", "index.asciidoc")
                self.data.update({"index_file": index_file})
                filepath = os.path.join(project_path, index_file)
                if os.path.exists(filepath):
                    logger.info("filepath {} found, opening index {}".format(filepath, index_file))
                else:
                    with open(filepath, "w", encoding="utf-8") as text_file:
                        text_str = "== new project {}\n\nasciidoc format\nlink:https://docs.asciidoctor.org/asciidoc/latest/syntax-quick-reference/[link quick reference guide asciidoc]\n".format(project_name)
                        text_file.write(text_str)
                        logger.error("new index file created {}".format(filepath))
            projects = self.data.get("projects", {})
            projects.update({project_name: {"path": project_path, "create_date": time.time(),
                                            "last_ascii_file": self.data.get("index_file", "index.asciidoc")}})
            self.data.update({"projects": projects})
            self.data.update({"last_project": project_name})
            self.project_drop_down.addItem(project_name)
            self.repo = notegit.NoteGit(project_path)
            self.repo.add_file(self.data.get("index_file", "index.asciidoc"))
            self.load_page()

    def on_project_change(self):
        new_project_name = self.project_drop_down.currentText()
        logger.info("dropdown project change to {}".format(new_project_name))
        self.data.update({"last_project": new_project_name})
        self.repo = notegit.NoteGit(self.data.get("projects", {}).get(new_project_name, {}).get("path", None))
        self.load_page()

    def init_ui(self):
        vbox = PyQt6.QtWidgets.QVBoxLayout()
        hbox = PyQt6.QtWidgets.QHBoxLayout()
        hbox2 = PyQt6.QtWidgets.QHBoxLayout()
        # projects from conf
        self.project_drop_down.setMinimumWidth(130)
        hbox.addWidget(self.project_drop_down)
        project_highlight = self.data.get("last_project", "")
        for project_name in list(self.data.get("projects",{}).keys()):
            if not project_highlight:
                project_highlight = project_name
            self.project_drop_down.addItem(project_name)
        self.project_drop_down.setCurrentText(project_highlight)
        self.project_drop_down.currentTextChanged.connect(self.on_project_change)
        # search box
        self.search_box.setEditable(True)
        self.search_box.setInsertPolicy(PyQt6.QtWidgets.QComboBox.InsertPolicy.NoInsert)
        # todo find correct parent for shortcut
        # shortcut = PyQt6.QtGui.QShortcut(PyQt6.QtGui.QKeySequence(PyQt6.QtCore.Qt.Key.Key_Return), self.search_box, activated=self.on_click_search)
        hbox.addWidget(self.search_box)
        self.search_box.currentTextChanged.connect(self.on_search_local)
        # search btn
        search_button = PyQt6.QtWidgets.QPushButton("🔎")
        hbox.addWidget(search_button)
        search_button.clicked.connect(self.on_click_search)
        # open git btn
        open_git_button = PyQt6.QtWidgets.QPushButton("Commits")
        hbox.addWidget(open_git_button)
        # open_git_button.clicked.connect(self.open_git)
        # add/ new btn
        add_project_button = PyQt6.QtWidgets.QPushButton('Add/ New Project', self)
        hbox2.addWidget(add_project_button)
        add_project_button.clicked.connect(self.create_new_project)
        # export btn
        export_button = PyQt6.QtWidgets.QPushButton("Export", self)
        hbox2.addWidget(export_button)
        export_button.clicked.connect(self.on_export_pdf)
        # edit btn
        edit_page_button = PyQt6.QtWidgets.QPushButton("Edit Page", self)
        hbox2.addWidget(edit_page_button)
        edit_page_button.clicked.connect(self.on_click_edit_page)
        # update page
        page_back_btn = PyQt6.QtWidgets.QPushButton("Back", self)
        hbox2.addWidget(page_back_btn)
        page_back_btn.clicked.connect(self.on_back_btn)
        # settings
        vbox.addLayout(hbox)
        vbox.addLayout(hbox2)
        # vbox.addLayout(breadcrumb_widget)
        vbox.addWidget(self.web_engine_view)
        main_widget = PyQt6.QtWidgets.QWidget()
        main_widget.setLayout(vbox)
        self.setCentralWidget(main_widget)
        geometry = self.data.get("geometry", [300, 250, 900, 600])
        self.setGeometry(geometry[0], geometry[1], geometry[2], geometry[3])
        logger.info("Main window widgets created")

    def on_search_local(self):
        search_text = self.search_box.currentText()
        self.web_page.findText(search_text)

    def on_click_search(self):
        search_text = self.search_box.currentText().lower()
        logger.info("search clicked for text {}".format(search_text))
        if not search_text:
            return
        project_path = self.data.get("projects",{}).get(self.project_drop_down.currentText(), {}).get("path", "")
        if not project_path:
            logger.warning("no project path found")
            return
        if self.search_box.findText(search_text) < 0:
            self.search_box.addItem(search_text)
        search_file_name = hashlib.md5(search_text.encode("utf-8")).hexdigest()
        search_file_name = os.path.join(project_path, "search-{}.html".format(search_file_name))
        search_file_name = os.path.normpath(search_file_name)
        if not os.path.exists(search_file_name):
            search_result = notehelper.search_files(search_text, self.repo.list_all_files(), project_path)
            html_text = notehelper.text_2_html(search_result)
            try:
                with open(search_file_name, "w", encoding="utf-8") as html_file:
                    html_file.write(html_text)
            except FileNotFoundError:
                logger.error("problem writing new file {}".format(search_file_name))
                return
        self.web_page.load(PyQt6.QtCore.QUrl(pathlib.Path(search_file_name).absolute().as_uri()))

    def load_page(self, file_name=None):
        if not file_name:
            file_name = self.data.get("index_file", "index.asciidoc")
        project_name = self.project_drop_down.currentText()
        logger.info("Loading page {} from project {}".format(file_name, project_name))
        project = self.data.get("projects").get(project_name)
        #
        # open files in webview
        if file_name.split(".")[-1].lower() in ["htm", "html", "txt", "jpg", "png", "jpeg"]:
            chrome_file_name = os.path.join(project.get("path"), file_name)
            chrome_file_name = os.path.normpath(chrome_file_name)
            logger.info("open other files in webview: {}".format(chrome_file_name))
            self.web_page.load(PyQt6.QtCore.QUrl(pathlib.Path(chrome_file_name).absolute().as_uri()))
            return
        #
        # open pdf in extern
        if file_name.split(".")[-1].lower() in ["pdf", "ppt", "doc", "docx"]:
            pdf_file_name = os.path.join(project.get("path"), file_name)
            # pdf_file_name = os.path.normpath(pdf_file_name)
            logger.info("open pdf in extern: {}".format(pdf_file_name))
            self.on_external_url(PyQt6.QtCore.QUrl(pathlib.Path(pdf_file_name).absolute().as_uri()))
            return
        #
        # dont open rest
        if file_name.split(".")[-1].lower() not in ["adoc", "asciidoc"]:
            return
        ascii_file_name = os.path.join(project.get("path"), file_name)
        ascii_file_name = os.path.normpath(ascii_file_name)
        logger.info("Loading page {}".format(ascii_file_name))
        try:
            with open(ascii_file_name, "r", encoding="utf-8") as ascii_file:
                text_in = ascii_file.read()
        except FileNotFoundError:
            logger.warning("file {} not found".format(ascii_file_name))
            text_in = "== empty page\n"
            if not os.path.exists(os.path.split(ascii_file_name)[0]):
                os.makedirs(os.path.split(ascii_file_name)[0])
            if os.path.isdir(os.path.split(ascii_file_name)[0]):
                logger.error("path {} not a directory".format(os.path.split(ascii_file_name)[0]))
            try:
                with open(ascii_file_name, "w", encoding="utf-8") as ascii_file:
                    ascii_file.write(text_in)
                    self.repo.add_file(file_name)
            except FileNotFoundError:
                logger.error("problem writing new file {}".format(ascii_file_name))
                return
        html_text = notehelper.text_2_html(text_in)
        html_file_name = "{}.html".format(ascii_file_name)
        try:
            with open(html_file_name, "w", encoding="utf-8") as html_file:
                html_file.write(html_text)
        except FileNotFoundError:
            logger.error("problem writing new file {}".format(html_file_name))
            return
        self.web_page.load(PyQt6.QtCore.QUrl(pathlib.Path(html_file_name).absolute().as_uri()))

    def on_file_edited(self, file_name):
        logger.info("git update {}".format(file_name))
        self.repo.update_file(file_name)

    def on_upload_file(self, file_name):
        logger.info("add uploaded file {} to git".format(file_name))
        self.repo.add_file(file_name)

    def on_click_edit_page(self):
        logger.info("edit clicked")
        project_name = self.project_drop_down.currentText()
        project = self.data.get("projects").get(project_name)
        file_name = self.web_page.url().fileName()
        if file_name.endswith(".html"):
            file_name = file_name[:-5]
        path_project = self.data.get("projects", {}).get(self.project_drop_down.currentText(), {}).get("path", "")
        path_url_str = str(os.path.split(self.web_page.url().path())[0])
        if path_url_str.startswith(str(pathlib.Path(path_project).absolute().as_uri())[7:]):
            logger.info("url starts with {}".format(path_project))
            if path_url_str > str(pathlib.Path(path_project).absolute().as_uri())[7:]:
                logger.info("recreate relative project path")
                cut_length = len(str(pathlib.Path(path_project).absolute().as_uri())[7:]) + 1
                if path_project.endswith("/"):
                    cut_length = cut_length - 1
                prefix = path_url_str[cut_length:]
                file_name = "{}/{}".format(prefix, file_name)
            if file_name.split(".")[-1] in ["adoc", "asciidoc"]:
                logger.info("edit page {}".format(file_name))
                self.edit_page_window.ascii_file_changed.disconnect(self.load_page)
                self.edit_page_window.ascii_file_changed.disconnect(self.on_file_edited)
                self.edit_page_window.project_new_file.disconnect(self.on_upload_file)
                self.edit_page_window.project_data_changed.disconnect(self.project_data_update)
                self.edit_page_window.geometry_update.disconnect(self.edit_page_window_geometry)
                self.edit_page_window = editpage.EditPage(project_data=project, project_name=project_name, file_name=file_name)
                geometry = self.data.get("edit_window_geometry", [300, 300, 600, 600])
                self.edit_page_window.set_geometry(geometry)
                self.edit_page_window.show()
                self.edit_page_window.ascii_file_changed.connect(self.load_page)
                self.edit_page_window.ascii_file_changed.connect(self.on_file_edited)
                self.edit_page_window.project_new_file.connect(self.on_upload_file)
                self.edit_page_window.geometry_update.connect(self.edit_page_window_geometry)
                self.edit_page_window.project_data_changed.connect(self.project_data_update)
        else:
            logger.error("path {} <-mismatch-> url {}".format(str(pathlib.Path(path_project).absolute().as_uri())[7:], path_url_str))

    def edit_page_window_geometry(self, geometry):
        # print(geometry)
        if os.name in ["nt", "windows"]:
            geometry = (geometry[0], geometry[1]+31, geometry[2], geometry[3]-31)
        # print(geometry)
        self.data.update({"edit_window_geometry": geometry})

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
        if path_url_str.startswith(str(pathlib.Path(path_project).absolute().as_uri())[7:]):
            logger.info("starts with {}".format(path_project))
            if path_url_str > str(pathlib.Path(path_project).absolute().as_uri())[7:]:
                logger.info("recreate relative project path")
                cut_length = len(str(pathlib.Path(path_project).absolute().as_uri())[7:])+1
                if path_project.endswith("/"):
                    cut_length = cut_length -1
                prefix = path_url_str[cut_length:]
                file_name = "{}/{}".format(prefix, file_name)
            logger.info("load page")
            self.load_page(file_name)
        else:
            logger.error("path {} <-mismatch-> url {}".format(str(pathlib.Path(path_project).absolute().as_uri())[7:], path_url_str))

    def on_back_btn(self):
        logger.info("hit back btn")
        self.web_page.triggerAction(PyQt6.QtWebEngineCore.QWebEnginePage.WebAction.Back)

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
        pdf_file = PyQt6.QtWidgets.QFileDialog.getSaveFileName(self, "Save PDF file", file_name, "PDF (*.pdf)")
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

    @PyQt6.QtCore.pyqtSlot(PyQt6.QtGui.QCloseEvent)
    def closeEvent(self, event):
        if os.name in ["nt", "windows"]:
            geometry = (self.frameGeometry().x(), self.frameGeometry().y()+31, self.frameGeometry().width(), self.frameGeometry().height()-31)
        else:
            geometry = (self.frameGeometry().x(), self.frameGeometry().y(), self.frameGeometry().width(), self.frameGeometry().height())
        self.data.update({"geometry": geometry})
        logger.info("Closing the notebook window")
        self.write_config()
        self.web_engine_view.setPage(None)
        self.web_engine_view = None
        self.web_page = None
        self.edit_page_window.close()
        self.edit_page_window = None


class NotebookApp:
    def __init__(self):
        self.app = PyQt6.QtWidgets.QApplication(sys.argv)
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
