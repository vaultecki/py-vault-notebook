# Copyright [2025] [ecki]
# SPDX-License-Identifier: Apache-2.0

"""
Commit browser dialog for displaying Git commit history.
"""
import PyQt6.QtWidgets
import PyQt6.QtCore
import PyQt6.QtGui


class CommitBrowserDialog(PyQt6.QtWidgets.QDialog):
    """
    Simple non-modal dialog that displays Git commit log.
    """

    def __init__(self, log_text: str, parent=None):
        """
        Initialize commit browser dialog.

        Args:
            log_text: Formatted commit log text
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Commit History (Last 50)")
        self.setMinimumSize(600, 400)

        main_layout = PyQt6.QtWidgets.QVBoxLayout(self)

        # Text field for commit log
        text_field = PyQt6.QtWidgets.QPlainTextEdit()
        text_field.setReadOnly(True)

        # Use monospace font for clean alignment
        font = PyQt6.QtGui.QFontDatabase.systemFont(
            PyQt6.QtGui.QFontDatabase.SystemFont.FixedFont
        )
        text_field.setFont(font)
        text_field.setPlainText(log_text)

        main_layout.addWidget(text_field)

        # Close button
        close_button = PyQt6.QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.accept)

        button_layout = PyQt6.QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)

        # Important: Delete dialog instance when closed
        self.setAttribute(PyQt6.QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
