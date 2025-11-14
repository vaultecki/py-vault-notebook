import logging
import notehelper
import os
import pathlib
import shutil
import sys

import PyQt6
import PyQt6.QtCore
import PyQt6.QtGui
import PyQt6.QtWidgets


logger = logging.getLogger(__name__)


class EditPage(PyQt6.QtWidgets.QWidget):
    ascii_file_changed = PyQt6.QtCore.pyqtSignal(str)
    project_data_changed = PyQt6.QtCore.pyqtSignal(dict)
    project_new_file = PyQt6.QtCore.pyqtSignal(str)
    geometry_update = PyQt6.QtCore.pyqtSignal(tuple)

    def __init__(self):
        super().__init__()

        self.project_data = None
        self.project_name = None
        self.file_name = None

        # ui
        main_layout = PyQt6.QtWidgets.QVBoxLayout()
        self.text_field = PyQt6.QtWidgets.QPlainTextEdit()
        main_layout.addWidget(self.text_field)
        main_layout.addWidget(self.init_format_field())

        # settings
        self.setLayout(main_layout)
        self.text_field.setLineWrapMode(PyQt6.QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.setWindowModality(PyQt6.QtCore.Qt.WindowModality.ApplicationModal)

        # signals
        self.connect_text_field_signals()

        # variables
        self.changed = False

        # add shortcuts
        PyQt6.QtGui.QShortcut(PyQt6.QtGui.QKeySequence("Ctrl+S"), self).activated.connect(self.on_save_changes)
        PyQt6.QtGui.QShortcut(PyQt6.QtGui.QKeySequence("ESC"), self).activated.connect(self.close)

    def set_geometry(self, geometry):
        logger.info("set window size")
        self.setGeometry(geometry[0], geometry[1], geometry[2], geometry[3])

    def init_format_field(self):
        # main widget and layout
        format_container = PyQt6.QtWidgets.QWidget(self)
        format_layout = PyQt6.QtWidgets.QGridLayout()
        format_container.setLayout(format_layout)

        # internal link button
        show_docs_btn = PyQt6.QtWidgets.QPushButton("show docs")
        show_docs_btn.setToolTip("<b>show all linkable internal documents</b>")
        format_layout.addWidget(show_docs_btn, 0, 0)
        show_docs_btn.clicked.connect(self.on_show_docs)

        # open git
        open_git_btn = PyQt6.QtWidgets.QPushButton("Commits")
        format_layout.addWidget(open_git_btn, 0, 1)
        open_git_btn.clicked.connect(self.on_open_git)

        # save btn
        save_btn = PyQt6.QtWidgets.QPushButton("Speichern")
        format_layout.addWidget(save_btn, 1, 0)
        save_btn.clicked.connect(self.on_save_changes)

        # reset changes button
        discard_btn = PyQt6.QtWidgets.QPushButton("Verwerfen")
        format_layout.addWidget(discard_btn, 1, 1)
        discard_btn.clicked.connect(self.on_discard_changes)

        # upload
        upload_file_btn = PyQt6.QtWidgets.QPushButton("Upload File")
        upload_file_btn.setToolTip("<b>Add files (img, pdf, ..) to project</b>")
        format_layout.addWidget(upload_file_btn, 0, 3)
        upload_file_btn.clicked.connect(self.on_upload)

        # info button
        info_button = PyQt6.QtWidgets.QPushButton("ℹ️")
        format_layout.addWidget(info_button, 1, 3)
        info_button.clicked.connect(self.on_click_info)

        return format_container

    def on_discard_changes(self):
        if not self.changed:
            return
        reply = PyQt6.QtWidgets.QMessageBox.question(self, "Text verwerfen",
                            "Wollen Sie den Text wirklich verwerfen?",
                            PyQt6.QtWidgets.QMessageBox.StandardButton.Yes | PyQt6.QtWidgets.QMessageBox.StandardButton.No,
                            PyQt6.QtWidgets.QMessageBox.StandardButton.No)
        if reply == PyQt6.QtWidgets.QMessageBox.StandardButton.Yes:
            logger.info("discarding changes")
            self.text_field.clear()
            self.load_content()

        self.text_field.setFocus()
        return

    def on_show_docs(self):
        logger.info("clicked show docs")
        # todo implement something useful
        pass

    def on_open_git(self):
        logger.info("open git clicked")
        pass

    def on_upload(self):
        logger.info("upload clicked")
        import_dir = os.path.expanduser("~")
        if os.name in ["nt", "windows"]:
            import_dir = os.path.join(import_dir, "Downloads")
        else:
            import_dir = os.path.join(import_dir, "Downloads")
        import_dir = self.project_data.get("import_dir", import_dir)
        import_file = PyQt6.QtWidgets.QFileDialog.getOpenFileName(self, "Import file", import_dir, "*")
        if not import_file:
            logger.warning("no file for upload selected")
            return
        if not import_file[0]:
            logger.warning("no file for upload selected")
            return
        import_file = import_file[0]
        file_name = os.path.split(import_file)[1]
        import_dir = os.path.split(import_file)[0]
        self.project_data.update({"import_dir": import_dir})
        self.project_data_changed.emit(self.project_data)
        copy_dir = self.project_data.get("path")
        if not copy_dir:
            logger.error("no project path set")
            return
        file_name = os.path.join(copy_dir, file_name)
        copy_file = PyQt6.QtWidgets.QFileDialog.getSaveFileName(self, "Save file to project path", file_name, "*")
        if not copy_file:
            logger.warning("no file for upload target selected")
            return
        if not copy_file[0]:
            logger.warning("no file for upload target selected")
            return
        copy_file = copy_file[0]
        try:
            target_path = pathlib.Path(copy_file)
            project_path = pathlib.Path(copy_dir)

            relative_path = target_path.relative_to(project_path)
            file_name_for_git = str(relative_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy(import_file, target_path)
            logger.info(f"Datei {import_file} nach {target_path} kopiert.")
            self.project_new_file.emit(file_name_for_git)
        except ValueError:
            logger.error(f"Fehler: Zieldatei {copy_file} liegt nicht im Projektpfad {copy_dir}.")
            PyQt6.QtWidgets.QMessageBox.warning(self, "Pfad-Fehler",
                                                "Die Datei muss innerhalb des Projektverzeichnisses gespeichert werden.")
        except Exception as e:
            logger.error(f"Fehler beim Datei-Upload: {e}")

    def on_click_info(self):
        logger.info("info clicked")
        url = PyQt6.QtCore.QUrl("https://docs.asciidoctor.org/asciidoc/latest/syntax-quick-reference/")
        reply = PyQt6.QtWidgets.QMessageBox.question(self, "Syntax Information",
                        "Open Asciidoc Quick Reference {}".format(url),
                        PyQt6.QtWidgets.QMessageBox.StandardButton.Yes | PyQt6.QtWidgets.QMessageBox.StandardButton.No,
                        PyQt6.QtWidgets.QMessageBox.StandardButton.No)
        if reply == PyQt6.QtWidgets.QMessageBox.StandardButton.Yes:
            logger.debug("open link in external browser")
            PyQt6.QtGui.QDesktopServices.openUrl(url)
        return

    def on_text_changed(self):
        logger.debug("text changed")
        self.changed = True

    def on_save_changes(self):
        if not self.changed:
            return
        text_file_path = os.path.join(self.project_data.get("path", ""), self.file_name)
        logger.debug("save changes in {}".format(text_file_path))
        text = self.text_field.toPlainText()
        try:
            html_text = notehelper.text_2_html(text)
        except Exception as e:
            logger.error("error in asciidoc: {}".format(e))
            PyQt6.QtWidgets.QMessageBox.warning(self, "Asciidoc error",f"error in asciidoc: {e}")
            return
        logger.debug("new html_text would be: {}".format(html_text))
        with open(text_file_path, "w", encoding="utf-8") as text_file:
            text_file.writelines(text)
        self.changed = False
        self.ascii_file_changed.emit(self.file_name)
        return

    def load_document(self, project_data, project_name, file_name):
        if not project_data:
            raise TypeError("missing project data")
        if not project_name:
            raise TypeError("missing project name")
        if not file_name:
            raise TypeError("missing file name")

        self.project_data = project_data
        self.project_name = project_name
        self.file_name = file_name

        logger.info("edit {} from project {}".format(file_name, project_name))
        self.setWindowTitle('Notedit {}'.format(file_name))

        self.load_content()
        logger.info("Edit window loaded document")

    def _read_file_safely(self, path: pathlib.Path) -> str:
        """
        Safely read a text file.
        - Handles missing files
        - Uses UTF-8 with fallback
        - Raises exceptions for caller
        """
        if not path.exists():
            raise FileNotFoundError(f"Datei nicht gefunden: {path}")

        # try UTF-8 first, then fallback
        try:
            with path.open("r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            logger.warning(f"UTF-8 decode failed for {path}, retrying latin-1")
            with path.open("r", encoding="latin-1", errors="replace") as f:
                return f.read()

    def _safe_disconnect_text_signal(self):
        """Disconnect textChanged safely (avoid TypeError if not connected)."""
        try:
            self.text_field.textChanged.disconnect(self.on_text_changed)
        except TypeError:
            pass  # already disconnected

    def _safe_connect_text_signal(self):
        """Reconnect textChanged without risk of double-connecting."""
        self._safe_disconnect_text_signal()
        self.text_field.textChanged.connect(self.on_text_changed)

    def load_content(self):
        if not self.project_data or not self.file_name:
            logger.error("load_content called without valid project data or filename")
            self.text_field.setPlainText("== FEHLER ==\nUngültige Projektdaten oder Dateiname.")
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
            logger.error(f"Fehler beim Laden von {file_path}: {e}")
            error_text = f"== FEHLER ==\nKonnte Datei nicht laden:\n{e}"
            self.text_field.setPlainText(error_text)

        finally:
            # Reset state and reconnect signals
            self.changed = False
            self.text_field.setFocus()
            self._safe_connect_text_signal()

    def connect_text_field_signals(self):
        self.text_field.textChanged.connect(self.on_text_changed)

    def disconnect_text_field_signals(self):
        self.text_field.textChanged.disconnect(self.on_text_changed)

    @PyQt6.QtCore.pyqtSlot(PyQt6.QtGui.QCloseEvent)
    def closeEvent(self, event):
        logger.info("Trying to close window")
        geometry = (self.frameGeometry().x(), self.frameGeometry().y(), self.frameGeometry().width(), self.frameGeometry().height())
        self.geometry_update.emit(geometry)
        if self.changed:
            msg_box = PyQt6.QtWidgets.QMessageBox()
            msg_box.setText("Möchten Sie die Änderungen Speichern?")

            yes_btn = msg_box.addButton(PyQt6.QtWidgets.QMessageBox.StandardButton.Yes)
            yes_btn.setText("Speichern")
            no_btn = msg_box.addButton(PyQt6.QtWidgets.QMessageBox.StandardButton.No)
            no_btn.setText("Nicht speichern")

            msg_box.setDefaultButton(yes_btn)

            ret = msg_box.exec()
            if ret == PyQt6.QtWidgets.QMessageBox.StandardButton.Yes:
                logger.info("close window - save changes")
                self.on_save_changes()
            else:
                logger.info("close window - changes not saved")
        else:
            logger.info("close window - no changes")


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)

    logger.info("moin")

    app = PyQt6.QtWidgets.QApplication(sys.argv)
    ex = EditPage({"path": "/home/ecki/temp/notebooks/private", "create_date": 1734897219.1147738,
            "last_ascii_file": "index.asciidoc"}, "test1", "index.asciidoc")
    ex.show()
    sys.exit(app.exec())
