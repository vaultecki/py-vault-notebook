# Copyright [2025] [ecki]
# SPDX-License-Identifier: Apache-2.0

"""
Main application file for Notebook application.
Handles project management, file viewing, and Git integration.
"""
import datetime
import json
import logging
import os
import pathlib
import sys
import time
from typing import Optional, Dict

import PyQt6
import PyQt6.QtCore
import PyQt6.QtGui
import PyQt6.QtWidgets
import PyQt6.QtWebEngineCore
import PyQt6.QtWebEngineWidgets

import editpage
import notegit
import notehelper
import commitbrowser

logger = logging.getLogger(__name__)


class NotebookPage(PyQt6.QtWebEngineCore.QWebEnginePage):
    """
    Custom WebEnginePage to customize link navigation handling.

    Signals:
        nav_link_clicked_internal_signal: Emitted for internal file links
        nav_link_clicked_external_signal: Emitted for external URLs
    """
    nav_link_clicked_internal_signal = PyQt6.QtCore.pyqtSignal(PyQt6.QtCore.QUrl)
    nav_link_clicked_external_signal = PyQt6.QtCore.pyqtSignal(PyQt6.QtCore.QUrl)

    def acceptNavigationRequest(
            self,
            url: PyQt6.QtCore.QUrl,
            _type: PyQt6.QtWebEngineCore.QWebEnginePage.NavigationType,
            isMainFrame: bool
    ) -> bool:
        """
        Handle navigation requests and emit appropriate signals.

        Args:
            url: Target URL
            _type: Type of navigation
            isMainFrame: Whether this is the main frame

        Returns:
            True to allow navigation, False to block it
        """
        if _type == PyQt6.QtWebEngineCore.QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            logger.debug(f"URL clicked: {url.toString()}")

            if not url.isValid() or url.isEmpty():
                logger.warning("Invalid URL")
                return False

            if url.isLocalFile():
                logger.debug("Emitting signal to handle local file")
                self.nav_link_clicked_internal_signal.emit(url)
                return False

            logger.debug("Emitting signal for external URL")
            self.nav_link_clicked_external_signal.emit(url)
            return False

        return super().acceptNavigationRequest(url, _type, isMainFrame)


class Notebook(PyQt6.QtWidgets.QMainWindow):
    """
    Main notebook application window.
    Manages projects, files, and provides AsciiDoc viewing and editing.
    """

    def __init__(self):
        super().__init__()

        # Initialize variables
        self.config_filename: Optional[pathlib.Path] = None
        self.data: Dict = {}
        self.current_file_name: Optional[str] = None
        self.commit_browser: Optional[commitbrowser.CommitBrowserDialog] = None
        self.repo: Optional[notegit.NoteGit] = None

        # Initialize UI elements
        self.project_drop_down = PyQt6.QtWidgets.QComboBox()
        self.search_box = PyQt6.QtWidgets.QComboBox()
        self.setWindowTitle('Notebook')

        # Read configuration
        self.read_config()

        # Initialize web view
        self.web_engine_view = PyQt6.QtWebEngineWidgets.QWebEngineView()
        self.web_page = NotebookPage(self)
        self.web_page.nav_link_clicked_internal_signal.connect(self.on_internal_url)
        self.web_page.nav_link_clicked_external_signal.connect(self.on_external_url)
        self.web_engine_view.setPage(self.web_page)

        # Initialize UI
        self.init_ui()

        # Initialize repository
        self._initialize_repository()

        # Initialize edit window
        self.edit_page_window = editpage.EditPage()
        self._connect_edit_window_signals()

        # Load start page
        project_name = self.data.get("last_project", self.project_drop_down.currentText())
        last_file = self.data.get("projects", {}).get(project_name, {}).get("last_ascii_file", "")
        self.load_page(last_file)

    def _initialize_repository(self) -> None:
        """Initialize Git repository for current project."""
        # Ensure projects exist
        while not self.data.get("projects", {}):
            result = PyQt6.QtWidgets.QMessageBox.question(
                self,
                "Kein Projekt",
                "Kein Projekt gefunden. Möchten Sie ein neues Projekt erstellen?",
                PyQt6.QtWidgets.QMessageBox.StandardButton.Yes |
                PyQt6.QtWidgets.QMessageBox.StandardButton.No
            )
            if result == PyQt6.QtWidgets.QMessageBox.StandardButton.Yes:
                self.create_new_project()
            else:
                logger.error("No projects available, exiting")
                sys.exit(1)

        # Set last project
        if not self.data.get("last_project"):
            first_project = list(self.data.get("projects").keys())[0]
            self.data.update({"last_project": first_project})

        project_name = self.data.get("last_project", self.project_drop_down.currentText())
        project_path = self.data.get("projects", {}).get(project_name, {}).get("path", "")

        if not project_path:
            logger.error(f"No path found for project {project_name}")
            PyQt6.QtWidgets.QMessageBox.critical(
                self,
                "Fehler",
                f"Kein Pfad für Projekt {project_name} gefunden"
            )
            return

        try:
            self.repo = notegit.NoteGit(project_path)
        except Exception as e:
            logger.error(f"Failed to initialize repository: {e}")
            PyQt6.QtWidgets.QMessageBox.critical(
                self,
                "Fehler",
                f"Projekt {project_name} konnte nicht geladen werden:\n{e}\n\n"
                "Das Projekt wird aus der Konfiguration entfernt."
            )
            self.data.get("projects", {}).pop(project_name, None)
            self.write_config()
            # Try to initialize another project
            self._initialize_repository()

    def _connect_edit_window_signals(self) -> None:
        """Connect edit window signals to main window handlers."""
        self.edit_page_window.ascii_file_changed.connect(self.load_page)
        self.edit_page_window.ascii_file_changed.connect(self.on_file_edited)
        self.edit_page_window.project_new_file.connect(self.on_upload_file)
        self.edit_page_window.geometry_update.connect(self.edit_page_window_geometry)
        self.edit_page_window.project_data_changed.connect(self.project_data_update)
        self.edit_page_window.show_commits_requested.connect(self.on_show_commits)

    def on_external_url(self, url: PyQt6.QtCore.QUrl) -> None:
        """
        Handle external URL click with user confirmation.

        Args:
            url: External URL to open
        """
        reply = PyQt6.QtWidgets.QMessageBox.question(
            self,
            "Proceed",
            f"Are you sure you want to open the URL '{url.toString()}' in an external browser?",
            PyQt6.QtWidgets.QMessageBox.StandardButton.Yes |
            PyQt6.QtWidgets.QMessageBox.StandardButton.No,
            PyQt6.QtWidgets.QMessageBox.StandardButton.No
        )

        if reply == PyQt6.QtWidgets.QMessageBox.StandardButton.Yes:
            logger.debug(f"Opening link {url.toString()} in external browser")
            PyQt6.QtGui.QDesktopServices.openUrl(url)

    def open_editor_window(
            self,
            project_data: Dict,
            project_name: str,
            file_name: str
    ) -> None:
        """
        Load data into editor window and show it.

        Args:
            project_data: Project configuration
            project_name: Name of the project
            file_name: Relative path to file
        """
        try:
            if not self.repo:
                raise ValueError("No repository initialized")

            file_list = self.repo.list_all_files()

            self.edit_page_window.load_document(
                project_data=project_data,
                project_name=project_name,
                file_name=file_name,
                file_list=file_list
            )

            geometry = self.data.get("edit_window_geometry", [300, 300, 600, 600])
            self.edit_page_window.set_geometry(geometry)
            self.edit_page_window.show()

        except Exception as e:
            logger.error(f"Failed to load document into editor: {e}")
            PyQt6.QtWidgets.QMessageBox.warning(
                self,
                "Fehler",
                f"Konnte Editor nicht laden:\n{e}"
            )

    def read_config(self) -> None:
        """Read configuration from JSON file."""
        home_dir = pathlib.Path.home()

        if os.name in ["nt", "windows"]:
            config_dir = home_dir / "AppData" / "Local" / "ThaNote"
        else:
            config_dir = home_dir / ".config" / "ThaNote"

        # Create config directory if it doesn't exist
        config_dir.mkdir(parents=True, exist_ok=True)

        self.config_filename = config_dir / "config.json"
        logger.debug(f"Reading config from {self.config_filename}")

        try:
            if self.config_filename.exists():
                data = json.loads(self.config_filename.read_text(encoding="utf-8"))
            else:
                logger.info("Config file doesn't exist, creating new one")
                data = {}
        except json.JSONDecodeError as e:
            logger.error(f"Config file corrupted: {e}")
            data = {}
        except Exception as e:
            logger.warning(f"Error reading config: {e}")
            data = {}

        self.data = data

    def write_config(self) -> None:
        """Write configuration to JSON file."""
        logger.info("Writing config")

        if not self.config_filename:
            logger.error("No config filename set")
            return

        try:
            with open(self.config_filename, "w", encoding="utf-8") as config_file:
                json.dump(self.data, config_file, indent=4)
            logger.debug("Config written successfully")
        except Exception as e:
            logger.error(f"Error writing config: {e}")

    def create_new_project(self) -> None:
        """Create or add a new project."""
        logger.debug("Creating new project")

        project_path_str = PyQt6.QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Directory"
        )

        if not project_path_str:
            logger.warning("No directory selected")
            return

        project_path = pathlib.Path(project_path_str)
        project_name = project_path.name

        # Check if project already exists
        if self.data.get("projects", {}).get(project_name, False):
            PyQt6.QtWidgets.QMessageBox.information(
                self,
                "Add Project",
                "Das Projekt ist bereits in der Liste"
            )
            logger.error("Project already in list")
            return

        index_file = self.data.get("index_file", "index.asciidoc")
        self.data.update({"index_file": index_file})

        filepath = project_path / index_file

        # Create index file if it doesn't exist
        if not filepath.exists():
            text_str = (
                f"== New project {project_name}\n\n"
                "AsciiDoc format\n\n"
                "link:https://docs.asciidoctor.org/asciidoc/latest/"
                "syntax-quick-reference/[Link to Quick Reference Guide]\n"
            )

            try:
                filepath.write_text(text_str, encoding="utf-8")
                logger.info(f"New index file created: {filepath}")
            except IOError as e:
                logger.error(f"Could not write index file {filepath}: {e}")
                PyQt6.QtWidgets.QMessageBox.critical(
                    self,
                    "Fehler",
                    f"Konnte Index-Datei nicht erstellen:\n{e}"
                )
                return
        else:
            logger.info(f"Index file {filepath} already exists")

        # Add project to config
        projects = self.data.get("projects", {})
        projects.update({
            project_name: {
                "path": project_path_str,
                "create_date": time.time(),
                "last_ascii_file": index_file
            }
        })
        self.data.update({"projects": projects})
        self.data.update({"last_project": project_name})

        # Update UI
        self.project_drop_down.addItem(project_name)

        # Initialize repository
        try:
            self.repo = notegit.NoteGit(project_path_str)
            self.repo.add_file(index_file)
        except Exception as e:
            logger.error(f"Failed to initialize git: {e}")
            PyQt6.QtWidgets.QMessageBox.warning(
                self,
                "Warnung",
                f"Git-Repository konnte nicht initialisiert werden:\n{e}"
            )

        self.load_page()

    def on_project_change(self) -> None:
        """Handle project dropdown change."""
        new_project_name = self.project_drop_down.currentText()
        logger.info(f"Project changed to {new_project_name}")

        self.data.update({"last_project": new_project_name})

        project_path = self.data.get("projects", {}).get(new_project_name, {}).get("path")
        if not project_path:
            logger.error(f"No path found for project {new_project_name}")
            return

        # Cleanup old repository
        if self.repo:
            self.repo.cleanup()

        # Initialize new repository
        try:
            self.repo = notegit.NoteGit(project_path)
        except Exception as e:
            logger.error(f"Failed to load project: {e}")
            PyQt6.QtWidgets.QMessageBox.critical(
                self,
                "Fehler",
                f"Projekt konnte nicht geladen werden:\n{e}"
            )
            return

        self.load_page()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        vbox = PyQt6.QtWidgets.QVBoxLayout()
        hbox = PyQt6.QtWidgets.QHBoxLayout()
        hbox2 = PyQt6.QtWidgets.QHBoxLayout()

        # Project dropdown
        self.project_drop_down.setMinimumWidth(130)
        hbox.addWidget(self.project_drop_down)

        project_highlight = self.data.get("last_project", "")
        for project_name in list(self.data.get("projects", {}).keys()):
            if not project_highlight:
                project_highlight = project_name
            self.project_drop_down.addItem(project_name)

        if project_highlight:
            self.project_drop_down.setCurrentText(project_highlight)

        # Disconnect any existing connections before connecting
        try:
            self.project_drop_down.currentTextChanged.disconnect()
        except TypeError:
            pass
        self.project_drop_down.currentTextChanged.connect(self.on_project_change)

        # Search box
        self.search_box.setEditable(True)
        self.search_box.setInsertPolicy(PyQt6.QtWidgets.QComboBox.InsertPolicy.NoInsert)
        hbox.addWidget(self.search_box)
        self.search_box.currentTextChanged.connect(self.on_search_local)

        # Search button
        search_button = PyQt6.QtWidgets.QPushButton("🔎")
        hbox.addWidget(search_button)
        search_button.clicked.connect(self.on_click_search)

        # Commits button
        open_git_button = PyQt6.QtWidgets.QPushButton("Commits")
        hbox.addWidget(open_git_button)
        open_git_button.clicked.connect(self.on_show_commits)

        # Add/New project button
        add_project_button = PyQt6.QtWidgets.QPushButton('Add/ New Project', self)
        hbox2.addWidget(add_project_button)
        add_project_button.clicked.connect(self.create_new_project)

        # Export button
        export_button = PyQt6.QtWidgets.QPushButton("Export", self)
        hbox2.addWidget(export_button)
        export_button.clicked.connect(self.on_export_pdf)

        # Edit button
        edit_page_button = PyQt6.QtWidgets.QPushButton("Edit Page", self)
        hbox2.addWidget(edit_page_button)
        edit_page_button.clicked.connect(self.on_click_edit_page)

        # Back button
        page_back_btn = PyQt6.QtWidgets.QPushButton("Back", self)
        hbox2.addWidget(page_back_btn)
        page_back_btn.clicked.connect(self.on_back_btn)

        # Layout assembly
        vbox.addLayout(hbox)
        vbox.addLayout(hbox2)
        vbox.addWidget(self.web_engine_view)

        main_widget = PyQt6.QtWidgets.QWidget()
        main_widget.setLayout(vbox)
        self.setCentralWidget(main_widget)

        # Set window geometry
        geometry = self.data.get("geometry", [300, 250, 900, 600])
        self.setGeometry(geometry[0], geometry[1], geometry[2], geometry[3])

        logger.info("Main window widgets created")

    def on_show_commits(self) -> None:
        """Show git commit browser dialog."""
        logger.info("Showing commit browser")

        # Prevent multiple windows
        if self.commit_browser is not None and self.commit_browser.isVisible():
            self.commit_browser.activateWindow()
            return

        if not self.repo:
            PyQt6.QtWidgets.QMessageBox.warning(
                self, "Fehler", "Kein Repository geladen"
            )
            return

        try:
            log_text = self.repo.get_commit_log()
        except Exception as e:
            logger.error(f"Could not get git log: {e}")
            PyQt6.QtWidgets.QMessageBox.warning(
                self,
                "Fehler",
                f"Git-Log konnte nicht abgerufen werden:\n{e}"
            )
            return

        # Create and show dialog (non-modal with .show())
        self.commit_browser = commitbrowser.CommitBrowserDialog(log_text, self)
        self.commit_browser.show()

    def on_search_local(self) -> None:
        """Search in current page."""
        search_text = self.search_box.currentText()
        self.web_page.findText(search_text)

    def on_click_search(self) -> None:
        """Perform semantic search across all files."""
        search_text = self.search_box.currentText().lower()
        logger.info(f"Search clicked for text: {search_text}")

        if not search_text:
            return

        project_name = self.project_drop_down.currentText()
        project_path = self.data.get("projects", {}).get(project_name, {}).get("path", "")

        if not project_path:
            logger.warning("No project path found")
            return

        if not self.repo:
            logger.warning("No repository initialized")
            return

        base_url = PyQt6.QtCore.QUrl.fromLocalFile(project_path + os.path.sep)

        # Add to search history
        if self.search_box.findText(search_text) < 0:
            self.search_box.addItem(search_text)

        # Perform search
        try:
            file_list = self.repo.list_all_files()
            search_result = notehelper.search_files(search_text, file_list, project_path)
            html_text = notehelper.text_2_html(search_result)
            self.web_page.setHtml(html_text, base_url)
        except Exception as e:
            logger.error(f"Search error: {e}")
            PyQt6.QtWidgets.QMessageBox.warning(
                self, "Fehler", f"Suchfehler:\n{e}"
            )

    def load_page(self, file_name: Optional[str] = None) -> None:
        """
        Load and display a page.

        Args:
            file_name: Relative path to file, or None for index file
        """
        if not file_name:
            file_name = self.data.get("index_file", "index.asciidoc")

        project_name = self.project_drop_down.currentText()
        logger.info(f"Loading page {file_name} from project {project_name}")

        project = self.data.get("projects", {}).get(project_name)
        if not project:
            logger.error(f"Project {project_name} not found")
            return

        project_path = project.get("path")
        if not project_path:
            logger.error(f"No path for project {project_name}")
            return

        base_url = PyQt6.QtCore.QUrl.fromLocalFile(project_path + os.path.sep)
        full_file_path = os.path.join(project_path, file_name)
        full_file_path = os.path.normpath(full_file_path)

        # Security check: ensure file is within project
        try:
            full_file_path_resolved = pathlib.Path(full_file_path).resolve()
            project_path_resolved = pathlib.Path(project_path).resolve()
            full_file_path_resolved.relative_to(project_path_resolved)
        except ValueError:
            logger.error(f"Security: File {full_file_path} outside project path")
            PyQt6.QtWidgets.QMessageBox.warning(
                self,
                "Sicherheitsfehler",
                "Die Datei liegt außerhalb des Projektverzeichnisses"
            )
            return

        file_extension = file_name.split(".")[-1].lower()

        # Handle different file types
        if file_extension in ["htm", "html", "txt", "jpg", "png", "jpeg"]:
            logger.info(f"Opening file in webview: {full_file_path}")
            self.web_page.load(
                PyQt6.QtCore.QUrl(pathlib.Path(full_file_path).absolute().as_uri())
            )
            return

        if file_extension in ["pdf", "ppt", "doc", "docx"]:
            logger.info(f"Opening file externally: {full_file_path}")
            self.on_external_url(
                PyQt6.QtCore.QUrl(pathlib.Path(full_file_path).absolute().as_uri())
            )
            return

        # Handle AsciiDoc files
        if file_extension in ["adoc", "asciidoc"]:
            logger.info(f"Loading asciidoc page {full_file_path}")
            self.current_file_name = file_name

            try:
                with open(full_file_path, "r", encoding="utf-8") as ascii_file:
                    text_in = ascii_file.read()
            except FileNotFoundError:
                logger.warning(f"File {full_file_path} not found, creating new")
                text_in = "== Empty page\n"

                os.makedirs(os.path.dirname(full_file_path), exist_ok=True)

                try:
                    with open(full_file_path, "w", encoding="utf-8") as ascii_file:
                        ascii_file.write(text_in)
                    if self.repo:
                        self.repo.add_file(file_name)
                except IOError as e:
                    logger.error(f"Problem writing new file {full_file_path}: {e}")
                    PyQt6.QtWidgets.QMessageBox.critical(
                        self, "Fehler", f"Datei konnte nicht erstellt werden:\n{e}"
                    )
                    return
            except Exception as e:
                logger.error(f"Error reading file {full_file_path}: {e}")
                PyQt6.QtWidgets.QMessageBox.critical(
                    self, "Fehler", f"Datei konnte nicht gelesen werden:\n{e}"
                )
                return

            try:
                html_text = notehelper.text_2_html(text_in)
                self.web_page.setHtml(html_text, base_url)
            except Exception as e:
                logger.error(f"Error converting to HTML: {e}")
                error_html = f"<h1>Conversion Error</h1><pre>{e}</pre>"
                self.web_page.setHtml(error_html, base_url)

    def on_file_edited(self, file_name: str) -> None:
        """
        Handle file edit event.

        Args:
            file_name: Relative path to edited file
        """
        logger.info(f"Git update {file_name}")
        if self.repo:
            self.repo.update_file(file_name)

    def on_upload_file(self, file_name: str) -> None:
        """
        Handle file upload event.

        Args:
            file_name: Relative path to uploaded file
        """
        logger.info(f"Adding uploaded file {file_name} to git")
        if self.repo:
            self.repo.add_file(file_name)

    def on_click_edit_page(self) -> None:
        """Open editor for current page."""
        logger.info("Edit clicked")

        project_name = self.project_drop_down.currentText()
        project = self.data.get("projects", {}).get(project_name)

        if not project:
            logger.error(f"Project '{project_name}' not found")
            return

        if not self.current_file_name:
            logger.warning("No file currently loaded to edit")
            PyQt6.QtWidgets.QMessageBox.warning(
                self, "Fehler", "Keine Datei zum Bearbeiten geladen"
            )
            return

        file_name = self.current_file_name
        file_extension = file_name.split(".")[-1].lower()

        if file_extension in ["adoc", "asciidoc"]:
            logger.info(f"Editing page {file_name}")
            self.open_editor_window(project, project_name, file_name)
        else:
            logger.warning(f"Cannot edit file type: {file_extension}")
            PyQt6.QtWidgets.QMessageBox.information(
                self,
                "Hinweis",
                f"Dateityp '{file_extension}' kann nicht bearbeitet werden"
            )

    def edit_page_window_geometry(self, geometry: tuple) -> None:
        """
        Save editor window geometry.

        Args:
            geometry: Tuple of (x, y, width, height)
        """
        self.data.update({"edit_window_geometry": geometry})

    def project_data_update(self, project_data: Dict) -> None:
        """
        Update project data.

        Args:
            project_data: Updated project data
        """
        project_name = self.project_drop_down.currentText()
        logger.info(f"Updating project data for {project_name}")
        self.data.get("projects", {}).update({project_name: project_data})

    def on_internal_url(self, url: PyQt6.QtCore.QUrl) -> None:
        """
        Handle internal file URL click.

        Args:
            url: Internal URL to open
        """
        logger.info(f"Opening internal URL: {url.toString()}")

        try:
            project_name = self.project_drop_down.currentText()
            project_path_str = self.data.get("projects", {}).get(
                project_name, {}
            ).get("path", "")

            if not project_path_str:
                logger.error("No project path configured")
                return

            project_path = pathlib.Path(project_path_str).resolve()
            url_path = pathlib.Path(url.toLocalFile()).resolve()

            # Security check
            try:
                relative_path = url_path.relative_to(project_path)
            except ValueError:
                logger.error(f"Security: Path {url_path} outside project {project_path}")
                PyQt6.QtWidgets.QMessageBox.warning(
                    self,
                    "Sicherheitsfehler",
                    "Die Datei liegt außerhalb des Projektverzeichnisses"
                )
                return

            if not url_path.is_file():
                logger.warning(f"File does not exist: {url_path}")
                PyQt6.QtWidgets.QMessageBox.warning(
                    self, "Fehler", f"Datei nicht gefunden:\n{url_path}"
                )
                return

            file_name = str(relative_path)
            logger.info(f"Loading relative page: {file_name}")
            self.load_page(file_name)

        except Exception as e:
            logger.error(f"Error in on_internal_url: {e}")
            PyQt6.QtWidgets.QMessageBox.critical(
                self, "Fehler", f"Fehler beim Öffnen der Datei:\n{e}"
            )

    def on_back_btn(self) -> None:
        """Navigate back in browser history."""
        logger.info("Back button clicked")
        self.web_page.triggerAction(
            PyQt6.QtWebEngineCore.QWebEnginePage.WebAction.Back
        )

    def on_export_pdf(self) -> None:
        """Export current page to PDF."""
        logger.info("Export clicked")

        try:
            export_dir = pathlib.Path.home() / "Downloads"
            if not export_dir.exists():
                export_dir = pathlib.Path.home()
        except Exception:
            export_dir = pathlib.Path.home()

        export_dir_str = self.data.get("export_dir", str(export_dir))
        export_dir = pathlib.Path(export_dir_str)

        current_page_name = pathlib.Path(self.web_page.url().fileName())
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        file_name = f"{date_str}_{current_page_name.stem}.pdf"
        default_pdf_path = export_dir / file_name

        pdf_file_dialog = PyQt6.QtWidgets.QFileDialog.getSaveFileName(
            self, "Save PDF file", str(default_pdf_path), "PDF (*.pdf)"
        )

        if pdf_file_dialog and pdf_file_dialog[0]:
            pdf_file_path_str = pdf_file_dialog[0]
            export_parent_dir = str(pathlib.Path(pdf_file_path_str).parent)
            self.data.update({"export_dir": export_parent_dir})

            try:
                self.web_engine_view.page().printToPdf(pdf_file_path_str)
                logger.info(f"Page exported to {pdf_file_path_str}")
            except Exception as e:
                logger.error(f"PDF export failed: {e}")
                PyQt6.QtWidgets.QMessageBox.critical(
                    self, "Fehler", f"PDF-Export fehlgeschlagen:\n{e}"
                )
        else:
            logger.warning("PDF export cancelled")

    @PyQt6.QtCore.pyqtSlot(PyQt6.QtGui.QCloseEvent)
    def closeEvent(self, event: PyQt6.QtGui.QCloseEvent) -> None:
        """
        Handle application close event.

        Args:
            event: Close event
        """
        logger.info("Closing the notebook window")

        # Save geometry
        geometry = self.geometry().getRect()
        self.data.update({"geometry": geometry})

        # Write config
        self.write_config()

        # Cleanup repository
        if self.repo:
            self.repo.cleanup()

        # Cleanup web view
        if self.web_engine_view:
            self.web_engine_view.setPage(None)
            self.web_engine_view.deleteLater()
            self.web_engine_view = None

        if self.web_page:
            self.web_page.deleteLater()
            self.web_page = None

        # Cleanup editor window
        if self.edit_page_window:
            self.edit_page_window.close()
            self.edit_page_window.deleteLater()
            self.edit_page_window = None

        # Cleanup commit browser
        if self.commit_browser:
            self.commit_browser.close()
            self.commit_browser.deleteLater()
            self.commit_browser = None


class NotebookApp:
    """Main application class."""

    def __init__(self):
        self.app = PyQt6.QtWidgets.QApplication(sys.argv)
        self.notes = Notebook()

    def run(self) -> None:
        """Run the application."""
        self.notes.show()
        self.app.exec()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger.info("Starting Notebook application")

    app = NotebookApp()
    app.run()
