import logging
import notehelper
import os
import shutil
import sys

import PySignal
import PyQt6
import PyQt6.QtCore
import PyQt6.QtGui
import PyQt6.QtWidgets


logger = logging.getLogger(__name__)


class EditPage(PyQt6.QtWidgets.QWidget):
    ascii_file_changed = PySignal.Signal()
    project_data_changed = PySignal.Signal()
    project_new_file = PySignal.Signal()
    geometry_update = PySignal.Signal()

    def __init__(self, project_data, project_name, file_name):
        super().__init__()
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

        # ui
        main_layout = PyQt6.QtWidgets.QVBoxLayout()
        self.text_field = PyQt6.QtWidgets.QPlainTextEdit()
        main_layout.addWidget(self.text_field)
        main_layout.addWidget(self.init_format_field())
        self.setWindowTitle('Notedit {}'.format(file_name))

        # settings
        self.setLayout(main_layout)
        #self.resize(900, 500)
        self.text_field.setLineWrapMode(PyQt6.QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.setWindowModality(PyQt6.QtCore.Qt.WindowModality.ApplicationModal)

        # signals
        self.connect_text_field_signals()

        # variables
        self.changed = False

        # loadings
        self.load_content()
        logger.info("Edit window initialized")
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
        path_url_str = str(os.path.split(copy_file)[0])
        file_name = str(os.path.split(copy_file)[1])
        if path_url_str.startswith(copy_dir):
            logger.info("url starts with {}".format(copy_dir))
            if path_url_str > copy_dir:
                logger.info("recreate relative project path")
                cut_length = len(copy_dir) + 1
                if copy_dir.endswith("/"):
                    cut_length = cut_length - 1
                logger.info("copy file {} to project path as {}".format(import_file, copy_file))
                prefix = path_url_str[cut_length:]
                file_name = "{}/{}".format(prefix, file_name)
            shutil.copy(import_file, copy_file)
            self.project_new_file.emit(file_name)

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
            PyQt6.QtWidgets.QMessageBox.warning(f"error in asciidoc: {e}")
            return
        logger.debug("new html_text would be: {}".format(html_text))
        with open(text_file_path, "w", encoding="utf-8") as text_file:
            text_file.writelines(text)
        self.changed = False
        self.ascii_file_changed.emit(self.file_name)
        return

    def load_content(self):
        text_file_path = os.path.join(self.project_data.get("path", ""), self.file_name)

        # disconnect signals
        self.disconnect_text_field_signals()

        self.text_field.clear()
        with open(text_file_path, "r", encoding="utf-8") as text_file:
            text = text_file.readlines()
        for line in text:
            self.text_field.appendPlainText(line.strip())
        self.text_field.setFocus()
        self.changed = False
        self.connect_text_field_signals()

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
