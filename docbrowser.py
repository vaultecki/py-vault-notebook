import PyQt6.QtWidgets
import PyQt6.QtCore


class DocBrowserDialog(PyQt6.QtWidgets.QDialog):
    """
    Ein Dialog, der eine durchsuchbare Liste von Dateien anzeigt
    und die Auswahl des Benutzers zurückgibt.
    """

    def __init__(self, file_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Internes Dokument auswählen")
        self.setMinimumSize(400, 300)

        self.all_files = sorted(file_list)
        self.selected_file = None

        # --- UI-Elemente ---
        self.search_bar = PyQt6.QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Filter nach Dateinamen...")

        self.list_widget = PyQt6.QtWidgets.QListWidget()
        self.list_widget.addItems(self.all_files)

        self.insert_button = PyQt6.QtWidgets.QPushButton("Link einfügen")
        self.cancel_button = PyQt6.QtWidgets.QPushButton("Abbrechen")

        # --- Layout ---
        main_layout = PyQt6.QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.search_bar)
        main_layout.addWidget(self.list_widget)

        button_layout = PyQt6.QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.insert_button)
        main_layout.addLayout(button_layout)

        # --- Signale ---
        self.search_bar.textChanged.connect(self.filter_list)
        self.insert_button.clicked.connect(self.on_accept)
        self.cancel_button.clicked.connect(self.reject)
        self.list_widget.itemDoubleClicked.connect(self.on_accept)

    def filter_list(self, text):
        """ Filtert die Liste basierend auf der Sucheingabe. """
        self.list_widget.clear()
        search_text = text.lower()
        if not search_text:
            self.list_widget.addItems(self.all_files)
            return

        filtered_files = [f for f in self.all_files if search_text in f.lower()]
        self.list_widget.addItems(filtered_files)

    def on_accept(self):
        """ Setzt die ausgewählte Datei und schließt den Dialog. """
        current_item = self.list_widget.currentItem()
        if current_item:
            self.selected_file = current_item.text()
            self.accept()  # Schließt den Dialog mit "Accepted" Status
        else:
            # Akzeptieren Sie auch, wenn Text markiert ist (für Enter-Druck)
            if self.list_widget.count() > 0:
                self.selected_file = self.list_widget.item(0).text()
                self.accept()

    @staticmethod
    def get_selected_file(file_list, parent=None):
        """
        Öffnet den Dialog modal und gibt die ausgewählte Datei zurück
        oder None bei Abbruch.
        """
        dialog = DocBrowserDialog(file_list, parent)
        result = dialog.exec()  # .exec() ist modal (blockierend)

        if result == PyQt6.QtWidgets.QDialog.DialogCode.Accepted:
            return dialog.selected_file
        return None
