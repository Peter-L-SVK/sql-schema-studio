# SQL Schema Studio <br>[![Tests](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/tests.yml/badge.svg)](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/tests.yml) [![Build RPM](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/build-rpm.yml/badge.svg)](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/build-rpm.yml) [![Build DEB](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/build-deb.yml/badge.svg)](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/build-deb.yml) [![PR Check](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/check-pr.yml/badge.svg)](https://github.com/Peter-L-SVK/sql-schema-studio/actions/workflows/check-pr.yml)

[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Top Language](https://img.shields.io/github/languages/top/Peter-L-SVK/sql-schema-studio)](https://github.com/Peter-L-SVK/sql-schema-studio)
[![GitHub release](https://img.shields.io/github/v/release/Peter-L-SVK/sql-schema-studio)](https://github.com/Peter-L-SVK/sql-schema-studio/releases/latest)
[![GitHub last commit](https://img.shields.io/github/last-commit/Peter-L-SVK/sql-schema-studio)](https://github.com/Peter-L-SVK/sql-schema-studio/commits/main)
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

### Editor
- **Multi-tab SQL editor** with Ctrl+T new tab, Ctrl+W close, drag to reorder
- **Autocomplete** with case-insensitive keyword matching and popover navigation
- **Syntax highlighting** via GtkSourceView 5 with multiple color schemes
- **Search & Replace** with case-sensitive toggle (Ctrl+F, Ctrl+H)
- **File operations** — open, save, and save as for SQL files (Ctrl+O/S/Shift+S)
- **Query execution** with formatted results, timing, and EXPLAIN ANALYZE support

### Schema Designer
- **Visual schema designer** with drag-and-drop tables, column editor, and FK relationships
- **Smart line routing** with obstacle avoidance and waypoints
- **Line jumps** (bridge arcs) for crossing lines
- **Bidirectional FK** with directional arrows and cardinality labels (1:N)
- **3 line styles** (straight, S-curve, orthogonal)
- **Color schemes** — 8 presets + custom color picker with GTK ColorDialog
- **Zoom & Pan** (Ctrl+Scroll, middle mouse drag, arrow keys)
- **Undo/Redo** (Ctrl+Z/Y) for all designer actions
- **SQL file import** — drag .sql files onto the designer to reverse-engineer schemas
- **Generate SQL** from designed schema

### Data Management
- **Connection manager** with saved profiles and system keyring password storage
- **SSH tunnel support** for remote PostgreSQL connections (password, key file, agent)
- **Database browser** with schema/table tree, live filtering, and double-click to query
- **Data export** — export query results to CSV and JSON
- **Data import** — import CSV and JSON files with preview dialog
- **Query history** with SQLite storage, search, and type categorization

### AI & Analytics
- **AI index advisor** — rule-based index recommendations for foreign keys and columns
- **Polars analytics engine** — column profiling, table comparison, correlation matrix
- **Hook system** with Python and Perl plugin support, execution, and JSON export
- **Built-in hooks**:
  - Auto-Vacuum Advisor with ML prediction
  - Schema Anomaly Detector (9 detection rules)
  - PostgreSQL Log Analyzer (3 reading methods: SQL, CSV, text)
  - Synthetic Data Generator with multi-CPU support
  - Keboola Normalizer with CSV validation and cloud upload
- **Multi-CPU worker pool** for parallel analytics processing

### UI/UX
- **Preferences dialog** with persistent editor settings (font, color scheme, tab width)
- **Window state persistence** — remembers size and pane positions across sessions
- Full menu bar with keyboard shortcuts, undo/redo, clipboard, SQL formatting
- Cross-desktop theming (Cinnamon, GNOME, MATE, XFCE, KDE Plasma)
- Clean shutdown with automatic disconnection

## Planned

### v1.0.0
- Migration generator with up/down SQL diffs
- FK Editor dialog (ON DELETE/ON UPDATE cascade rules)
- Export schema to GraphQL and pg_dump
- Graph visualization of table dependencies
- RPM/DEB packages in official repositories
- Flatpak / AppImage distribution
- PyPI package
- Complete test suite and performance benchmarking
- LaTeX user manual (PDF + EPUB)

### Future
- Visual query builder with drag-and-drop JOINs
- Multi-database support (MySQL/MariaDB, SQLite)
- Data editor with inline editing
- Dark mode / light mode toggle
- Query profiler (execution timeline)
- Git integration for schemas
- Cython optimization for critical paths
- SSH tunneling with jump hosts

## Requirements

- Linux or FreeBSD
- Windows 10/11 via WSL2
- Python 3.12 or later
- GTK 4 and GtkSourceView 5
- PostgreSQL 12 or later
- Perl 5.30 or later (optional, for Perl hooks)
- Developed on Fedora 43 Cinnamon and tested on Fedora 43 KDE Plasma 6


## Installation from Packages

### Fedora / RHEL (RPM)

```bash
# Install build dependencies
sudo dnf install rpm-build rpmdevtools rpmlint python3-devel vte291-gtk4

pip install polars

# Clone and build
git clone https://github.com/Peter-L-SVK/sql-schema-studio.git
cd sql-schema-studio

# Build RPM package
./scripts/packaging/build_rpm.sh

# Install
sudo dnf install ~/rpmbuild/RPMS/noarch/sql-schema-studio-*.rpm
```

### Debian / Ubuntu / Mint (DEB) / WSL2

```bash
# Install build dependencies
sudo apt install -y python3-psycopg2 python3-gi python3-gi-cairo \
  python3-sqlparse python3-keyring python3-numpy \
  python3-scikit-learn python3-matplotlib python3-cairo python3-paramiko \
  gir1.2-gtk-4.0 gir1.2-gtksource-5 libvte-2.91-gtk4-dev \
  python3-pipx

pip install polars  --break-system-packages

# Install dependencies with pipx
pipx install faker kbcstorage scikit-learn --include-deps

# Clone and build
git clone https://github.com/Peter-L-SVK/sql-schema-studio.git
cd sql-schema-studio

# Build DEB package
./scripts/packaging/build_deb.sh

# Install
sudo dpkg -i sql-schema-studio_*.deb
sudo apt --fix-broken install
```

### Run

```bash
sql-schema-studio
```

## Run from source

### Debian / Ubuntu / Mint / WSL2

```bash
sudo apt update
sudo apt install -y python3-psycopg2 python3-gi python3-gi-cairo \
  python3-sqlparse python3-keyring python3-numpy \
  python3-scikit-learn python3-matplotlib python3-cairo python3-paramiko \
  gir1.2-gtk-4.0 gir1.2-gtksource-5 libvte-2.91-gtk4-dev \
  pipx

pip install polars  --break-system-packages

# Install pipx if not already installed (it's in the apt command above)
# pipx ensures isolated Python package installations

# Install dependencies with pipx
pipx install faker kbcstorage scikit-learn --include-deps

# Clone and install from source
git clone https://github.com/Peter-L-SVK/sql-schema-studio.git
cd sql-schema-studio

# Run the application
python3 -m src.main
```

### Fedora / CentOS / RedHat

```bash
sudo dnf install python3-gobject gtk4 gtksourceview5 libadwaita cairo python3-cairo \
  python3-paramiko python3-faker python3-kbcstorage vte291-gtk4

git clone https://github.com/Peter-L-SVK/sql-schema-studio.git
cd sql-schema-studio
pip install --user -e .
python3 -m src.main
```

### Windows (WSL2)

```bash
# Install WSL2 (run this in Windows PowerShell as admin)
wsl --install
wsl --update

# Inside WSL2 terminal (Debian / Ubuntu):
sudo apt update && sudo apt upgrade -y

# Install required system dependencies
sudo apt install -y python3-psycopg2 python3-gi python3-gi-cairo \
  python3-sqlparse python3-keyring python3-numpy \
  python3-matplotlib python3-cairo python3-paramiko \
  gir1.2-gtk-4.0 gir1.2-gtksource-5 libvte-2.91-gtk4-dev \
  pipx postgresql postgresql-client 

pip install polars  --break-system-packages

# Install pipx if not already installed
# pipx ensures isolated Python package installations

# Install dependencies with pipx
pipx install faker kbcstorage scikit-learn --include-deps

# (Optional) Start local PostgreSQL
sudo service postgresql start

# Clone and install from source
git clone https://github.com/Peter-L-SVK/sql-schema-studio.git
cd sql-schema-studio

# Run the application
python3 -m src.main

# Note: GUI will work automatically through WSLg on Windows 11
# For Windows 10, you may need to set up an X server
```

## Development Installation

For development work with all dependencies:

```bash
# Install system dependencies as above

# Clone the repository
git clone https://github.com/Peter-L-SVK/sql-schema-studio.git
cd sql-schema-studio

# Install with development extras
pip install -e ".[dev]"

# Install optional development tools
pip install black flake8 mypy pytest pytest-cov

# Run tests
python3 -m pytest tests/ -v

# Check code style
python3 -m black src/ tests/
python3 -m flake8 src/ tests/
python3 -m mypy src/
```

## Dependency Breakdown

### Required System Packages (installed via apt/dnf)
These are essential for the application to run:
- **PostgreSQL client**: `python3-psycopg2` - Database connectivity
- **GTK4 GUI**: `python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-4.0`, `gir1.2-gtksource-5` - GUI framework
- **SQL parsing**: `python3-sqlparse` - SQL parsing and formatting
- **Data processing**: `python3-numpy`, `python3-pandas`, `python3-scikit-learn` - Analytics engine
- **Visualization**: `python3-matplotlib`, `python3-cairo` - Charts and graphs
- **SSH tunneling**: `python3-paramiko` - Secure remote connections
- **Terminal**: `gir1.2-vte-3.91` - Embedded terminal widget
- **Keyring**: `python3-keyring` - Secure password storage

### Optional Packages (install via pipx or apt)
These add extra features but aren't required:
- **Synthetic data**: `faker` - Generate test data (pipx install faker)
- **Keboola integration**: `kbcstorage` - Cloud data platform (pipx install kbcstorage)

## Installation Troubleshooting

### Common Issues

**1. "ModuleNotFoundError: No module named 'sklearn'"**
```bash
# Fix: Install scikit-learn
sudo apt install python3-scikit-learn  # Debian/Ubuntu
sudo dnf install python3-scikit-learn  # Fedora
```

**2. "ModuleNotFoundError: No module named 'faker'"**
```bash
# Fix: Install faker via pipx
pipx install faker
# Or via apt (if available)
sudo apt install python3-faker
```

**3. "ModuleNotFoundError: No module named 'kbcstorage'"**
```bash
# Fix: Install kbcstorage via pipx
pipx install kbcstorage
```

**4. GTK4 or GtkSourceView not found**
```bash
# Debian/Ubuntu
sudo apt install gir1.2-gtk-4.0 gir1.2-gtksource-5 libvte-2.91-gtk4-dev

# Fedora
sudo dnf install gtk4 gtksourceview5 vte291-gtk4
```

**5. WSL2 GUI not working**
```bash
# Ensure WSLg is enabled (Windows 11)
wsl --update

# For Windows 10, install an X server like VcXsrv
# and set DISPLAY environment variable
export DISPLAY=$(ip route list default | awk '{print $3}'):0
```

## Architecture

```
src/
├── main.py                     Entry point
├── app.py                      Gtk.Application lifecycle
├── actions.py                  Menu and toolbar handlers
├── config.py                   Centralized constants
├── core/                       Database connectivity, query execution, SQL parsing, SSH, worker pool
├── ui/                         GTK4 interface (window, browser, editor, designer)
│   ├── editor/                 Multi tabed editor with autocomplete
│   ├── dialogs/                Connection, about, preferences, column editor, hooks
│   ├── schema_designer/	    Grafical schema designer
│   └── window/                 Application window with it's tools
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
