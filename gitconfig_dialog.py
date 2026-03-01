# Copyright [2025] [ecki]
# SPDX-License-Identifier: Apache-2.0

"""
Git configuration dialog for managing remotes and user settings.
"""
import logging
from typing import Optional
import PyQt6.QtWidgets
import PyQt6.QtCore
import PyQt6.QtGui

logger = logging.getLogger(__name__)


class GitConfigDialog(PyQt6.QtWidgets.QDialog):
    """
    Dialog for Git configuration (remotes, user settings).
    """

    def __init__(self, git_wrapper, parent=None):
        """
        Initialize Git config dialog.

        Args:
            git_wrapper: NoteGit instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.git_wrapper = git_wrapper
        self.setWindowTitle("Git Konfiguration")
        self.setMinimumSize(600, 500)

        main_layout = PyQt6.QtWidgets.QVBoxLayout(self)

        # Create tabs
        tab_widget = PyQt6.QtWidgets.QTabWidget()
        tab_widget.addTab(self._create_remotes_tab(), "Remotes")
        tab_widget.addTab(self._create_user_tab(), "Benutzer")
        main_layout.addWidget(tab_widget)

        # Buttons
        button_layout = PyQt6.QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        self.close_button = PyQt6.QtWidgets.QPushButton("Schließen")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        main_layout.addLayout(button_layout)

        # Load initial data
        self.load_remotes()
        self.load_user_config()

    def _create_remotes_tab(self) -> PyQt6.QtWidgets.QWidget:
        """Create the remotes configuration tab."""
        widget = PyQt6.QtWidgets.QWidget()
        layout = PyQt6.QtWidgets.QVBoxLayout(widget)

        # Info label
        info_label = PyQt6.QtWidgets.QLabel(
            "Konfiguriere Git-Remotes für Synchronisation mit anderen Repositories."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Remotes list
        self.remotes_table = PyQt6.QtWidgets.QTableWidget()
        self.remotes_table.setColumnCount(2)
        self.remotes_table.setHorizontalHeaderLabels(["Name", "URL"])
        self.remotes_table.horizontalHeader().setStretchLastSection(True)
        self.remotes_table.setSelectionBehavior(
            PyQt6.QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        layout.addWidget(self.remotes_table)

        # Buttons for remote management
        remote_buttons = PyQt6.QtWidgets.QHBoxLayout()
        
        self.add_remote_btn = PyQt6.QtWidgets.QPushButton("Hinzufügen")
        self.add_remote_btn.clicked.connect(self.on_add_remote)
        remote_buttons.addWidget(self.add_remote_btn)
        
        self.edit_remote_btn = PyQt6.QtWidgets.QPushButton("Bearbeiten")
        self.edit_remote_btn.clicked.connect(self.on_edit_remote)
        remote_buttons.addWidget(self.edit_remote_btn)
        
        self.remove_remote_btn = PyQt6.QtWidgets.QPushButton("Entfernen")
        self.remove_remote_btn.clicked.connect(self.on_remove_remote)
        remote_buttons.addWidget(self.remove_remote_btn)
        
        remote_buttons.addStretch()
        layout.addLayout(remote_buttons)

        # Common remote templates
        templates_group = PyQt6.QtWidgets.QGroupBox("Schnellauswahl")
        templates_layout = PyQt6.QtWidgets.QVBoxLayout(templates_group)
        
        templates_label = PyQt6.QtWidgets.QLabel(
            "Gängige Git-Dienste:"
        )
        templates_layout.addWidget(templates_label)
        
        templates_info = PyQt6.QtWidgets.QLabel(
            "• GitHub: https://github.com/username/repo.git\n"
            "• GitLab: https://gitlab.com/username/repo.git\n"
            "• Bitbucket: https://bitbucket.org/username/repo.git\n"
            "• Lokales Netzwerk: /pfad/zum/repo.git oder file:///pfad/zum/repo.git"
        )
        templates_info.setStyleSheet("color: #666;")
        templates_layout.addWidget(templates_info)
        
        layout.addWidget(templates_group)

        return widget

    def _create_user_tab(self) -> PyQt6.QtWidgets.QWidget:
        """Create the user configuration tab."""
        widget = PyQt6.QtWidgets.QWidget()
        layout = PyQt6.QtWidgets.QVBoxLayout(widget)

        # Info label
        info_label = PyQt6.QtWidgets.QLabel(
            "Diese Informationen werden in Git-Commits verwendet."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Form layout
        form_layout = PyQt6.QtWidgets.QFormLayout()
        
        self.user_name_edit = PyQt6.QtWidgets.QLineEdit()
        self.user_name_edit.setPlaceholderText("z.B. Max Mustermann")
        form_layout.addRow("Name:", self.user_name_edit)
        
        self.user_email_edit = PyQt6.QtWidgets.QLineEdit()
        self.user_email_edit.setPlaceholderText("z.B. max@example.com")
        form_layout.addRow("E-Mail:", self.user_email_edit)
        
        layout.addLayout(form_layout)

        # Save button
        save_user_btn = PyQt6.QtWidgets.QPushButton("Speichern")
        save_user_btn.clicked.connect(self.on_save_user_config)
        
        btn_layout = PyQt6.QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(save_user_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

        return widget

    def load_remotes(self) -> None:
        """Load remotes from Git repository."""
        self.remotes_table.setRowCount(0)
        
        remotes = self.git_wrapper.get_remotes()
        
        for remote in remotes:
            row = self.remotes_table.rowCount()
            self.remotes_table.insertRow(row)
            
            name_item = PyQt6.QtWidgets.QTableWidgetItem(remote['name'])
            name_item.setFlags(name_item.flags() & ~PyQt6.QtCore.Qt.ItemFlag.ItemIsEditable)
            self.remotes_table.setItem(row, 0, name_item)
            
            url_item = PyQt6.QtWidgets.QTableWidgetItem(remote['url'])
            url_item.setFlags(url_item.flags() & ~PyQt6.QtCore.Qt.ItemFlag.ItemIsEditable)
            self.remotes_table.setItem(row, 1, url_item)

    def load_user_config(self) -> None:
        """Load Git user configuration."""
        config = self.git_wrapper.get_git_config()
        self.user_name_edit.setText(config.get('user.name', ''))
        self.user_email_edit.setText(config.get('user.email', ''))

    def on_add_remote(self) -> None:
        """Add a new remote."""
        dialog = RemoteEditDialog(parent=self)
        
        if dialog.exec() == PyQt6.QtWidgets.QDialog.DialogCode.Accepted:
            name = dialog.name_edit.text().strip()
            url = dialog.url_edit.text().strip()
            
            if not name or not url:
                PyQt6.QtWidgets.QMessageBox.warning(
                    self, "Fehler", "Name und URL müssen ausgefüllt sein."
                )
                return
            
            if self.git_wrapper.add_remote(name, url):
                PyQt6.QtWidgets.QMessageBox.information(
                    self, "Erfolg", f"Remote '{name}' wurde hinzugefügt."
                )
                self.load_remotes()
            else:
                PyQt6.QtWidgets.QMessageBox.critical(
                    self, "Fehler", f"Remote '{name}' konnte nicht hinzugefügt werden.\nMöglicherweise existiert der Name bereits."
                )

    def on_edit_remote(self) -> None:
        """Edit selected remote."""
        current_row = self.remotes_table.currentRow()
        
        if current_row < 0:
            PyQt6.QtWidgets.QMessageBox.warning(
                self, "Keine Auswahl", "Bitte wählen Sie einen Remote aus."
            )
            return
        
        name = self.remotes_table.item(current_row, 0).text()
        url = self.remotes_table.item(current_row, 1).text()
        
        dialog = RemoteEditDialog(name, url, edit_mode=True, parent=self)
        
        if dialog.exec() == PyQt6.QtWidgets.QDialog.DialogCode.Accepted:
            new_url = dialog.url_edit.text().strip()
            
            if not new_url:
                PyQt6.QtWidgets.QMessageBox.warning(
                    self, "Fehler", "URL muss ausgefüllt sein."
                )
                return
            
            if self.git_wrapper.update_remote_url(name, new_url):
                PyQt6.QtWidgets.QMessageBox.information(
                    self, "Erfolg", f"Remote '{name}' wurde aktualisiert."
                )
                self.load_remotes()
            else:
                PyQt6.QtWidgets.QMessageBox.critical(
                    self, "Fehler", f"Remote '{name}' konnte nicht aktualisiert werden."
                )

    def on_remove_remote(self) -> None:
        """Remove selected remote."""
        current_row = self.remotes_table.currentRow()
        
        if current_row < 0:
            PyQt6.QtWidgets.QMessageBox.warning(
                self, "Keine Auswahl", "Bitte wählen Sie einen Remote aus."
            )
            return
        
        name = self.remotes_table.item(current_row, 0).text()
        
        reply = PyQt6.QtWidgets.QMessageBox.question(
            self,
            "Remote entfernen",
            f"Möchten Sie den Remote '{name}' wirklich entfernen?",
            PyQt6.QtWidgets.QMessageBox.StandardButton.Yes |
            PyQt6.QtWidgets.QMessageBox.StandardButton.No,
            PyQt6.QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == PyQt6.QtWidgets.QMessageBox.StandardButton.Yes:
            if self.git_wrapper.remove_remote(name):
                PyQt6.QtWidgets.QMessageBox.information(
                    self, "Erfolg", f"Remote '{name}' wurde entfernt."
                )
                self.load_remotes()
            else:
                PyQt6.QtWidgets.QMessageBox.critical(
                    self, "Fehler", f"Remote '{name}' konnte nicht entfernt werden."
                )

    def on_save_user_config(self) -> None:
        """Save Git user configuration."""
        name = self.user_name_edit.text().strip()
        email = self.user_email_edit.text().strip()
        
        if not name or not email:
            PyQt6.QtWidgets.QMessageBox.warning(
                self, "Fehler", "Name und E-Mail müssen ausgefüllt sein."
            )
            return
        
        if self.git_wrapper.set_git_config(name, email):
            PyQt6.QtWidgets.QMessageBox.information(
                self, "Erfolg", "Git-Benutzerkonfiguration wurde gespeichert."
            )
        else:
            PyQt6.QtWidgets.QMessageBox.critical(
                self, "Fehler", "Konfiguration konnte nicht gespeichert werden."
            )


class RemoteEditDialog(PyQt6.QtWidgets.QDialog):
    """Dialog for adding/editing a remote."""
    
    def __init__(self, name: str = "", url: str = "", edit_mode: bool = False, parent=None):
        """
        Initialize remote edit dialog.
        
        Args:
            name: Remote name (for edit mode)
            url: Remote URL
            edit_mode: True if editing existing remote
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Remote bearbeiten" if edit_mode else "Remote hinzufügen")
        self.setMinimumWidth(500)
        
        layout = PyQt6.QtWidgets.QVBoxLayout(self)
        
        # Form
        form_layout = PyQt6.QtWidgets.QFormLayout()
        
        self.name_edit = PyQt6.QtWidgets.QLineEdit(name)
        self.name_edit.setPlaceholderText("z.B. origin")
        if edit_mode:
            self.name_edit.setReadOnly(True)
            self.name_edit.setStyleSheet("background-color: #f0f0f0;")
        form_layout.addRow("Name:", self.name_edit)
        
        self.url_edit = PyQt6.QtWidgets.QLineEdit(url)
        self.url_edit.setPlaceholderText("z.B. https://github.com/user/repo.git")
        form_layout.addRow("URL:", self.url_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = PyQt6.QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = PyQt6.QtWidgets.QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        ok_btn = PyQt6.QtWidgets.QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
