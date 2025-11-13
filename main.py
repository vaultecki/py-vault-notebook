import datetime
import hashlib
import json
import logging
import os
import pathlib
import sys
import time

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
    nav_link_clicked_internal_signal = PyQt6.QtCore.pyqtSignal(PyQt6.QtCore.QUrl)
    nav_link_clicked_external_signal = PyQt6.QtCore.pyqtSignal(PyQt6.QtCore.QUrl)

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
        self.current_file_name = None
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
        # repo
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
        # edit window
        self.edit_page_window = editpage.EditPage()
        # connect edit window
        self.edit_page_window.ascii_file_changed.connect(self.load_page)
        self.edit_page_window.ascii_file_changed.connect(self.on_file_edited)
        self.edit_page_window.project_new_file.connect(self.on_upload_file)
        self.edit_page_window.geometry_update.connect(self.edit_page_window_geometry)
        self.edit_page_window.project_data_changed.connect(self.project_data_update)
        # start page
        self.load_page(self.data.get("projects", {}).get(project_name, {}).get("last_ascii_file", ""))

    def on_external_url(self, url):
        reply = PyQt6.QtWidgets.QMessageBox.question(self, "Proceed",
                    "Are you sure you want to open the url '{}' in an external browser".format(url),
                    PyQt6.QtWidgets.QMessageBox.StandardButton.Yes | PyQt6.QtWidgets.QMessageBox.StandardButton.No,
                    PyQt6.QtWidgets.QMessageBox.StandardButton.No)
        if reply == PyQt6.QtWidgets.QMessageBox.StandardButton.Yes:
            logger.debug("open link {} in external browser".format(url))
            PyQt6.QtGui.QDesktopServices.openUrl(url)
        return

    def open_editor_window(self, project_data, project_name, file_name):
        """ Lädt Daten in das bestehende Editorfenster und zeigt es an. """
        try:
            self.edit_page_window.load_document(
                project_data=project_data,
                project_name=project_name,
                file_name=file_name
            )

            geometry = self.data.get("edit_window_geometry", [300, 300, 600, 600])
            self.edit_page_window.set_geometry(geometry)
            self.edit_page_window.show()

        except Exception as e:
            logger.error(f"Failed to load document into editor: {e}")
            PyQt6.QtWidgets.QMessageBox.warning(self, "Fehler", f"Konnte Editor nicht laden: {e}")

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

        project_path = self.data.get("projects", {}).get(self.project_drop_down.currentText(), {}).get("path", "")
        if not project_path:
            logger.warning("no project path found")
            return

        base_url = PyQt6.QtCore.QUrl.fromLocalFile(project_path + os.path.sep)
        if self.search_box.findText(search_text) < 0:
            self.search_box.addItem(search_text)

        search_result = notehelper.search_files(search_text, self.repo.list_all_files(), project_path)
        html_text = notehelper.text_2_html(search_result)
        self.web_page.setHtml(html_text, base_url)

    def load_page(self, file_name=None):
        if not file_name:
            file_name = self.data.get("index_file", "index.asciidoc")
        project_name = self.project_drop_down.currentText()
        self.current_file_name = file_name
        logger.info("Loading page {} from project {}".format(file_name, project_name))

        project = self.data.get("projects").get(project_name)
        project_path = project.get("path")

        base_url = PyQt6.QtCore.QUrl.fromLocalFile(project_path + os.path.sep)
        full_file_path = os.path.join(project_path, file_name)
        full_file_path = os.path.normpath(full_file_path)
        file_extension = file_name.split(".")[-1].lower()

        # open some known extensions in webview
        if file_extension in ["htm", "html", "txt", "jpg", "png", "jpeg"]:
            logger.info("open other files in webview: {}".format(full_file_path))
            self.web_page.load(PyQt6.QtCore.QUrl(pathlib.Path(full_file_path).absolute().as_uri()))
            return

        # open pdf in extern
        if file_extension in ["pdf", "ppt", "doc", "docx"]:
            logger.info("open pdf in extern: {}".format(full_file_path))
            self.on_external_url(PyQt6.QtCore.QUrl(pathlib.Path(full_file_path).absolute().as_uri()))
            return
        #
        # open asciidoc as html
        if file_extension in ["adoc", "asciidoc"]:
            logger.info("Loading asciidoc page {}".format(full_file_path))
            try:
                with open(full_file_path, "r", encoding="utf-8") as ascii_file:
                    text_in = ascii_file.read()
            except FileNotFoundError:
                logger.warning("file {} not found, creating new".format(full_file_path))

                text_in = "== empty page\n"
                os.makedirs(os.path.split(full_file_path)[0], exist_ok=True)
                try:
                    with open(full_file_path, "w", encoding="utf-8") as ascii_file:
                        ascii_file.write(text_in)
                        self.repo.add_file(file_name)
                except IOError as e:
                    logger.error("problem writing new file {}: {}".format(full_file_path, e))
                    return

            html_text = notehelper.text_2_html(text_in)
            self.web_page.setHtml(html_text, base_url)

        return

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

        if not project:
            logger.error(f"Project '{project_name}' not found.")
            return

        if not self.current_file_name:
            logger.warning("No file is currently loaded to edit.")
            PyQt6.QtWidgets.QMessageBox.warning(self, "Fehler", "Keine Datei zum Bearbeiten geladen.")
            return

        file_name = self.current_file_name
        file_extension = file_name.split(".")[-1].lower()
        if file_extension in ["adoc", "asciidoc"]:
            logger.info("edit page {}".format(file_name))
            self.open_editor_window(project, project_name, file_name)
        else:
            logger.warning(f"Cannot edit file type: {file_extension}")
            PyQt6.QtWidgets.QMessageBox.information(self, "Hinweis",
                                                    f"Dateityp '{file_extension}' kann nicht bearbeitet werden.")

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
        try:
            project_path_str = self.data.get("projects", {}).get(self.project_drop_down.currentText(), {}).get("path",
                                                                                                               "")
            if not project_path_str:
                logger.error("No project path configured.")
                return

            project_path = pathlib.Path(project_path_str).absolute()
            url_path = pathlib.Path(url.toLocalFile())
            relative_path = url_path.relative_to(project_path)

            file_name = str(relative_path)
            logger.info(f"Load relative page: {file_name}")
            self.load_page(file_name)
        except ValueError:
            logger.error(f"Path {url_path} is not inside project path {project_path}")
        except Exception as e:
            logger.error(f"Error in on_internal_url: {e}")

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
            geometry = (self.frameGeometry().x(), self.frameGeometry().y() + 31, self.frameGeometry().width(),
                        self.frameGeometry().height() - 31)
        else:
            geometry = (self.frameGeometry().x(), self.frameGeometry().y(), self.frameGeometry().width(),
                        self.frameGeometry().height())
        self.data.update({"geometry": geometry})
        logger.info("Closing the notebook window")
        self.write_config()

        if hasattr(self, 'repo') and self.repo:
            self.repo.cleanup()

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
