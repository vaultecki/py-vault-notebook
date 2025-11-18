# Copyright [2025] [ecki]
# SPDX-License-Identifier: Apache-2.0

"""
Edit page for AsciiDoc documents with syntax checking and file management.
"""
import logging
import notehelper
import commitbrowser
import docbrowser
import os
import pathlib
import shutil
import sys
from typing import Optional, Dict, List

import PyQt6
import PyQt6.QtCore
import PyQt6.QtGui
import PyQt6.QtWidgets

logger = logging.getLogger(__name__)


class EditPage(PyQt6.QtWidgets.QWidget):
    """
    Editor widget for AsciiDoc files with integrated Git support.

    Signals:
        ascii_file_changed: Emitted when file is saved (str: filename)
        project_data_changed: Emitted when project data changes (dict)
        project_new_file: Emitted when new file is added (str: filename)
        geometry_update: Emitted when window geometry changes (tuple)
        show_commits_requested: Emitted when user wants to see commits
    """
    ascii_file_changed = PyQt6.QtCore.pyqtSignal(str)
    project_data_changed = PyQt6.QtCore.pyqtSignal(dict)
    project_new_file = PyQt6.QtCore.pyqtSignal(str)
    geometry_update = PyQt6.QtCore.pyqtSignal(tuple)
    show_commits_requested = PyQt6.QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()

        # Data
        self.project_data: Optional[Dict] = None
        self.project_name: Optional[str] = None
        self.file_name: Optional[str] = None
        self.file_list: List[str] = []
        self.changed = False

        # UI
        main_layout = PyQt6.QtWidgets.QVBoxLayout()
        self.text_field = PyQt6.QtWidgets.QPlainTextEdit()
        main_layout.addWidget(self.text_field)
        main_layout.addWidget(self._init_format_field())

        # Settings
        self.setLayout(main_layout)
        self.text_field.setLineWrapMode(
            PyQt6.QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap
        )
        self.setWindowModality(PyQt6.QtCore.Qt.WindowModality.ApplicationModal)

        # Signals
        self._safe_connect_text_signal()

        # Shortcuts
        PyQt6.QtGui.QShortcut(
            PyQt6.QtGui.QKeySequence("Ctrl+S"), self
        ).activated.connect(self.on_save_changes)
        PyQt6.QtGui.QShortcut(
            PyQt6.QtGui.QKeySequence("ESC"), self
        ).activated.connect(self.close)

    def set_geometry(self, geometry: tuple) -> None:
        """
        Set window geometry.

        Args:
            geometry: Tuple of (x, y, width, height)
        """
        logger.info("Setting window size")
        self.setGeometry(geometry[0], geometry[1], geometry[2], geometry[3])

    def _init_format_field(self) -> PyQt6.QtWidgets.QWidget:
        """
        Initialize the toolbar with format and action buttons.

        Returns:
            Widget containing the toolbar
        """
        format_container = PyQt6.QtWidgets.QWidget(self)
        format_layout = PyQt6.QtWidgets.QGridLayout()
        format_container.setLayout(format_layout)

        # Internal link button
        show_docs_btn = PyQt6.QtWidgets.QPushButton("Show Docs")
        show_docs_btn.setToolTip("<b>Show all linkable internal documents</b>")
        format_layout.addWidget(show_docs_btn, 0, 0)
        show_docs_btn.clicked.connect(self.on_show_docs)

        # Open git button
        open_git_btn = PyQt6.QtWidgets.QPushButton("Commits")
        format_layout.addWidget(open_git_btn, 0, 1)
        open_git_btn.clicked.connect(self.on_open_git)

        # Save button
        save_btn = PyQt6.QtWidgets.QPushButton("Speichern")
        format_layout.addWidget(save_btn, 1, 0)
        save_btn.clicked.connect(self.on_save_changes)

        # Discard changes button
        discard_btn = PyQt6.QtWidgets.QPushButton("Verwerfen")
        format_layout.addWidget(discard_btn, 1, 1)
        discard_btn.clicked.connect(self.on_discard_changes)

        # Upload button
        upload_file_btn = PyQt6.QtWidgets.QPushButton("Upload File")
        upload_file_btn.setToolTip("<b>Add files (img, pdf, ..) to project</b>")
        format_layout.addWidget(upload_file_btn, 0, 3)
        upload_file_btn.clicked.connect(self.on_upload)

        # Info button
        info_button = PyQt6.QtWidgets.QPushButton("ℹ️")
        format_layout.addWidget(info_button, 1, 3)
        info_button.clicked.connect(self.on_click_info)

        return format_container

    def on_discard_changes(self) -> None:
        """Discard unsaved changes and reload original content."""
        if not self.changed:
            return

        reply = PyQt6.QtWidgets.QMessageBox.question(
            self,
            "Text verwerfen",
            "Wollen Sie den Text wirklich verwerfen?",
            PyQt6.QtWidgets.QMessageBox.StandardButton.Yes |
            PyQt6.QtWidgets.QMessageBox.StandardButton.No,
            PyQt6.QtWidgets.QMessageBox.StandardButton.No
        )

        if reply == PyQt6.QtWidgets.QMessageBox.StandardButton.Yes:
            logger.info("Discarding changes")
            self.text_field.clear()
            self.load_content()

        self.text_field.setFocus()

    def on_show_docs(self) -> None:
        """Show dialog to select and insert link to internal document."""
        logger.info("Show docs clicked")

        selected_file = docbrowser.DocBrowserDialog.get_selected_file(
            self.file_list, self
        )

        if not selected_file:
            return

        try:
            # Calculate relative path from current file to selected file
            current_dir = str(pathlib.Path(self.file_name).parent)
        except Exception as e:
            logger.error(f"Could not find parent directory of {self.file_name}: {e}")
            current_dir = "."

        relative_link_path = os.path.relpath(selected_file, current_dir)
        relative_link_path = relative_link_path.replace(os.path.sep, '/')

        link_text = f"link:{relative_link_path}[]"
        self.text_field.insertPlainText(link_text)
        self.text_field.setFocus()

    def on_open_git(self) -> None:
        """Open git commit browser."""
        logger.info("Open git clicked")
        self.show_commits_requested.emit()

    def on_upload(self) -> None:
        """Upload a file to the project directory."""
        logger.info("Upload clicked")

        # Determine import directory
        import_dir = os.path.expanduser("~")
        if os.name in ["nt", "windows"]:
            import_dir = os.path.join(import_dir, "Downloads")
        else:
            import_dir = os.path.join(import_dir, "Downloads")

        import_dir = self.project_data.get("import_dir", import_dir)

        # Select file to upload
        import_file_tuple = PyQt6.QtWidgets.QFileDialog.getOpenFileName(
            self, "Import file", import_dir, "*"
        )

        if not import_file_tuple or not import_file_tuple[0]:
            logger.warning("No file selected for upload")
            return

        import_file = import_file_tuple[0]
        file_name = os.path.basename(import_file)
        import_dir = os.path.dirname(import_file)

        # Update import directory in project data
        self.project_data.update({"import_dir": import_dir})
        self.project_data_changed.emit(self.project_data)

        # Get project path
        copy_dir = self.project_data.get("path")
        if not copy_dir:
            logger.error("No project path set")
            PyQt6.QtWidgets.QMessageBox.critical(
                self, "Fehler", "Kein Projektpfad gesetzt"
            )
            return

        # Select target location
        default_target = os.path.join(copy_dir, file_name)
        copy_file_tuple = PyQt6.QtWidgets.QFileDialog.getSaveFileName(
            self, "Save file to project path", default_target, "*"
        )

        if not copy_file_tuple or not copy_file_tuple[0]:
            logger.warning("No target location selected")
            return

        copy_file = copy_file_tuple[0]

        try:
            target_path = pathlib.Path(copy_file).resolve()
            project_path = pathlib.Path(copy_dir).resolve()

            # Ensure target is within project directory
            relative_path = target_path.relative_to(project_path)
            file_name_for_git = str(relative_path)

            # Create target directory if needed
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy(import_file, target_path)
            logger.info(f"File {import_file} copied to {target_path}")

            # Notify about new file
            self.project_new_file.emit(file_name_for_git)

        except ValueError:
            logger.error(f"Error: Target file {copy_file} not in project path {copy_dir}")
            PyQt6.QtWidgets.QMessageBox.warning(
                self,
                "Pfad-Fehler",
                "Die Datei muss innerhalb des Projektverzeichnisses gespeichert werden."
            )
        except Exception as e:
            logger.error(f"Error during file upload: {e}")
            PyQt6.QtWidgets.QMessageBox.critical(
                self, "Fehler", f"Fehler beim Datei-Upload: {e}"
            )

    def on_click_info(self) -> None:
        """Open AsciiDoc syntax reference in browser."""
        logger.info("Info clicked")

        url = PyQt6.QtCore.QUrl(
            "https://docs.asciidoctor.org/asciidoc/latest/syntax-quick-reference/"
        )

        reply = PyQt6.QtWidgets.QMessageBox.question(
            self,
            "Syntax Information",
            f"Open AsciiDoc Quick Reference {url.toString()}",
            PyQt6.QtWidgets.QMessageBox.StandardButton.Yes |
            PyQt6.QtWidgets.QMessageBox.StandardButton.No,
            PyQt6.QtWidgets.QMessageBox.StandardButton.No
        )

        if reply == PyQt6.QtWidgets.QMessageBox.StandardButton.Yes:
            logger.debug("Opening link in external browser")
            PyQt6.QtGui.QDesktopServices.openUrl(url)

    def on_text_changed(self) -> None:
        """Called when text is modified."""
        logger.debug("Text changed")
        self.changed = True

    def on_save_changes(self) -> None:
        """Save changes to file and validate AsciiDoc syntax."""
        if not self.changed:
            return

        if not self.project_data or not self.file_name:
            logger.error("Cannot save: missing project data or filename")
            PyQt6.QtWidgets.QMessageBox.warning(
                self, "Fehler", "Keine Projektdaten oder Dateiname vorhanden"
            )
            return

        text_file_path = os.path.join(
            self.project_data.get("path", ""),
            self.file_name
        )
        logger.debug(f"Saving changes to {text_file_path}")

        text = self.text_field.toPlainText()

        # Validate AsciiDoc syntax
        try:
            html_text = notehelper.text_2_html(text)
            logger.debug("AsciiDoc syntax validation successful")
        except Exception as e:
            logger.error(f"AsciiDoc syntax error: {e}")
            PyQt6.QtWidgets.QMessageBox.warning(
                self,
                "AsciiDoc Fehler",
                f"Fehler in der AsciiDoc-Syntax:\n\n{e}"
            )
            return

        # Write file
        try:
            with open(text_file_path, "w", encoding="utf-8") as text_file:
                text_file.write(text)
            logger.info(f"File saved: {text_file_path}")
        except Exception as e:
            logger.error(f"Error writing file: {e}")
            PyQt6.QtWidgets.QMessageBox.critical(
                self, "Fehler", f"Fehler beim Speichern:\n\n{e}"
            )
            return

        self.changed = False
        self.ascii_file_changed.emit(self.file_name)

    def load_document(
            self,
            project_data: Dict,
            project_name: str,
            file_name: str,
            file_list: List[str] = None
    ) -> None:
        """
        Load a document into the editor.

        Args:
            project_data: Project configuration dict
            project_name: Name of the project
            file_name: Relative path to the file
            file_list: List of all files in project (for doc browser)

        Raises:
            TypeError: If required parameters are missing
        """
        if not project_data:
            raise TypeError("Missing project data")
        if not project_name:
            raise TypeError("Missing project name")
        if not file_name:
            raise TypeError("Missing file name")

        self.project_data = project_data
        self.project_name = project_name
        self.file_name = file_name
        self.file_list = file_list or []

        logger.info(f"Editing {file_name} from project {project_name}")
        self.setWindowTitle(f'Notedit {file_name}')

        self.load_content()
        logger.info("Edit window loaded document")

    def _read_file_safely(self, path: pathlib.Path) -> str:
        """
        Safely read a text file with encoding fallback.

        Args:
            path: Path to file

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Try UTF-8 first, then fallback to latin-1
        try:
            with path.open("r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            logger.warning(f"UTF-8 decode failed for {path}, retrying with latin-1")
            with path.open("r", encoding="latin-1", errors="replace") as f:
                return f.read()

    def _safe_disconnect_text_signal(self) -> None:
        """Disconnect textChanged signal safely."""
        try:
            self.text_field.textChanged.disconnect(self.on_text_changed)
        except TypeError:
            pass  # Already disconnected

    def _safe_connect_text_signal(self) -> None:
        """Connect textChanged signal without risk of double-connecting."""
        self._safe_disconnect_text_signal()
        self.text_field.textChanged.connect(self.on_text_changed)

    def load_content(self) -> None:
        """Load file content into editor."""
        if not self.project_data or not self.file_name:
            logger.error("load_content called without valid project data or filename")
            self.text_field.setPlainText(
                "== FEHLER ==\nUngültige Projektdaten oder Dateiname."
            )
            return

        project_path = pathlib.Path(self.project_data.get("path", ""))
        file_path = project_path / self.file_name

        logger.info(f"Loading file content from {file_path}")

        # Disconnect textChanged to avoid setting changed=True while loading
        self._safe_disconnect_text_signal()

        try:
            text = self._read_file_safely(file_path)
            self.text_field.setPlainText(text)

        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            error_text = f"== FEHLER ==\nKonnte Datei nicht laden:\n{e}"
            self.text_field.setPlainText(error_text)

        finally:
            # Reset state and reconnect signals
            self.changed = False
            self.text_field.setFocus()
            self._safe_connect_text_signal()

    @PyQt6.QtCore.pyqtSlot(PyQt6.QtGui.QCloseEvent)
    def closeEvent(self, event: PyQt6.QtGui.QCloseEvent) -> None:
        """
        Handle window close event.

        Args:
            event: Close event
        """
        logger.info("Trying to close window")

        # Save geometry
        geometry = self.geometry().getRect()
        self.geometry_update.emit(geometry)

        # Check for unsaved changes
        if self.changed:
            msg_box = PyQt6.QtWidgets.QMessageBox()
            msg_box.setText("Möchten Sie die Änderungen speichern?")

            yes_btn = msg_box.addButton(
                PyQt6.QtWidgets.QMessageBox.StandardButton.Yes
            )
            yes_btn.setText("Speichern")

            no_btn = msg_box.addButton(
                PyQt6.QtWidgets.QMessageBox.StandardButton.No
            )
            no_btn.setText("Nicht speichern")

            msg_box.setDefaultButton(yes_btn)

            ret = msg_box.exec()
            if ret == PyQt6.QtWidgets.QMessageBox.StandardButton.Yes:
                logger.info("Close window - saving changes")
                self.on_save_changes()
            else:
                logger.info("Close window - changes not saved")
        else:
            logger.info("Close window - no changes")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Testing EditPage...")

    app = PyQt6.QtWidgets.QApplication(sys.argv)

    test_project_data = {
        "path": "/tmp/test_notebook",
        "create_date": 1734897219.1147738,
        "last_ascii_file": "index.asciidoc"
    }

    ex = EditPage()
    ex.load_document(test_project_data, "test1", "index.asciidoc")
    ex.show()

    sys.exit(app.exec())
