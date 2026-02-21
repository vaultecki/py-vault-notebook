# VaultNotebook - Python Notebook Application

A local documentation wiki built with Python, PyQt6, AsciiDoc, and Git.

## Features

- 📝 **AsciiDoc Editor** - Write and view documents in AsciiDoc format
- 🔍 **Semantic Search** - Find documents using intelligent relevance ranking
- 🔄 **Git Integration** - Automatic version control with background sync
- 🔗 **Internal Links** - Easy linking between documents
- 📊 **Export to PDF** - Export pages as PDF documents
- 📂 **Multi-Project Support** - Manage multiple notebook projects
- 🌐 **Web Preview** - View formatted documents in integrated browser

## Requirements

See `requirements.txt`:
```
asciidoc~=10.2.1
GitPython~=3.1.43
PyQt6~=6.8.0
PyQt6-WebEngine~=6.8.0
jaro-winkler~=2.0.3
```

## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

## Configuration

Configuration is stored in:
- **Linux/macOS**: `~/.config/ThaNote/config.json`
- **Windows**: `%LOCALAPPDATA%\ThaNote\config.json`

### Config Structure

```json
{
  "projects": {
    "project_name": {
      "path": "/path/to/project",
      "create_date": 1234567890.0,
      "last_ascii_file": "index.asciidoc",
      "import_dir": "/path/to/import"
    }
  },
  "last_project": "project_name",
  "index_file": "index.asciidoc",
  "geometry": [300, 250, 900, 600],
  "edit_window_geometry": [300, 300, 600, 600],
  "export_dir": "/path/to/exports"
}
```

## Usage

### Creating a Project

1. Click **"Add/ New Project"**
2. Select a directory
3. An `index.asciidoc` file will be created automatically

### Editing Documents

1. Navigate to a document
2. Click **"Edit Page"**
3. Make changes in the editor
4. Press **Ctrl+S** or click **"Speichern"** to save

### Searching

- **Local Search**: Type in search box to search current page
- **Global Search**: Click 🔎 to search across all documents

### Linking Documents

1. In the editor, click **"Show Docs"**
2. Select a document from the list
3. A relative link will be inserted: `link:path/to/doc.adoc[]`

### Uploading Files

1. Click **"Upload File"** in the editor
2. Select a file (images, PDFs, etc.)
3. Choose where to save it in your project
4. File is automatically added to Git

## Keyboard Shortcuts

- **Ctrl+S** - Save current document
- **ESC** - Close editor window
- **Return** - Accept dialog / Execute search

## Architecture

### Key Components

- **main.py** - Main application window and project management
- **editpage.py** - Document editor with syntax checking
- **notegit.py** - Git wrapper with threaded operations
- **notehelper.py** - AsciiDoc conversion and search functionality
- **commitbrowser.py** - Git commit history viewer
- **docbrowser.py** - Document selection dialog

### Design Patterns

- **Signal/Slot Pattern** - PyQt signals for communication between components
- **Worker Thread Pattern** - Git operations run in background thread
- **Caching** - Search index caches file contents for performance
- **Safe Cleanup** - Proper resource management on application exit

## Advanced Features

### Semantic Search

The search algorithm ranks results based on:
1. Filename matches (highest weight)
2. Heading matches (weighted by heading level)
3. Emphasized text matches
4. Link text matches
5. Word boundary matches
6. Keyword frequency

### Git Integration

- Automatic commits on save
- Background push/pull operations
- Commit history browser
- Dirty repository detection

### Security Features

- Path traversal prevention
- File access restricted to project directory
- External URL confirmation dialogs

## Troubleshooting

### Git Issues

If you see git-related errors:
1. Check that Git is installed: `git --version`
2. Ensure project directory has write permissions
3. Check `.gitignore` configuration

### Encoding Issues

If you see garbled characters:
1. Ensure files are saved as UTF-8
2. Check your system locale settings
3. Try reopening the file

### Performance Issues

If search is slow:
1. Large files (>300KB) are skipped
2. Cache is automatically cleared after 5 minutes
3. Consider splitting large documents

## Development

### Running Tests

```bash
python -m pytest tests/
```

### Code Style

Follow PEP 8 guidelines. Use type hints where appropriate.

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Future Enhancements

- [ ] Full-text search indexing
- [ ] Markdown support
- [ ] Mobile companion app
- [ ] Easy image insert
- [ ] show git merge error
- [ ] let user change git address and branch
- [ ] provide app as appimage, exe, ...

## License

- Copyright [2025] [ecki]
- SPDX-License-Identifier: Apache-2.0


## Credits

Built with:
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- [AsciiDoc](https://asciidoc.org/)
- [GitPython](https://gitpython.readthedocs.io/)

## Support

For issues or questions:
- Open an issue on GitHub
- Check existing documentation
- Review the code comments

---

**Version**: 2.0  
**Last Updated**: 2025-01-18
