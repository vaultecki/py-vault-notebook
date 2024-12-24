import os
import sys

import PySignal

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import pyqtSlot
import logging


logger = logging.getLogger(__name__)


class EditPage(QtWidgets.QWidget):
    ascii_file_changed = PySignal.Signal()

    def __init__(self, project_data, project_name, file_name=None):
        super().__init__()
        self.project_data = project_data
        self.project_name = project_name
        if not file_name:
            file_name = self.project_data.get("last_ascii_file")
        self.file_name = file_name
        logger.info("edit {} from project {}".format(file_name, project_name))

        # ui
        main_layout = QtWidgets.QVBoxLayout()
        self.text_field = QtWidgets.QPlainTextEdit()
        main_layout.addWidget(self.text_field)
        main_layout.addWidget(self.init_format_field())

        # settings
        self.setLayout(main_layout)
        self.resize(900, 500)
        self.text_field.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        # signals
        self.connect_text_field_signals()

        # variables
        self.changed = False

        # loadings
        self.load_content()
        logger.info("Edit window initialized")

    def init_format_field(self):
        # main widget and layout
        format_container = QtWidgets.QWidget(self)
        format_layout = QtWidgets.QGridLayout()
        format_container.setLayout(format_layout)

        # internal link button
        int_link_btn = QtWidgets.QPushButton("Int Link")
        int_link_btn.setToolTip("<b>Internen Link hinzufügen</b><br><br>Fügen Sie einen internen Link hinzu")
        format_layout.addWidget(int_link_btn, 0, 0)
        # int_link_btn.clicked.connect(self.handle_click_link_buttons)

        # external link button
        ext_link_btn = QtWidgets.QPushButton("Ext Link")
        ext_link_btn.setToolTip("<b>Externen Link hinzufügen</b><br><br>Fügen Sie einen externen Link hinzu")
        format_layout.addWidget(ext_link_btn, 0, 1)
        # ext_link_btn.clicked.connect(lambda: self.handle_click_link_buttons(external=True))

        # open git
        open_git_btn = QtWidgets.QPushButton("Commits")
        format_layout.addWidget(open_git_btn, 0, 2)
        # open_git_btn.clicked.connect(self.on_open_git)

        # save btn
        save_btn = QtWidgets.QPushButton("Speichern")
        format_layout.addWidget(save_btn, 1, 0)
        save_btn.clicked.connect(self.save_changes)

        # reset changes button
        discard_btn = QtWidgets.QPushButton("Verwerfen")
        format_layout.addWidget(discard_btn, 1, 1)
        discard_btn.clicked.connect(self.on_discard_changes)

        # upload
        upload_file_btn = QtWidgets.QPushButton("Upload File")
        upload_file_btn.setToolTip("<b>Add files (img, pdf, ..) to project</b>")
        format_layout.addWidget(upload_file_btn, 0, 4)
        # upload_file_btn.clicked.connect(self.on_click_discard_changes)

        # info button
        info_button = QtWidgets.QPushButton("ℹ️")
        format_layout.addWidget(info_button, 1, 4)
        info_button.clicked.connect(self.on_click_info)

        return format_container

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

    def on_discard_changes(self):
        reply = QtWidgets.QMessageBox.question(self, "Text verwerfen",
                            "Wollen Sie den Text wirklich verwerfen?",
                            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                            QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            logger.info("discarding changes")
            self.text_field.clear()
            self.load_content()

        self.text_field.setFocus()

    def on_open_git(self):
        self.git_window = GitWindow(git_repo=self.repo, project_path=self.project_path, html_handler=self.html_handler, debug=self.debug)
        self.git_window.show()

    def on_enter_pressed(self, block_nr):
        prev_line_text = self.text_field.textCursor().block().previous().text()

        if not prev_line_text:
            return

        self.text_field.setFocus()

    def on_click_info(self):
        logger.info("info clicked")
        url = QtCore.QUrl("https://docs.asciidoctor.org/asciidoc/latest/syntax-quick-reference/")
        reply = QtWidgets.QMessageBox.question(self, "Syntax Information",
                        "Open Asciidoc Quick Reference {}".format(url),
                        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                        QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            logger.debug("open link in external browser")
            QtGui.QDesktopServices.openUrl(url)
        return

    def on_text_changed(self):
        logger.debug("text changed")
        self.changed = True

    def save_changes(self):
        text_file_path = os.path.join(self.project_data.get("path", ""), self.file_name)
        logger.debug("save changes in {}".format(text_file_path))
        text = self.text_field.toPlainText()
        with open(text_file_path, "w") as text_file:
            text_file.writelines(text)
        self.changed = False
        self.ascii_file_changed.emit(self.file_name)

    def load_content(self):
        text_file_path = os.path.join(self.project_data.get("path", ""), self.file_name)

        # disconnect signals
        self.disconnect_text_field_signals()

        self.text_field.clear()
        text = ""
        with open(text_file_path, "r") as text_file:
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

    @pyqtSlot(QtGui.QCloseEvent)
    def closeEvent(self, event):
        logger.info("Trying to close window")
        if self.changed:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText("Möchten Sie die Änderungen Speichern?")

            yes_btn = msg_box.addButton(QtWidgets.QMessageBox.StandardButton.Yes)
            yes_btn.setText("Speichern")
            no_btn = msg_box.addButton(QtWidgets.QMessageBox.StandardButton.No)
            no_btn.setText("Nicht speichern")

            msg_box.setDefaultButton(yes_btn)

            ret = msg_box.exec()
            if ret == QtWidgets.QMessageBox.StandardButton.Yes:
                logger.info("close window - save changes")
                self.save_changes()
            else:
                logger.info("close window - changes not saved")
        else:
            logger.info("close window - no changes")

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)

    logger.info("moin")

    app = QtWidgets.QApplication(sys.argv)
    ex = EditPage({"path": "/home/ecki/tmp2/notebooks/test1", "create_date": 1734897219.1147738,
            "last_ascii_file": "index.asciidoc"}, "test1", "index.asciidoc")
    ex.show()
    sys.exit(app.exec())