# Copyright [2025] [ecki]
# SPDX-License-Identifier: Apache-2.0

"""
File history and diff viewer for Git versions.
"""
import logging
from typing import Optional, List, Dict
import PyQt6.QtWidgets
import PyQt6.QtCore
import PyQt6.QtGui

logger = logging.getLogger(__name__)


class HistoryViewerDialog(PyQt6.QtWidgets.QDialog):
    """
    Dialog for viewing file history and comparing versions.
    """

    def __init__(self, git_wrapper, file_path: str, parent=None):
        """
        Initialize history viewer dialog.

        Args:
            git_wrapper: NoteGit instance
            file_path: Relative path to file in repository
            parent: Parent widget
        """
        super().__init__(parent)
        self.git_wrapper = git_wrapper
        self.file_path = file_path
        self.commits: List[Dict] = []
        
        self.setWindowTitle(f"Versions-Historie: {file_path}")
        self.setMinimumSize(900, 600)

        main_layout = PyQt6.QtWidgets.QVBoxLayout(self)

        # Info label
        info_label = PyQt6.QtWidgets.QLabel(
            f"Zeigt alle Versionen von: <b>{file_path}</b>"
        )
        main_layout.addWidget(info_label)

        # Splitter for list and content
        splitter = PyQt6.QtWidgets.QSplitter(PyQt6.QtCore.Qt.Orientation.Horizontal)
        
        # Left side: Commit list
        left_widget = self._create_commit_list()
        splitter.addWidget(left_widget)
        
        # Right side: Tabs for content and diff
        right_widget = self._create_content_tabs()
        splitter.addWidget(right_widget)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)

        # Buttons
        button_layout = PyQt6.QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        self.close_button = PyQt6.QtWidgets.QPushButton("Schließen")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        main_layout.addLayout(button_layout)

        # Load history
        self.load_history()
        
        # Important: Delete dialog instance when closed
        self.setAttribute(PyQt6.QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)

    def _create_commit_list(self) -> PyQt6.QtWidgets.QWidget:
        """Create the commit list widget."""
        widget = PyQt6.QtWidgets.QWidget()
        layout = PyQt6.QtWidgets.QVBoxLayout(widget)
        
        label = PyQt6.QtWidgets.QLabel("Versionen:")
        layout.addWidget(label)
        
        self.commit_list = PyQt6.QtWidgets.QListWidget()
        self.commit_list.currentRowChanged.connect(self.on_commit_selected)
        layout.addWidget(self.commit_list)
        
        # Compare button
        self.compare_button = PyQt6.QtWidgets.QPushButton("Vergleichen")
        self.compare_button.setToolTip("Vergleiche ausgewählte Version mit vorheriger")
        self.compare_button.clicked.connect(self.on_compare_with_previous)
        layout.addWidget(self.compare_button)
        
        return widget

    def _create_content_tabs(self) -> PyQt6.QtWidgets.QWidget:
        """Create tabs for content view and diff view."""
        self.tab_widget = PyQt6.QtWidgets.QTabWidget()
        
        # Content tab
        self.content_view = PyQt6.QtWidgets.QPlainTextEdit()
        self.content_view.setReadOnly(True)
        self.content_view.setLineWrapMode(
            PyQt6.QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap
        )
        font = PyQt6.QtGui.QFontDatabase.systemFont(
            PyQt6.QtGui.QFontDatabase.SystemFont.FixedFont
        )
        self.content_view.setFont(font)
        self.tab_widget.addTab(self.content_view, "Inhalt")
        
        # Diff tab
        self.diff_view = PyQt6.QtWidgets.QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setLineWrapMode(
            PyQt6.QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap
        )
        self.diff_view.setFont(font)
        self.tab_widget.addTab(self.diff_view, "Änderungen (Diff)")
        
        return self.tab_widget

    def load_history(self) -> None:
        """Load commit history for the file."""
        self.commits = self.git_wrapper.get_file_history(self.file_path)
        
        self.commit_list.clear()
        
        for commit in self.commits:
            item_text = (
                f"{commit['hash']} | {commit['date']}\n"
                f"{commit['message'][:50]}\n"
                f"von {commit['author']}"
            )
            item = PyQt6.QtWidgets.QListWidgetItem(item_text)
            item.setData(PyQt6.QtCore.Qt.ItemDataRole.UserRole, commit)
            self.commit_list.addItem(item)
        
        if self.commits:
            self.commit_list.setCurrentRow(0)

    def on_commit_selected(self, index: int) -> None:
        """
        Handle commit selection.
        
        Args:
            index: Selected row index
        """
        if index < 0 or index >= len(self.commits):
            return
        
        commit = self.commits[index]
        
        # Load file content at this commit
        content = self.git_wrapper.get_file_at_commit(
            self.file_path, 
            commit['full_hash']
        )
        
        if content:
            self.content_view.setPlainText(content)
            
            # Show commit info
            info = (
                f"Commit: {commit['hash']}\n"
                f"Datum: {commit['date']}\n"
                f"Autor: {commit['author']}\n"
                f"Nachricht: {commit['message']}\n"
                f"\n{'='*60}\n\n"
            )
            self.content_view.setPlainText(info + content)
        else:
            self.content_view.setPlainText(
                "Fehler: Datei-Inhalt konnte nicht geladen werden."
            )
        
        # Switch to content tab
        self.tab_widget.setCurrentIndex(0)

    def on_compare_with_previous(self) -> None:
        """Compare selected version with previous version."""
        current_row = self.commit_list.currentRow()
        
        if current_row < 0:
            PyQt6.QtWidgets.QMessageBox.warning(
                self, "Keine Auswahl", "Bitte wählen Sie eine Version aus."
            )
            return
        
        if current_row >= len(self.commits) - 1:
            PyQt6.QtWidgets.QMessageBox.information(
                self, "Info", "Dies ist die älteste Version, kein Vergleich möglich."
            )
            return
        
        # Current (newer) and previous (older) commit
        newer_commit = self.commits[current_row]
        older_commit = self.commits[current_row + 1]
        
        # Get diff
        diff = self.git_wrapper.get_file_diff(
            self.file_path,
            older_commit['full_hash'],
            newer_commit['full_hash']
        )
        
        # Format and colorize diff
        formatted_diff = self._format_diff(diff, older_commit, newer_commit)
        
        self.diff_view.setPlainText(formatted_diff)
        
        # Switch to diff tab
        self.tab_widget.setCurrentIndex(1)

    def _format_diff(self, diff: str, older_commit: Dict, newer_commit: Dict) -> str:
        """
        Format diff output with header.
        
        Args:
            diff: Raw diff output
            older_commit: Older commit info
            newer_commit: Newer commit info
            
        Returns:
            Formatted diff string
        """
        header = (
            f"Vergleich von Versionen:\n"
            f"\n"
            f"ALT:  {older_commit['hash']} | {older_commit['date']}\n"
            f"      {older_commit['message']}\n"
            f"      von {older_commit['author']}\n"
            f"\n"
            f"NEU:  {newer_commit['hash']} | {newer_commit['date']}\n"
            f"      {newer_commit['message']}\n"
            f"      von {newer_commit['author']}\n"
            f"\n"
            f"{'='*70}\n"
            f"\n"
        )
        
        if not diff:
            return header + "Keine Änderungen zwischen diesen Versionen."
        
        # Add legend
        legend = (
            "Legende:\n"
            "  - Zeilen beginnend mit '-' wurden gelöscht\n"
            "  - Zeilen beginnend mit '+' wurden hinzugefügt\n"
            "  - Zeilen beginnend mit ' ' (Leerzeichen) sind unverändert\n"
            f"\n"
            f"{'='*70}\n"
            f"\n"
        )
        
        return header + legend + diff


class QuickCompareDialog(PyQt6.QtWidgets.QDialog):
    """
    Quick dialog to compare current file with last committed version.
    """
    
    def __init__(self, git_wrapper, file_path: str, current_content: str, parent=None):
        """
        Initialize quick compare dialog.
        
        Args:
            git_wrapper: NoteGit instance
            file_path: Relative path to file
            current_content: Current file content
            parent: Parent widget
        """
        super().__init__(parent)
        self.git_wrapper = git_wrapper
        self.file_path = file_path
        self.current_content = current_content
        
        self.setWindowTitle(f"Änderungen: {file_path}")
        self.setMinimumSize(700, 500)
        
        layout = PyQt6.QtWidgets.QVBoxLayout(self)
        
        # Info
        info_label = PyQt6.QtWidgets.QLabel(
            "Zeigt Änderungen gegenüber der letzten gespeicherten Version"
        )
        layout.addWidget(info_label)
        
        # Diff view
        self.diff_view = PyQt6.QtWidgets.QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setLineWrapMode(
            PyQt6.QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap
        )
        font = PyQt6.QtGui.QFontDatabase.systemFont(
            PyQt6.QtGui.QFontDatabase.SystemFont.FixedFont
        )
        self.diff_view.setFont(font)
        layout.addWidget(self.diff_view)
        
        # Buttons
        button_layout = PyQt6.QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = PyQt6.QtWidgets.QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Load and show diff
        self.load_diff()
        
        self.setAttribute(PyQt6.QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)

    def load_diff(self) -> None:
        """Load and display diff."""
        # Get last commit
        history = self.git_wrapper.get_file_history(self.file_path, max_count=1)
        
        if not history:
            self.diff_view.setPlainText(
                "Keine vorherige Version gefunden.\n"
                "Dies ist möglicherweise eine neue Datei."
            )
            return
        
        last_commit = history[0]
        
        # Get diff (comparing HEAD with working tree would be better,
        # but we compare with last commit for simplicity)
        diff = self.git_wrapper.get_file_diff(
            self.file_path,
            last_commit['full_hash'],
            None  # Compare with working tree
        )
        
        header = (
            f"Änderungen seit letztem Commit:\n"
            f"\n"
            f"Letzter Commit: {last_commit['hash']} | {last_commit['date']}\n"
            f"                {last_commit['message']}\n"
            f"                von {last_commit['author']}\n"
            f"\n"
            f"{'='*70}\n"
            f"\n"
        )
        
        if not diff:
            self.diff_view.setPlainText(header + "Keine Änderungen.")
        else:
            legend = (
                "Legende:\n"
                "  - Zeilen mit '-' wurden gelöscht\n"
                "  - Zeilen mit '+' wurden hinzugefügt\n"
                f"\n"
                f"{'='*70}\n"
                f"\n"
            )
            self.diff_view.setPlainText(header + legend + diff)
