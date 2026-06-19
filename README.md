# SQL Schema Studio

[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Top Language](https://img.shields.io/github/languages/top/Peter-L-SVK/sql-schema-studio)](https://github.com/Peter-L-SVK/sql-schema-studio)
[![GitHub release](https://img.shields.io/github/v/release/Peter-L-SVK/sql-schema-studio)](https://github.com/Peter-L-SVK/sql-schema-studio/releases/latest)
[![GitHub last commit](https://img.shields.io/github/last-commit/Peter-L-SVK/sql-schema-studio)](https://github.com/Peter-L-SVK/sql-schema-studio/commits/main)

<!-- CI/CD Status Badges -->
[![Tests](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/tests.yml/badge.svg)](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/tests.yml)
[![Build RPM](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/build-rpm.yml/badge.svg)](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/build-rpm.yml)
[![Build DEB](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/build-deb.yml/badge.svg)](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/build-deb.yml)
[![PR Check](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/check-pr.yml/badge.svg)](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/check-pr.yml)

<a href="https://buymeacoffee.com/leukanic.peter"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" height="20px"></a>  

SQL Schema Studio is a native GTK4 PostgreSQL client built for Linux — not Electron, not a web app.
It runs lean on any Linux desktop, extends via Python or Perl hooks, and ships a visual schema designer
without a subscription fee or a JVM. Windows users can run it via WSL2 with full GUI support through WSLg.

If you live in a terminal but want a GUI when it earns it, this is for you.

**Alpha software — under active development.**

![Demo](scrshots/4.png)

## What It Does

Connect to PostgreSQL, browse schemas and tables, write and execute queries
with syntax highlighting, design schemas visually, and get AI-powered index
recommendations. Extend with Python and Perl hooks for custom automation.

## Current Features

- **Connection manager** with saved profiles and system keyring password storage
- **Database browser** with schema/table tree, live filtering, and double-click to query
- **SQL editor** with GtkSourceView syntax highlighting, line numbers, and F5 execution
- **Query execution** with formatted results, timing, and EXPLAIN ANALYZE support
- **File operations** — open, save, and save as for SQL files (Ctrl+O/S/Shift+S)
- **Data export** — export query results to CSV and JSON
- **Data import** — import CSV and JSON files with preview dialog
- **Visual schema designer** with drag-and-drop tables, column editor, and FK relationships
  with multiple line styles (straight, S-curve, orthogonal) and arrow heads
- **SQL file import** — drag .sql files onto the designer to reverse-engineer schemas
- **Query history** with SQLite storage, search, and type categorization
- **AI index advisor** — rule-based index recommendations for foreign keys and columns
- **Hook system** with Python and Perl plugin support, execution, and JSON export
- **Built-in hooks** — Auto-Vacuum Advisor with ML prediction, Schema Anomaly Detector with
  9 detection rules, PostgreSQL Log Analyzer with 3 reading methods
- **Preferences dialog** with persistent editor settings (font, color scheme, tab width)
- **Window state persistence** — remembers size and pane positions across sessions
- Full menu bar with keyboard shortcuts, undo/redo, clipboard, SQL formatting
- Cross-desktop theming (Cinnamon, GNOME, MATE, XFCE, KDE Plasma)
- Clean shutdown with automatic disconnection

## Planned

- Multi-tab SQL editor and results panel
- Migration generator with up/down SQL diffs
- Color schemes and bidirectional FK for schema designer
- Polars analytics engine and Kebola normalization hook
- RPM/DEB packaging and installation
- Browse data with inline editing
- Visual query builder with drag-and-drop JOINs
- SSH tunnel support for remote connections
- User manual and documentation

## Installation from Packages

### Fedora / RHEL (RPM)

```bash
sudo dnf install rpm-build rpmdevtools rpmlint python3-devel
git clone https://github.com/Peter-L-SVK/sql-schema-studio.git
cd sql-schema-studio
./scripts/packaging/build_rpm.sh
sudo dnf install ~/rpmbuild/RPMS/noarch/sql-schema-studio-*.rpm
```

### Debian / Ubuntu / Mint (DEB) / WSL2

```bash
sudo apt install dpkg-dev debhelper python3-dev
git clone https://github.com/Peter-L-SVK/sql-schema-studio.git
cd sql-schema-studio
./scripts/packaging/build_deb.sh
sudo dpkg -i sql-schema-studio_*.deb
sudo apt --fix-broken install
```

### Run

```bash
sql-schema-studio
```

**Note:** Currently the application can only be launched via terminal. Desktop launcher (.desktop file) is planned for v0.9.0.

## From Source

### Debian / Ubuntu / Mint / WSL2

```bash
sudo apt update
sudo apt install -y python3-psycopg python3-gi python3-sqlparse python3-keyring \
  python3-numpy python3-pandas python3-sklearn python3-matplotlib python3-cairo \
  python3-paramiko gir1.2-gtk-4.0 gir1.2-gtksource-5

git clone https://github.com/Peter-L-SVK/sql-schema-studio.git
cd sql-schema-studio
pip install --user -e .
sql-schema-studio
```

### Fedora / CentOS / RedHat

```bash
sudo dnf install python3-gobject gtk4 gtksourceview5 libadwaita cairo python3-cairo

git clone https://github.com/Peter-L-SVK/sql-schema-studio.git
cd sql-schema-studio
pip install --user -e .
sql-schema-studio
```

### Windows (WSL2)

```bash
wsl --install
wsl --update

# Inside WSL2 terminal (Debian / Ubuntu):
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-psycopg python3-gi python3-sqlparse python3-keyring \
  python3-numpy python3-pandas python3-sklearn python3-matplotlib python3-cairo \
  python3-paramiko gir1.2-gtk-4.0 gir1.2-gtksource-5 \
  postgresql postgresql-client

sudo service postgresql start

git clone https://github.com/Peter-L-SVK/sql-schema-studio.git
cd sql-schema-studio
pip install --user -e .
sql-schema-studio
```

## Development

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v
python3 -m black src/ tests/
python3 -m flake8 src/ tests/
python3 -m mypy src/
```

## System Requirements

**Debian / Ubuntu / Mint:**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
  gir1.2-gtksource-5 libgtk-4-1 libgtksourceview-5-0 \
  libcairo2-dev python3-cairo
```

**Fedora / CentOS / RedHat:**
```bash
sudo dnf install python3-gobject gtk4 gtksourceview5 libadwaita cairo python3-cairo
```

## Architecture

```
src/
├── main.py                     Entry point
├── app.py                      Gtk.Application lifecycle
├── actions.py                  Menu and toolbar handlers
├── config.py                   Centralized constants
├── core/                       Database connectivity, query execution, SQL parsing
├── ui/                         GTK4 interface (window, browser, editor, designer)
│   └── dialogs/                Connection, about, preferences, column editor, hooks
├── models/                     Table, column, and relationship data models
├── hooks/                      Plugin system with Python and Perl executors
│   ├── python/                 Python hook runtime
│   ├── perl/                   Perl hook runtime
│   ├── python_hooks/           Python hook implementations
│   └── perl_hooks/             Perl hook implementations
├── analytics/                  Index advisor and query analysis
├── utils/                      GTK4 helpers, logging, settings, signal handlers
└── resources/
    └── ui/
        ├── style.css           Application stylesheet
        └── icons/              Application icons
```

## Contributing

See [CONTRIBUTING](https://github.com/Peter-L-SVK/sql-schema-studio/blob/main/CONTRIBUTING.md) for details.  
Please open an issue or pull request for bug fixes, feature suggestions, or documentation improvements.
Also discussion on repo is allowed.

## License

GNU General Public License v3 or later. See [LICENSE](LICENSE).

---
