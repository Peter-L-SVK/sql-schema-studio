# SQL Schema Studio

[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Top Language](https://img.shields.io/github/languages/top/Peter-L-SVK/sql-schema-studio)](https://github.com/Peter-L-SVK/sql-schema-studio)
[![GitHub release](https://img.shields.io/github/v/release/Peter-L-SVK/sql-schema-studio)](https://github.com/Peter-L-SVK/sql-schema-studio/releases/latest)
[![GitHub last commit](https://img.shields.io/github/last-commit/Peter-L-SVK/sql-schema-studio)](https://github.com/Peter-L-SVK/sql-schema-studio/commits/main)
<a href="https://buymeacoffee.com/leukanic.peter"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" height="20px"></a>

Intelligent PostgreSQL Management Platform. A GTK4 desktop application for
database administrators and developers who want a clean, fast, and extensible
SQL tool.

**Alpha software — under active development.**

## What It Does

Connect to PostgreSQL, browse schemas and tables, write and execute queries
with syntax highlighting, design schemas visually, and get AI-powered index
recommendations. Extend with Python and Perl hooks for custom automation.

## Current Features

- Connection manager with saved profiles, test-on-demand, and system keyring password storage
- Database browser with schema/table tree and live filtering
- SQL editor with syntax highlighting, line numbers, and F5 execution
- Results viewer with formatted table output and timing
- **Visual schema designer** with drag-and-drop tables, column editor, and FK relationships
- **SQL file import** — drag .sql files onto the designer to reverse-engineer schemas
- **Preferences dialog** with persistent editor settings (font, color scheme, tab width)
- **Window state persistence** — remembers size, pane positions across sessions
- Full menu bar with undo/redo, clipboard, SQL formatting, and EXPLAIN
- Modular architecture separating core, UI, models, hooks, and analytics
- Clean shutdown with automatic disconnection on window close
- Cross-desktop theming (Cinnamon, GNOME, MATE, XFCE)

## Planned

- Migration generator with up/down SQL diffs
- AI index advisor using scikit-learn query pattern analysis
- Hook manager for enabling and configuring Python and Perl plugins
- Multiple result tabs and query history
- Multi-CPU analytics worker pool for large datasets

## Requirements

- Linux or FreeBSD
- Python 3.12 or later
- GTK 4 and GtkSourceView 5
- PostgreSQL 12 or later
- Perl 5.30 or later (optional, for Perl hooks)

## System Requirements

The Python packages above require these system libraries:

**Debian / Ubuntu:**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
  gir1.2-gtksource-5.0 gir1.2-adw-1.0 libgtk-4-1 libgtksourceview-5-0
```

**Fedora:**
```bash
sudo dnf install python3-gobject gtk4 gtksourceview5 libadwaita
```

## Quick Start

```bash
git clone https://github.com/peter-leukanic/sql-schema-studio.git
cd sql-schema-studio
pip install -r requirements.txt
python3 -m src.main
```

## Contributing

Contributions are welcome!  
See [CONTRIBUTING](https://github.com/Peter-L-SVK/sql-schema-studio/blob/main/CONTRIBUTING.md) file for details.  

For contact please see my email in profile info or use GitHub's built-in communication tools.

Please open an issue or pull request for any:  

- Bug fixes
- Feature suggestions
- Documentation improvements

## Development

```bash
pip install -r requirements.txt
pip install pytest black flake8 mypy

python3 -m pytest tests/ -v
python3 -m black src/ tests/
python3 -m flake8 src/ tests/
python3 -m mypy src/
```

## Architecture

```
src/
├── main.py              Entry point — signal handlers, app launch
├── app.py               Gtk.Application subclass — lifecycle management
├── actions.py            All menu and toolbar action handlers
├── config.py             Centralized constants (defaults, limits, schemas)
├── core/
│   ├── db_connector.py   Connection profiles, keyring passwords, query execution
│   ├── query_executor.py Async query runner with timeout and cancellation
│   ├── schema_manager.py Schema parsing and generation (planned)
│   └── migration.py      Diff and migration generator (planned)
├── ui/
│   ├── window.py         Main application window — layout assembly
│   ├── browser.py        Database object tree with filtering
│   ├── editor.py         SQL editor with GtkSourceView syntax highlighting
│   ├── results.py        Query results panel with formatted table output
│   ├── schema_designer.py Visual schema designer with drag-drop and FK lines
│   ├── toolbar.py        Main toolbar — connect, run, stop, tools
│   ├── menubar.py        Traditional menu bar (File, Edit, View, Query, Tools, Help)
│   ├── statusbar.py      Bottom status bar — connection info, row counts, timing
│   └── dialogs/
│       ├── connection.py Connection dialog with test and password visibility toggle
│       ├── about.py      About dialog with system information
│       ├── preferences.py Editor settings with persistent JSON storage
│       └── column_editor.py Table column editor with type selection and PK toggles
├── models/
│   ├── table.py          Table model with SQL generation
│   ├── column.py         Column model with constraints and type handling
│   └── relationship.py   Foreign key relationship model
├── hooks/
│   ├── base_plugin.py    Abstract base classes for hooks and plugins
│   ├── registry.py       Plugin discovery and registration
│   ├── sandbox.py        Secure execution environment with resource limits
│   ├── bridge.py         Python ↔ Perl data marshaling
│   ├── python/
│   │   └── executor.py   Python hook runtime
│   └── perl/
│       └── executor.py   Perl5 hook runtime via subprocess
├── analytics/
│   ├── index_advisor.py  ML-based index recommendations (scikit-learn)
│   ├── query_analyzer.py Query pattern analysis (planned)
│   ├── pipeline.py       Data preprocessing pipelines (planned)
│   └── visualizations/   Matplotlib and Plotly backends (planned)
├── utils/
│   ├── gtk_helpers.py    GTK4 margin, layout, and run_async utilities
│   ├── logging.py        Centralized logger factory and configuration
│   ├── settings.py       Persistent JSON settings manager
│   └── signal_handlers.py SIGINT handler for graceful Ctrl-C exit
└── resources/
    └── ui/
        └── style.css     Cinnamon-inspired cross-DE stylesheet
```

## License

GNU General Public License v3 or later. See [LICENSE](LICENSE).  

---
