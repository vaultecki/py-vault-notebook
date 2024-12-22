import io
import json
import os
import sys
import time

import asciidoc
import PySignal

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView
import logging


logger = logging.getLogger(__name__)


class QVLine(QtWidgets.QFrame):
    def __init__(self):
        super(QVLine, self).__init__()

        self.setFrameShape(QtWidgets.QFrame().Shape.VLine)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Raised)


class EditPage(QtWidgets.QMainWindow):
    window_closed_signal = PySignal.Signal()

    def __init__(self, project_data, project_name, file_name=None):
        super(EditPage, self).__init__()

        self.project_data = project_data
        self.project_name = project_name
        if not file_name:
            file_name = self.project_data.get("last_ascii_file")
        self.file_name = file_name

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
        logger.info("Edit window initialized")

    def init_format_field(self):
        # main widget and layout
        format_container = QtWidgets.QWidget(self)
        format_layout = QtWidgets.QGridLayout()
        format_container.setLayout(format_layout)

        # internal link button
        int_link_btn = QtWidgets.QPushButton("Int Link")
        int_link_btn.setToolTip("<b>Internen Link hinzufügen</b><br><br>Fügen Sie einen internen Link hinzu")
        format_layout.addWidget(int_link_btn, 0, 6, 1, 1)
        # int_link_btn.clicked.connect(self.handle_click_link_buttons)

        # external link button
        ext_link_btn = QtWidgets.QPushButton("Ext Link")
        ext_link_btn.setToolTip("<b>Externen Link hinzufügen</b><br><br>Fügen Sie einen externen Link hinzu")
        format_layout.addWidget(ext_link_btn, 0, 7, 1, 1)
        # ext_link_btn.clicked.connect(lambda: self.handle_click_link_buttons(external=True))

        # open git
        open_git_btn = QtWidgets.QPushButton("Commits")
        format_layout.addWidget(open_git_btn, 0, 10)
        open_git_btn.clicked.connect(self.on_open_git)

        format_layout.addWidget(QVLine(), 0, 8, 2, 1)  # line

        # save btn
        save_change_btn = QtWidgets.QPushButton("Speichern")
        format_layout.addWidget(save_change_btn, 1, 9)
        # save_change_btn.clicked.connect(self.on_click_save)

        # reset changes button
        discard_btn = QtWidgets.QPushButton("Verwerfen")
        format_layout.addWidget(discard_btn, 0, 9)
        # discard_btn.clicked.connect(self.on_click_discard_changes)

        # preview
        preview_btn = QtWidgets.QPushButton("Preview")
        format_layout.addWidget(preview_btn, 0, 9)
        # preview_btn.clicked.connect(self.on_click_discard_changes)

        # preview
        upload_file_btn = QtWidgets.QPushButton("Upload File")
        format_layout.addWidget(upload_file_btn, 0, 9)
        # upload_file_btn.clicked.connect(self.on_click_discard_changes)

        # info button
        info_button = QtWidgets.QPushButton("ℹ️")
        format_layout.addWidget(info_button, 1, 10)
        # info_button.clicked.connect(self.on_click_info)

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
        logger.debug("save changes")
        text_file_path = os.path.join(self.project_data.get("path", ""), self.file_name)
        text = self.text_field.toPlainText()

        with open(text_file_path, "w") as text_file:
            text_file.writelines(text)

        # todo if necessary ask for commit name
        # commit
        #if self.repo.is_dirty():
        #    index = len(list(self.repo.iter_commits()))
        #    self.repo.index.add(["index.html"])
        #    self.repo.index.commit("commit_{}".format(index + 1))
        #    self.logger.debug("Changes committed; Commits count: {}".format(index))
        #else:
        #    self.logger.info("No change - Not committed")

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
        logger.info("Trying to close window")
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
            # elif ret == QtWidgets.QMessageBox.StandardButton.No:
            #     self.window_closed_sygnal.emit()
            # elif ret == QtWidgets.QMessageBox.StandardButton.Cancel:
            #     event.ignore()
        # else:
        #     self.window_closed_sygnal.emit()


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)

    logger.info("moin")

    app = QtWidgets.QApplication(sys.argv)
    ex = EditPage({"path": "/home/ecki/tmp2/notebooks/test1", "create_date": 1734897219.1147738,
            "last_ascii_file": "index.asciidoc"}, "test1", "index.asciidoc")
    ex.show()
    sys.exit(app.exec())