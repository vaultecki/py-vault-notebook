import datetime
import os
import sys
import re
import PySignal
import git
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView
import logging
# import vault_helper


class WikiPage(QWebEnginePage):
    """ Custom WebEnginePage to customize how we handle link navigation """
    nav_link_clicked_signal = PySignal.Signal()

    def acceptNavigationRequest(self, url, _type, isMainFrame):
        if _type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            self.nav_link_clicked_signal.emit(url)

            # Keep reference to external window, so it isn't cleared up.
            # self.external_windows.append(w)
            return False
        return super().acceptNavigationRequest(url, _type, isMainFrame)


class HandleHTML:
    def __init__(self, rules):
        self.rules = rules

    def convert_html2text(self, html, only_body=True):
        if only_body:
            html_text = str(html).split('<body>')[1].split('</body>')[0]
        else:
            html_text = str(html)
        escape = self.rules.get("escape")
        # uncomment escape symbol
        html_text = html_text.replace("<!--{}-->".format(escape), escape)
        html_text = html_text.replace("&lt;", "<")
        html_text = html_text.replace("&gt;", ">")
        html_text = html_text.replace("&emsp;", "    ")
        html_text = html_text.replace("&ensp;", "  ")
        html_text = html_text.replace("&nbsp;", " ")

        for name, tag in self.rules.items():
            if type(tag) == dict:
                if tag.get("txt", False):
                    html_text = self.replace_asym_character(text=html_text, old_tags=tag.get("html"), new_tags=tag.get("txt"))
                else:
                    try:
                        for item, value in tag.items():
                            html_text = self.replace_asym_character(html_text, value.get("html"), value.get("txt"))
                    except:
                        pass
        return html_text

    def convert_text2html(self, text, project_path):

        # converting txt tag into html tag
        html_data = "<html>\n<head>\n<title>{}</title>\n</head>\n<body>\n".format(project_path)
        # todo if necessary escape "&" symbol

        # Replace < with &lt and > with &gt outside of <del> and </del> tags
        # "&lt;" represents in html code "<" and "&gt;" represents in html code ">"
        pattern = r'<(?!/?del\b)[^>]*>'
        text = re.sub(pattern, lambda x: x.group().replace('<', '&lt;').replace('>', '&gt;'), text)
        for line in text.split("\n"):
            if not line:
                html_data += "<br/>\n"
                continue
            # whitespace = len(line) - len(line.lstrip())
            # line = "{}{}".format(whitespace * self.rules.get("leerzeichen").get("html")[0], line.lstrip())

            line = line.replace("    ", "&emsp;")
            line = line.replace("  ", "&ensp;")
            line = line.replace(" ", "&nbsp;")
            ret = self.replace_sym_character(line, old_tags=self.rules.get("fetter_text").get("txt"), new_tags=self.rules.get("fetter_text").get("html"), escape=self.rules.get("escape"))
            ret = self.replace_sym_character(ret, old_tags=self.rules.get("unterstrichener_text").get("txt"), new_tags=self.rules.get("unterstrichener_text").get("html"), escape=self.rules.get("escape"))
            ret = self.replace_asym_character(ret, old_tags=self.rules.get("link").get("txt"), new_tags=self.rules.get("link").get("html"))
            ret = self.replace_sym_character(ret, old_tags=self.rules.get("kursiver_text").get("txt"), new_tags=self.rules.get("kursiver_text").get("html"), escape=self.rules.get("escape"))
            for indentation, signs in self.rules.get("ueberschriften").items():
                ret = self.replace_sym_character(ret, old_tags=signs.get("txt"), new_tags=signs.get("html"), escape=self.rules.get("escape"))
            html_data += "<p>{}</p>\n".format(ret)

        html_data += "</body>\n</html>"
        return html_data

    def replace_asym_character(self, text, old_tags, new_tags, escape=None):
        if len(old_tags) != len(new_tags):
            raise ValueError("old_tags and new_tags must have the same length")

        for i in range(len(old_tags)):
            text = text.replace(old_tags[i], new_tags[i])
            if escape:
                text = text.replace("{}{}".format(escape, new_tags[i]), old_tags[i])
        return text

    def replace_sym_character(self, text, old_tags, new_tags, escape):
        if len(old_tags) != len(new_tags):
            raise ValueError("old_tags and new_tags must have the same length")

        new_text = ""
        last_set_tag = ""
        skip_indices = 0
        for index, ltr in enumerate(text):
            if index < skip_indices:
                continue

            maybe_escaped_old = text[index: index + len(escape) + len(old_tags[0])]
            maybe_old = text[index: index + len(old_tags[0])]
            if maybe_escaped_old == "{}{}".format(escape, old_tags[0]):
                # new_text += old_tags[0]
                # new_text += maybe_escaped_old
                # save escape symbols as comment, to not show them
                new_text += "<!--{}-->{}".format(escape, old_tags[0])
                skip_indices = index + len(maybe_escaped_old)
            elif maybe_old == old_tags[0]:
                if last_set_tag == new_tags[1] or not last_set_tag:
                    new_text += new_tags[0]
                    last_set_tag = new_tags[0]
                    skip_indices = index + len(maybe_old)

                elif last_set_tag == new_tags[0]:
                    new_text += new_tags[1]
                    last_set_tag = new_tags[1]
                    skip_indices = index + len(maybe_old)
            else:
                new_text += ltr

        return new_text

    def get_html_content(self, filepath):
        try:
            f = open(filepath, "r", encoding="utf-8")
            html = f.read()
            f.close()
        except Exception as e:
            html = "<html><head><title>error page</title></head><body><h1>unexpected error</h1><p>{}</body></html>".format(e)

        return html

    def write_html_content(self, html, filepath):
        try:
            w = open(filepath, "w", encoding="utf-8")
            w.write(html)
            w.close()
        except Exception as e:
            raise FileNotFoundError

    def init_html_str(self, project_path="", font_family=""):
        html = "<html>\n<head>\n<title>{}</title>\n</head>\n<body>\n<p><h1>{}</h1></p>\n</body>\n</html>".format(project_path, project_path)
        if font_family:
            html = "<html>\n<head>\n<style>\nbody {font-family: {}}\n</style>\n<title>{}</title>\n</head>\n<body>\n<p><h1>{}</h1></p>\n</body>\n</html>".format(font_family, project_path, project_path)

        return html


class Wiki(QtWidgets.QWidget):

    def __init__(self, debug=False):
        super().__init__()
        # Configure logger
        self.debug = True
        log_name = "MainWindow"
        logging.basicConfig(format=f'%(levelname)s - {log_name}: %(message)s', level=logging.DEBUG, force=True)
        self.logger = logging.getLogger()
        self.logger.disabled = not self.debug

        # web
        self.web_engine_view = QWebEngineView()
        self.web_page = WikiPage(self)
        self.web_page.nav_link_clicked_signal.connect(self.on_click_nav_link)
        self.web_engine_view.setPage(self.web_page)

        # config
        self.conf_filename = "config/config.json"
        self.html_const_name = "index.html"
        self.config = vault_helper.json_file_read(self.conf_filename)
        self.projects = self.config.get("projects", {})
        self.rules = self.config.get("rules")

        # current project
        self.active_project = self.config.get("active", "")
        self.project_path = self.projects.get(self.active_project, {}).get("path", "")
        self.filepath = os.path.join(self.project_path, self.html_const_name)

        # html_converter object
        self.html_handler = HandleHTML(self.rules)

        # variables
        self.edit_page_window = None
        self.repo = None

        # init
        self.init_ui()
        self.init_page()

    def init_ui(self):
        vbox = QtWidgets.QVBoxLayout(self)
        hbox = QtWidgets.QHBoxLayout()
        hbox2 = QtWidgets.QHBoxLayout()

        # projects from conf
        self.project_drop_down = QtWidgets.QComboBox()
        self.project_drop_down.setMinimumWidth(130)
        hbox.addWidget(self.project_drop_down)

        # search box
        self.search_box = QtWidgets.QComboBox()
        self.search_box.setEditable(True)
        hbox.addWidget(self.search_box)

        # search btn
        search_button = QtWidgets.QPushButton("🔎")
        hbox.addWidget(search_button)
        search_button.clicked.connect(self.on_click_search)

        # open git btn
        open_git_button = QtWidgets.QPushButton("Commits")
        hbox.addWidget(open_git_button)
        open_git_button.clicked.connect(self.open_git)

        # add btn
        add_project_button = QtWidgets.QPushButton('Add Project', self)
        hbox2.addWidget(add_project_button)
        add_project_button.clicked.connect(self.on_click_add_project)

        # new btn
        new_project_button = QtWidgets.QPushButton('New Project', self)
        hbox2.addWidget(new_project_button)
        new_project_button.clicked.connect(self.on_click_new_project)

        # export btn
        export_button = QtWidgets.QPushButton('Export', self)
        hbox2.addWidget(export_button)
        export_button.clicked.connect(self.on_export_pdf)

        # edit btn
        edit_page_button = QtWidgets.QPushButton('Edit Page', self)
        hbox2.addWidget(edit_page_button)
        edit_page_button.clicked.connect(self.on_click_edit_page)

        # update page
        update_current_page_btn = QtWidgets.QPushButton("🔄")
        hbox2.addWidget(update_current_page_btn)
        update_current_page_btn.clicked.connect(self.update_current_page)

        # settings
        vbox.addLayout(hbox)
        vbox.addLayout(hbox2)
        vbox.addWidget(self.web_engine_view)
        self.setLayout(vbox)

        self.setGeometry(300, 300, 350, 250)
        self.resize(900, 500)
        self.setWindowTitle('QWebEngineView')
        self.show()
        self.logger.info("Mainwindow widgets created")

    def init_page(self):
        # check for removed files
        self.__check_removed_files()

        # load all projects
        self.project_drop_down.clear()
        for project_name in self.projects:
            self.project_drop_down.addItem(project_name)

        # load page
        if not self.project_path:
            self.logger.warning("You have to create a new project")
        else:
            html = self.html_handler.get_html_content(self.filepath)
            self.load_page(project_name=self.active_project, html=html, project_path=self.project_path)

        # connect event on select project_drop_down only now because it causes some problems during initialization
        self.project_drop_down.currentTextChanged.connect(self.on_project_select)

    def on_project_select(self, project_name):
        self.logger.info("Selection changed to: {}".format(project_name))
        if not project_name:
            return
        project_path = self.projects.get(project_name, {}).get("path")
        filepath = os.path.join(project_path, self.html_const_name)
        html = self.html_handler.get_html_content(filepath)

        self.load_page(project_name=project_name, html=html, project_path=project_path)

    def on_click_new_project(self):
        project_name = ""
        while not project_name:
            new_name, ok = QtWidgets.QInputDialog.getText(self, "New Project", "Name für das Projekt:")
            if self.projects.get(new_name):
                QtWidgets.QMessageBox.information(self, "New Project", "Das Projekt is bereits in der Liste.\nBitte geben Sie einen anderen Namen ein.")
                self.logger.error("Das Projekt is bereits in der Liste.\nBitte geben Sie einen anderen Namen ein.")
                continue
            elif not ok:
                return
            project_name = new_name

        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory")
        if path:
            project_path = os.path.join(path, project_name)
            if not os.path.exists(project_path):
                # create folder
                os.mkdir(project_path)
                filepath = os.path.join(project_path, self.html_const_name)
                # create html file
                html = self.html_handler.init_html_str(project_path=project_path)
                self.html_handler.write_html_content(html=html, filepath=filepath)

                username = os.getlogin()
                name, ok = QtWidgets.QInputDialog.getText(self, "Committer", "Ihr Committer-name:", text=username)
                if ok:
                    username = name
                self.__init_repo(project_path=project_path, add_files=[self.html_const_name], name=username)
                self.load_page(project_name=project_name, html=html, project_path=project_path)
                self.logger.debug("Project created: {}; path: {}; Committer-Name: {};".format(project_name, project_path, name))
            else:
                QtWidgets.QMessageBox.information(self, "New Project", "Ein Ordner/Datei mit diesem Namen exestiert bereits.\nBitte geben Sie einen anderen Namen ein.")
                self.logger.error("Ein Ordner/Datei mit diesem Namen exestiert bereits.\nBitte geben Sie einen anderen Namen ein.")

    def on_click_add_project(self):
        project_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory")
        if project_path:
            project_name = os.path.split(project_path)[1]
            if not self.projects.get(project_name, False):
                filepath = os.path.join(project_path, self.html_const_name)
                if os.path.exists(filepath):
                    html = self.html_handler.get_html_content(filepath)
                    self.load_page(project_name=project_name, html=html, project_path=project_path)
                else:
                    QtWidgets.QMessageBox.information(self, "Add Project", "{} nicht gefunden".format(filepath))
                    self.logger.error("Add Project", "{} nicht gefunden".format(filepath))
            else:
                QtWidgets.QMessageBox.information(self, "Add Project", "Das Projekt is bereits in der Liste")
                self.logger.error("Das Projekt is bereits in der Liste")

    def on_click_edit_page(self):
        self.edit_page_window = EditPage(project_path=self.project_path, html_filepath=self.filepath, repo=self.repo, html_handler=self.html_handler, debug=self.debug)
        self.edit_page_window.window_closed_sygnal.connect(self.update_current_page)
        self.edit_page_window.show()

    def on_click_search(self):  # todo develope and use if need
        searched = self.search_box.currentText().lower()
        if not searched:
            return

        found = []
        for file in os.listdir(self.project_path):
            if file.lower().startswith(searched):
                found.append(os.path.join(self.project_path, file))
        # todo do smth with found files
        self.search_box.addItems(found)
        self.logger.debug("Found: {}".format(found))

    def on_export_pdf(self, pdf_filepath=""):
        if not pdf_filepath:
            datetime_now = datetime.datetime.now()
            pdf_filepath = os.path.join(self.project_path, "page_{}_{}.pdf".format(self.active_project, datetime_now.strftime("%d-%m-%Y_%H-%M")))

        self.web_engine_view.page().printToPdf(pdf_filepath)
        QtWidgets.QMessageBox.information(self, 'info', 'Page exported successfully.\nPath: {}'.format(pdf_filepath))
        self.logger.info('Page exported successfully.\nPath: {}'.format(pdf_filepath))

    def on_click_nav_link(self, url):
        url_text = url.url()
        self.logger.info("Link clicked: {}; url_text: {};".format(url, url_text))

        msg_box = QtWidgets.QMessageBox()
        msg_box.setText("Möchten Sie diese Seite öffnen?")
        msg_box.addButton("Ja", QtWidgets.QMessageBox.ButtonRole.YesRole)
        msg_box.addButton("Abbrechen", QtWidgets.QMessageBox.ButtonRole.NoRole)

        if url_text.startswith("file:///"):
            path = url_text.split("file:///")[1]
            # case 1: html file # case 2: project folder

            filename = ""
            project_name = ""
            project_path = ""

            if not os.path.isfile(path):
                self.logger.info("Link is not a filepath")
                for file in os.listdir(path):
                    if os.path.splitext(file)[1] == ".html":
                        filename = file
                        project_name = os.path.basename(path)
                        project_path = path
                        break
            elif os.path.isfile(path) and os.path.splitext(path)[1] == ".html":
                filename = os.path.basename(path)
                project_path = os.path.dirname(path)
                project_name = os.path.basename(project_path)
            else:
                return
            msg_box.setInformativeText("Link: {}\nDiese Datei wird geladen: {}".format(path, filename))
            self.logger.info("Link: {}\nDiese Datei wird geladen: {}".format(path, filename))

            ret = msg_box.exec()
            # 0 - Ja, 1 - Abbrechen
            if ret == 0:
                # load html
                filepath = os.path.join(project_path, filename)
                html = self.html_handler.get_html_content(filepath)
                self.load_page(project_name=project_name, html=html, project_path=project_path)
        else:
            msg_box.setInformativeText("Externer Link: {}".format(url_text))
            ret = msg_box.exec()
            # 0 - Ja, 1 - Abbrechen
            if ret == 0:
                # load html
                self.web_page.load(url)

    def open_git(self):
        self.git_window = GitWindow(git_repo=self.repo, project_path=self.project_path, html_handler=self.html_handler, debug=self.debug)
        self.git_window.show()

    def load_page(self, project_name, html, project_path):
        self.logger.info("Loading page from path: {}".format(project_path))
        self.__update_active_config(project_name)

        if not self.projects.get(project_name, False):
            self.__update_project_config(project_name, project_path, [self.html_const_name])
            self.project_drop_down.addItem(project_name)
        self.project_drop_down.setCurrentText(project_name)

        # todo add all untracked files
        if self.repo:
            self.repo.close()
        self.repo = git.Repo(project_path)

        # update paths
        self.project_path = project_path
        self.filepath = os.path.join(project_path, self.html_const_name)
        self.__check_untracked_files()
        self.web_page.setHtml(html)

    def update_current_page(self):
        html = self.html_handler.get_html_content(self.filepath)
        self.load_page(project_name=self.active_project, html=html, project_path=self.project_path)

    def __update_project_config(self, project_name, path="", last=[]):
        project = {project_name: {"path": path, "last": last}}
        self.projects.update(project)
        self.config.update({"active": project_name})
        self.config.update({"projects": self.projects})
        self.active_project = project_name
        vault_helper.json_file_write(self.config, self.conf_filename)

    def __update_active_config(self, project_name):
        self.active_project = project_name
        self.config.update({"active": project_name})

    def __init_repo(self, project_path, add_files=[], name=None, email=None):
        repo = git.Repo.init(project_path)
        repo.index.add(add_files)

        committer = git.Actor(name=name, email=email)
        repo.index.commit("initial commit", author=committer, committer=committer)
        return repo

    def __check_untracked_files(self):
        untracked_files = self.repo.untracked_files
        if untracked_files:
            self.logger.debug("Untracked files: {}".format(untracked_files))

    def __check_removed_files(self):
        # check for removed files or folders
        files_to_remove = []
        for project_name, project in self.projects.items():
            project_path = project.get("path", False)

            if not os.path.exists(project_path):
                file_to_remove = {"type": "folder", "project_name": project_name, "path": project_path}
                files_to_remove.append(file_to_remove)
            else:
                for file in project.get("last", []):
                    file_path = os.path.join(project_path, file)
                    if not os.path.exists(file_path):
                        file_to_remove = {"type": "file", "project_name": project_name, "filename": file, "path": file_path}
                        files_to_remove.append(file_to_remove)
        if files_to_remove:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText("Einige Dateien können nicht gefunden werden. Möchten Sie Pfade zu ihnen entfernen?")
            msg_box.setIcon(QtWidgets.QMessageBox.Icon.Question)

            msg_box.setDetailedText("\n".join(d["path"] for d in files_to_remove))

            msg_box.addButton("Ja", QtWidgets.QMessageBox.ButtonRole.YesRole)
            msg_box.addButton("Nein", QtWidgets.QMessageBox.ButtonRole.NoRole)

            ret = msg_box.exec()
            if ret == 0:  # pressed yes
                self.logger.debug("files to remove: {}".format(files_to_remove))
                for file in files_to_remove:

                    if file.get("type") == "folder":
                        project_name = file.get("project_name")
                        self.projects.pop(project_name)
                        if self.active_project == project_name:
                            self.active_project = ""
                    elif file.get("type") == "file":
                        self.projects.get(file.get("project_name")).get("last").remove(file.get("filename"))

                self.config.update({"projects": self.projects})

    @pyqtSlot(QtGui.QCloseEvent)
    def closeEvent(self, event):
        self.logger.info("Closing the window")
        vault_helper.json_file_write(self.config, self.conf_filename)
        self.web_engine_view.setPage(None)
        self.web_engine_view = None
        self.web_page = None


class EditPage(QtWidgets.QMainWindow):
    window_closed_sygnal = PySignal.Signal()

    def __init__(self, project_path, html_filepath, repo, html_handler, debug=False):
        super(EditPage, self).__init__()
        # Configure logger
        self.debug = debug
        log_name = "EditWindow"
        logging.basicConfig(format=f'%(levelname)s - {log_name}: %(message)s', level=logging.DEBUG, force=True)
        self.logger = logging.getLogger()
        self.logger.disabled = not self.debug

        self.filepath = html_filepath
        self.project_path = project_path
        self.conf_filename = "config/config.json"
        self.config = vault_helper.json_file_read(self.conf_filename)
        self.rules = self.config.get("rules")

        self.html_handler = html_handler
        self.repo = repo

        # Qt widgets
        main_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout()
        self.text_field = QtWidgets.QPlainTextEdit()

        # layout settings
        main_layout.addWidget(self.text_field)
        main_layout.addWidget(self.init_format_field())
        main_widget.setLayout(main_layout)

        # settings
        self.setCentralWidget(main_widget)
        self.resize(900, 500)
        self.text_field.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        # signals
        self.connect_text_field_signals()

        # variables
        self.saved = False

        # loadings
        self.load_content()
        self.logger.info("Edit window initialized")

    def init_format_field(self):
        # main widget and layout
        format_container = QtWidgets.QWidget(self)
        format_layout = QtWidgets.QGridLayout()
        format_container.setLayout(format_layout)

        # headlines combobox
        headlines_combobox = QtWidgets.QComboBox()
        headlines_combobox.setToolTip("<b>Überschrift</b><br><br>Eine neue Überschrift auswählen")
        headlines = self.rules.get("ueberschriften", False)

        headlines_combobox.addItems(headlines)
        format_layout.addWidget(headlines_combobox, 0, 0, 1, 2)
        headlines_combobox.textActivated.connect(lambda: self.on_select_headline_indent("ueberschriften", headlines_combobox.currentText()))

        # indentation
        indent_combobox = QtWidgets.QComboBox()
        indent_options = self.rules.get("absatzausrichtungen", False)
        indent_combobox.addItems(indent_options)
        indent_combobox.setToolTip("<b>Absatzausrichtung</b><br><br>Textausrichtung, Absatzabstände und Textrichtung festlegen")
        format_layout.addWidget(indent_combobox, 0, 2, 1, 2)
        indent_combobox.textActivated.connect(lambda: self.on_select_headline_indent("absatzausrichtungen", indent_combobox.currentText()))

        # bullet_combobox
        bullet_combobox = QtWidgets.QComboBox()
        bullet_symbols = self.rules.get("symbole")
        bullet_combobox.addItems(bullet_symbols)
        bullet_combobox.setToolTip("<b>Aufzählungszeichen</b><br><br>Erstellen Sie eine Aufzählung")
        format_layout.addWidget(bullet_combobox, 0, 4, 1, 2)
        bullet_combobox.textActivated.connect(self.on_select_bullet)

        # internal link button
        int_link_btn = QtWidgets.QPushButton("Int Link")
        int_link_btn.setToolTip("<b>Internen Link hinzufügen</b><br><br>Fügen Sie einen internen Link hinzu")
        format_layout.addWidget(int_link_btn, 0, 6, 1, 1)
        int_link_btn.clicked.connect(self.handle_click_link_buttons)

        # external link button
        ext_link_btn = QtWidgets.QPushButton("Ext Link")
        ext_link_btn.setToolTip("<b>Externen Link hinzufügen</b><br><br>Fügen Sie einen externen Link hinzu")
        format_layout.addWidget(ext_link_btn, 0, 7, 1, 1)
        ext_link_btn.clicked.connect(lambda: self.handle_click_link_buttons(external=True))

        # bold_text_btn
        bold_text_btn = QtWidgets.QPushButton("F")
        bold_text_btn.setStyleSheet("font-weight: bold")
        bold_text_btn.setToolTip("<b>Fett</b><br><br>Text fett formatieren")
        format_layout.addWidget(bold_text_btn, 1, 0, 1, 2)
        bold_text_btn.clicked.connect(lambda: self.on_click_format_buttons("fetter_text"))

        # cursive_text_btn
        cursive_text_btn = QtWidgets.QPushButton("K")
        cursive_text_btn.setStyleSheet("font: italic")
        cursive_text_btn.setToolTip("<b>Kursiv</b><br><br>Text kursiv formatieren")
        format_layout.addWidget(cursive_text_btn, 1, 2, 1, 2)
        cursive_text_btn.clicked.connect(lambda p: self.on_click_format_buttons("kursiver_text"))

        # underline_text_btn
        underline_text_btn = QtWidgets.QPushButton("U")
        underline_text_btn.setStyleSheet("text-decoration: underline")
        underline_text_btn.setToolTip("<b>Unterstreichen</b><br><br>Text unterstreichen")
        format_layout.addWidget(underline_text_btn, 1, 4, 1, 2)
        underline_text_btn.clicked.connect(lambda p: self.on_click_format_buttons("unterstrichener_text"))

        # strikethrough_text_btn
        strikethrough_text_btn = QtWidgets.QPushButton("ab")
        strikethrough_text_btn.setStyleSheet("text-decoration: line-through")
        strikethrough_text_btn.setToolTip("<b>Durchstreichen</b><br><br>Text durchstreichen")
        format_layout.addWidget(strikethrough_text_btn, 1, 6, 1, 2)
        strikethrough_text_btn.clicked.connect(lambda p: self.on_click_format_buttons("durchgestrichener_text"))

        # open git
        open_git_btn = QtWidgets.QPushButton("Commits")
        format_layout.addWidget(open_git_btn, 0, 10)
        open_git_btn.clicked.connect(self.on_open_git)

        format_layout.addWidget(QVLine(), 0, 8, 2, 1)  # line

        # save btn
        save_change_btn = QtWidgets.QPushButton("Speichern")
        format_layout.addWidget(save_change_btn, 1, 9)
        save_change_btn.clicked.connect(self.on_click_save)

        # reset changes button
        discard_btn = QtWidgets.QPushButton("Verwerfen")
        format_layout.addWidget(discard_btn, 0, 9)
        discard_btn.clicked.connect(self.on_click_discard_changes)

        # info button
        info_button = QtWidgets.QPushButton("ℹ️")
        format_layout.addWidget(info_button, 1, 10)
        info_button.clicked.connect(self.on_click_info)

        return format_container

    def on_select_headline_indent(self, style, item):
        style = self.rules.get(style, False)
        sign = style.get(item, False).get("txt", [])

        selected_text = self.text_field.textCursor().selectedText()
        if selected_text:
            item = selected_text

        start = self.text_field.textCursor().selectionStart() + len(sign[0])
        length = len(item) + 1

        text_to_set = "{} {} {}".format(sign[0], item, sign[1])
        self.text_field.insertPlainText(text_to_set)
        self.__select_text(start, length)

    def on_select_bullet(self, symbol):
        # row_nr = self.getLineAtPosition(self.text_field.textCursor().position())
        # column_nr = self.text_field.textCursor().columnNumber()
        cur_line_text = self.text_field.textCursor().block().text()

        text_to_set = "    {} ".format(symbol)
        if cur_line_text:
            text_to_set = "\n{}".format(text_to_set)

        self.text_field.insertPlainText(text_to_set)
        self.text_field.setFocus()

    def on_click_format_buttons(self, style):
        sign = self.rules.get(style, {}).get("txt", [])

        selected_text = self.text_field.textCursor().selectedText()
        if selected_text:
            if selected_text.strip() == style.strip():
                return
            style = selected_text

        selection_start = self.text_field.textCursor().selectionStart() + len(sign[0])
        # number of whitespaces before and after "style"
        length = len(style) + 2
        text_to_set = "{} {} {}".format(sign[0], style, sign[1])
        self.text_field.insertPlainText(text_to_set)
        self.__select_text(selection_start, length)

    def handle_click_link_buttons(self, external=False):
        sign = self.rules.get("link", {}).get("txt", [])
        if external:
            path = self.rules.get("link").get("style")

        else:
            # todo select either file or folder available
            path = QtWidgets.QFileDialog.getOpenFileName(self, "Select File")[0]
            if path:
                self.logger.debug("Path selected: {}".format(path))

        placeholder = path
        selection_start = self.text_field.textCursor().selectionStart() + len(sign[0]) + len(sign[1]) + len(placeholder)
        text_to_set = "{}{}{}{}{}".format(sign[0], path, sign[1], placeholder, sign[2])
        self.text_field.insertPlainText(text_to_set)

        length = len(placeholder)
        self.__select_text(selection_start, length)
        self.text_field.setFocus()

    def on_click_save(self):
        if not self.saved:
            self.save_changes()
            self.saved = True

    def on_click_discard_changes(self):
        msg_box = QtWidgets.QMessageBox()
        msg_box.setText("Wollen Sie den Text wirklich verwerfen?")

        msg_box.addButton("Ja", QtWidgets.QMessageBox.ButtonRole.YesRole)
        msg_box.addButton("Abbrechen", QtWidgets.QMessageBox.ButtonRole.NoRole)

        ret = msg_box.exec()
        if ret == 0:
            self.text_field.clear()
            self.load_content()
            self.logger.info("Discarding changes")

        self.text_field.setFocus()

    def on_open_git(self):
        self.git_window = GitWindow(git_repo=self.repo, project_path=self.project_path, html_handler=self.html_handler, debug=self.debug)
        self.git_window.show()

    def on_enter_pressed(self, block_nr):
        prev_line_text = self.text_field.textCursor().block().previous().text()

        if not prev_line_text:
            return

        for symbol in self.rules.get("symbole"):
            if prev_line_text == "    {} ".format(symbol):
                # wenn die aufgezählte Zeile leer ist, nicht mehr aufzählen
                return
            elif prev_line_text.startswith("    {}".format(symbol)):
                text_to_set = "    {} ".format(symbol)
                self.text_field.insertPlainText(text_to_set)
                return
        self.text_field.setFocus()

    def on_click_info(self, text=""):
        self.info_window = QtWidgets.QMainWindow(self)
        self.info_window.resize(700, 500)
        self.info_window.setWindowTitle("Information")
        self.info_window.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        info_text_field = QtWidgets.QPlainTextEdit()
        info_text_field.setReadOnly(True)
        info_text_field.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.info_window.setCentralWidget(info_text_field)

        if not text:
            try:
                r = open("config/information.txt", "r", encoding="utf-8")
                text = r.readlines()
                r.close()
            except:
                text = ["Keine Information"]

            for line in text:
                info_text_field.insertPlainText(line)
        else:
            info_text_field.appendPlainText(text)
        self.info_window.show()

    def on_text_changed(self):
        self.saved = False

    def __select_text(self, start, length):
        cursor = self.text_field.textCursor()
        cursor.clearSelection()

        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start, QtGui.QTextCursor.MoveMode.MoveAnchor)
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.MoveAnchor, start + length)
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Left, QtGui.QTextCursor.MoveMode.KeepAnchor, length)
        cursor.selectedText()
        self.text_field.setFocus()
        self.text_field.setTextCursor(cursor)

    def save_changes(self):
        content = self.text_field.toPlainText()

        html = self.html_handler.convert_text2html(text=content, project_path=self.project_path)
        self.logger.debug("Converted Text to HTML:\n{}\n{}".format(html, 40 * "-"))
        # save into file
        self.html_handler.write_html_content(html=html, filepath=self.filepath)
        self.logger.info("Changes saved")

        # todo if necessary ask for commit name
        # commit
        if self.repo.is_dirty():
            index = len(list(self.repo.iter_commits()))
            self.repo.index.add(["index.html"])
            self.repo.index.commit("commit_{}".format(index + 1))
            self.logger.debug("Changes committed; Commits count: {}".format(index))
        else:
            self.logger.info("No change - Not committed")

    def load_content(self):
        html = self.html_handler.get_html_content(self.filepath)

        converted_text = self.html_handler.convert_html2text(html)
        # disconnect signals
        self.disconnect_text_field_signals()

        self.text_field.clear()
        for line in converted_text.splitlines():
            self.text_field.appendPlainText(line)
        self.text_field.setFocus()
        self.connect_text_field_signals()

    def __getLineAtPosition(self, pos):
        cursor = self.text_field.textCursor()
        cursor.setPosition(pos)

        cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfLine)
        lines = 0

        lines_text = cursor.block().text().splitlines()
        lines_pos = 0
        for line_text in lines_text:
            lines_pos += len(line_text) + 1
            if lines_pos > cursor.position() - cursor.block().position():
                break
            lines += 1

        block = cursor.block().previous()
        while block.isValid():
            lines += block.lineCount()
            block = block.previous()

        return lines

    def connect_text_field_signals(self):
        self.text_field.textChanged.connect(self.on_text_changed)
        self.text_field.blockCountChanged.connect(self.on_enter_pressed)

    def disconnect_text_field_signals(self):
        self.text_field.textChanged.disconnect(self.on_text_changed)
        self.text_field.blockCountChanged.disconnect(self.on_enter_pressed)

    @pyqtSlot(QtGui.QCloseEvent)
    def closeEvent(self, event):
        self.logger.info("Trying to close window")
        if not self.saved:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText("Möchten Sie die Änderungen Speichern?")

            yes_btn = msg_box.addButton(QtWidgets.QMessageBox.StandardButton.Yes)
            yes_btn.setText("Speichern")
            no_btn = msg_box.addButton(QtWidgets.QMessageBox.StandardButton.No)
            no_btn.setText("Nicht speichern")
            cancel_btn = msg_box.addButton(QtWidgets.QMessageBox.StandardButton.Cancel)
            cancel_btn.setText("Weiter bearbeiten")

            msg_box.setDefaultButton(yes_btn)

            ret = msg_box.exec()
            if ret == QtWidgets.QMessageBox.StandardButton.Yes:
                self.save_changes()
                self.saved = True
            elif ret == QtWidgets.QMessageBox.StandardButton.No:
                self.window_closed_sygnal.emit()
            elif ret == QtWidgets.QMessageBox.StandardButton.Cancel:
                event.ignore()
        else:
            self.window_closed_sygnal.emit()


class GitWindow(QtWidgets.QMainWindow):
    def __init__(self, git_repo, html_handler, project_path="", debug=False):
        super().__init__()
        # Configure logger
        self.debug = debug
        log_name = "GitWindow"
        logging.basicConfig(format=f'%(levelname)s - {log_name}: %(message)s', level=logging.DEBUG, force=True)
        self.logger = logging.getLogger()
        self.logger.disabled = not self.debug

        self.project_path = project_path
        self.repo = git_repo
        self.html_handler = html_handler

        # window
        self.tab = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tab)

        self.tab.addTab(self.init_version_tab(), 'Versionen')
        self.tab.addTab(self.init_overview_tab(), 'View')

        self.resize(700, 400)
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        self.selected = []

        self.load_commits()
        self.logger.info("Git window started")

    def init_version_tab(self):
        version_page = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout()
        version_page.setLayout(layout)

        self.verson_tab_label = QtWidgets.QLabel("Wählen Sie zwei Commits zum Vergleich aus")
        layout.addWidget(self.verson_tab_label)

        self.commits_tree = QtWidgets.QTreeWidget()
        self.commits_tree.setColumnCount(5)
        self.commits_tree.setHeaderLabels(["Beschreibung", "Datum", "Author", "Größe in Byte", "Commit"])
        self.commits_tree.itemChanged.connect(self.handle_item_changed)
        layout.addWidget(self.commits_tree)

        self.compare_btn = QtWidgets.QPushButton("Vergleichen")
        layout.addWidget(self.compare_btn)
        self.compare_btn.setEnabled(False)
        self.compare_btn.clicked.connect(self.on_click_compare)

        return version_page

    def init_overview_tab(self):
        overview_page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        text_boxes_layout = QtWidgets.QHBoxLayout()
        overview_page.setLayout(layout)

        self.overview_label = QtWidgets.QLabel("Hier werden die Unterschiede zwischen zwei Versionen angezeigt.")
        layout.addWidget(self.overview_label)

        self.left_commit_box = QtWidgets.QPlainTextEdit()
        self.left_commit_box.setReadOnly(True)
        self.left_commit_box.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        text_boxes_layout.addWidget(self.left_commit_box)

        text_boxes_layout.addWidget(QVLine())

        self.right_commit_box = QtWidgets.QPlainTextEdit()
        self.right_commit_box.setReadOnly(True)
        self.right_commit_box.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        text_boxes_layout.addWidget(self.right_commit_box)

        layout.addLayout(text_boxes_layout)

        return overview_page

    def on_click_compare(self):
        self.left_commit_box.clear()
        self.right_commit_box.clear()

        commits_list = []
        for item in self.selected:
            message = item.text(0)
            datetime = item.text(1)
            author = item.text(2)
            size = item.text(3)
            commit = item.text(4)
            commit_data = {"message": message, "datetime": datetime, "author": author, "size": size, "commit": commit}
            commits_list.append(commit_data)

        left_diff = "{}\n".format(str(commits_list[0]))
        diff = self.repo.git.diff(commits_list[1].get("commit"), commits_list[0].get("commit"))
        left_diff += self.html_handler.convert_html2text(html=diff, only_body=True)

        right_diff = "{}\n".format(str(commits_list[1]))
        diff = self.repo.git.diff(commits_list[0].get("commit"), commits_list[1].get("commit"))
        right_diff += self.html_handler.convert_html2text(html=diff, only_body=True)

        self.left_commit_box.appendPlainText(left_diff)
        self.right_commit_box.appendPlainText(right_diff)

        # show second tab
        self.tab.setCurrentIndex(1)

    def handle_item_changed(self, item, column):
        self.compare_btn.setEnabled(False)
        if item.checkState(column) == QtCore.Qt.CheckState.Checked:
            self.logger.debug("checked: {}".format(item))
            self.selected.append(item)
            # print("selected items: ", self.selected)
            if len(self.selected) == 1:
                return
            elif len(self.selected) == 2:
                self.__disableTreeItem(state=True, exception=self.selected)
                self.compare_btn.setEnabled(True)
        elif item.checkState(column) == QtCore.Qt.CheckState.Unchecked:
            self.logger.debug("unchecked: {}".format(item))
            self.selected.remove(item)
            self.__disableTreeItem(state=False)

    def __disableTreeItem(self, state, exception=[]):
        self.commits_tree.itemChanged.disconnect(self.handle_item_changed)
        # disconnect event during this process, because this process calls the event
        for item in self.get_all_items(self.commits_tree):
            if item not in exception:
                item.setDisabled(state)
        # connect event again
        self.commits_tree.itemChanged.connect(self.handle_item_changed)

    def load_commits(self):
        self.logger.info("Loading commits")
        commits = self.repo.iter_commits(rev=self.repo.head.reference)
        for commit in commits:
            entry = QtWidgets.QTreeWidgetItem([commit.message, str(commit.committed_datetime), str(commit.author), str(commit.size), str(commit)])
            entry.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
            self.commits_tree.addTopLevelItem(entry)
            self.commits_tree.resizeColumnToContents(0)
            self.commits_tree.resizeColumnToContents(1)
            self.commits_tree.resizeColumnToContents(2)

    def __get_subtree_nodes(self, tree_widget_item):
        """Returns all QTreeWidgetItems in the subtree rooted at the given node."""
        nodes = []
        nodes.append(tree_widget_item)
        for i in range(tree_widget_item.childCount()):
            nodes.extend(self.__get_subtree_nodes(tree_widget_item.child(i)))
        return nodes

    def get_all_items(self, tree_widget):
        """Returns all QTreeWidgetItems in the given QTreeWidget."""
        all_items = []
        for i in range(tree_widget.topLevelItemCount()):
            top_item = tree_widget.topLevelItem(i)
            all_items.extend(self.__get_subtree_nodes(top_item))
        return all_items


class QVLine(QtWidgets.QFrame):
    def __init__(self):
        super(QVLine, self).__init__()

        self.setFrameShape(QtWidgets.QFrame().Shape.VLine)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Raised)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    ex = Wiki(False)
    sys.exit(app.exec())
