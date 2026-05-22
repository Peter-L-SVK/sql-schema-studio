# SQL Schema Studio

Intelligent PostgreSQL Management Platform. A GTK4 desktop application for
database administrators and developers who want a clean, fast, and extensible
SQL tool.

## What It Does

Connect to PostgreSQL, browse schemas and tables, write and execute queries
with syntax highlighting, and get formatted results. The plugin system lets
you extend it with Python and Perl hooks for custom automation, and the
built-in analytics engine can suggest indexes and detect query patterns.

## Current Features

- Connection manager with saved profiles and test-on-demand
- Database browser with schema/table tree and live filtering
- SQL editor with syntax highlighting, line numbers, and F5 execution
- Results viewer with formatted table output and timing
- Full menu bar with undo/redo, clipboard, SQL formatting, and EXPLAIN
- Modular architecture separating core, UI, models, hooks, and analytics
- Clean shutdown with automatic disconnection on window close

## Planned

- Visual schema designer with drag-and-drop table editing
- Migration generator with up/down SQL diffs
- AI index advisor using scikit-learn query pattern analysis
- Hook manager for enabling and configuring Python and Perl plugins
- Multiple result tabs and query history

## Requirements

- Python 3.12 or later
- GTK 4 and GtkSourceView 5
- PostgreSQL 12 or later
- Perl 5.30 or later (optional, for Perl hooks)

## Quick Start

```bash
git clone https://github.com/peter-leukanic/sql-schema-studio.git
cd sql-schema-studio
pip install -r requirements.txt
python3 -m src.main
```

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
├── main.py              Entry point
├── app.py               Gtk.Application lifecycle
├── actions.py            Menu and toolbar handlers
├── core/                 Database connectivity and query execution
├── ui/                   GTK4 interface components
│   └── dialogs/          Connection and about dialogs
├── models/               Table, column, and relationship data models
├── hooks/                Plugin system with Python and Perl executors
├── analytics/            Machine learning analytics pipeline
├── utils/                GTK4 helpers and signal handlers
└── resources/            CSS stylesheets
```

## License

GNU General Public License v3 or later. See [LICENSE](LICENSE).
