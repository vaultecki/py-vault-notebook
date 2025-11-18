# Copyright [2025] [ecki]
# SPDX-License-Identifier: Apache-2.0

"""
Document browser dialog for selecting internal documents to link.
"""
from typing import List, Optional
import PyQt6.QtWidgets
import PyQt6.QtCore


class DocBrowserDialog(PyQt6.QtWidgets.QDialog):
    """
    Dialog that displays a searchable list of files
    and returns the user's selection.
    """

    def __init__(self, file_list: List[str], parent=None):
        """
        Initialize document browser dialog.

        Args:
            file_list: List of file paths to display
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Select Internal Document")
        self.setMinimumSize(400, 300)

        self.all_files = sorted(file_list)
        self.selected_file: Optional[str] = None

        # UI Elements
        self.search_bar = PyQt6.QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Filter by filename...")

        self.list_widget = PyQt6.QtWidgets.QListWidget()
        self.list_widget.addItems(self.all_files)

        self.insert_button = PyQt6.QtWidgets.QPushButton("Insert Link")
        self.cancel_button = PyQt6.QtWidgets.QPushButton("Cancel")

        # Layout
        main_layout = PyQt6.QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.search_bar)
        main_layout.addWidget(self.list_widget)

        button_layout = PyQt6.QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.insert_button)
        main_layout.addLayout(button_layout)

        # Signals
        self.search_bar.textChanged.connect(self.filter_list)
        self.insert_button.clicked.connect(self.on_accept)
        self.cancel_button.clicked.connect(self.reject)
        self.list_widget.itemDoubleClicked.connect(self.on_accept)

        # Focus on search bar
        self.search_bar.setFocus()

    def filter_list(self, text: str) -> None:
        """
        Filter the file list based on search input.

        Args:
            text: Search text
        """
        self.list_widget.clear()
        search_text = text.lower()

        if not search_text:
            self.list_widget.addItems(self.all_files)
            return

        filtered_files = [
            f for f in self.all_files
            if search_text in f.lower()
        ]
        self.list_widget.addItems(filtered_files)

    def on_accept(self) -> None:
        """Set the selected file and close the dialog."""
        current_item = self.list_widget.currentItem()

        if current_item:
            self.selected_file = current_item.text()
            self.accept()
        elif self.list_widget.count() > 0:
            # If no item selected but list has items, select first one
            self.selected_file = self.list_widget.item(0).text()
            self.accept()

    @staticmethod
    def get_selected_file(
            file_list: List[str],
            parent=None
    ) -> Optional[str]:
        """
        Open the dialog modally and return the selected file.

        Args:
            file_list: List of files to display
            parent: Parent widget

        Returns:
            Selected filename or None if cancelled
        """
        dialog = DocBrowserDialog(file_list, parent)
        result = dialog.exec()  # .exec() is modal (blocking)

        if result == PyQt6.QtWidgets.QDialog.DialogCode.Accepted:
            return dialog.selected_file
        return None
