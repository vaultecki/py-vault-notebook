import PyQt6.QtWidgets
import PyQt6.QtCore
import PyQt6.QtGui


class CommitBrowserDialog(PyQt6.QtWidgets.QDialog):
    """
    Ein einfacher, nicht-modaler Dialog, der den Git-Commit-Log anzeigt.
    """

    def __init__(self, log_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Commit-Verlauf (Letzte 50)")
        self.setMinimumSize(600, 400)

        main_layout = PyQt6.QtWidgets.QVBoxLayout(self)

        text_field = PyQt6.QtWidgets.QPlainTextEdit()
        text_field.setReadOnly(True)
        # Verwenden einer Monospace-Schriftart für saubere Ausrichtung
        font = PyQt6.QtGui.QFontDatabase.systemFont(PyQt6.QtGui.QFontDatabase.SystemFont.FixedFont)
        text_field.setFont(font)
        text_field.setPlainText(log_text)

        main_layout.addWidget(text_field)

        close_button = PyQt6.QtWidgets.QPushButton("Schließen")
        close_button.clicked.connect(self.accept)

        button_layout = PyQt6.QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)

        # Wichtig: Dialog-Instanz beim Schließen löschen
        self.setAttribute(PyQt6.QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
