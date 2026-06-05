# Contributing to SQL Schema Studio

Thank you for considering contributing. This document outlines the standards
and workflow used by the project.

## Code Style

SQL Schema Studio follows PEP 8 with these specifics:

**Line length:** 100 characters maximum.

**Quotes:** Double quotes for strings, single quotes where double would
require escaping.

**Docstrings:** Triple double quotes for all docstrings. First line is a
one-line summary, followed by a blank line, then details.

**Type hints:** Required on all public functions. Use Python 3.10+ union
syntax (`str | None`, not `Optional[str]`).

### Import Order

Standard library imports first, then third-party, then local. One blank
line between groups. Alphabetical within each group.

```python
import os
import sys

import psycopg

from src.core.db_connector import ConnectionProfile
from src.utils.gtk_helpers import run_async, set_margin
```

Parentheses for four or more imports from the same module.

### File Headers

All source files must include the project header:

```python
# ----------------------------------------------------------------------
# SQL Schema Studio - [Component Name] (GPLv3)
# Copyright (C) 2025-2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------
```

When you make significant changes to a file (50+ lines of meaningful code),
add your name to a Contributors line after the copyright:

```python
# Copyright (C) 2025-2026 Peter Leukanič
# Contributors: Your Name
```

Never remove existing names. Only add your own.

## Commit Messages

```
type(scope): brief description

Detailed explanation if needed. Reference issues with #number.
```

**Types:** feat, fix, docs, style, refactor, test, chore

**Example:**
```
feat(editor): add SQL formatting via Ctrl+Shift+F

Uses sqlparse to reformat the current query with consistent
capitalization and indentation. Closes #12.
```

## Branching Strategy

- **main** — stable, tested, production-ready
- **stage** — integration branch for incoming features
- **feat/*** — feature branches created from stage

### Workflow

1. Fork the repository and clone locally.
2. Checkout stage and pull latest changes.
3. Create a feature branch: `git checkout -b feat/your-feature`
4. Commit your changes following the commit message format.
5. Push and open a pull request targeting the `stage` branch.
6. After review, your changes will be merged into stage.
7. Periodically, stage is merged into main for releases.

Delete feature branches after they are merged.

## Testing

New features require tests. Bug fixes should include a test that
demonstrates the bug was present and is now fixed.

```bash
python3 -m pytest tests/ -v
```

Test files go in the `tests/` directory. Use pytest fixtures from
`conftest.py` for database connections.

## Code Quality Checks

Preconfigured in repo. For flake8 toml config:    
```sh 
pip install flake8-pyproject 
```

Run before submitting a pull request:

```bash
python3 -m black src/ tests/          # Formatting
python3 -m flake8 src/ tests/         # Linting
python3 -m mypy src/                  # Type checking
python3 -m pytest tests/ -v           # Tests
```

All checks must pass. The CI pipeline runs these automatically.

## Versioning

The project uses semantic versioning (MAJOR.MINOR.PATCH).

File headers use major.minor format and only need updating for minor or
major releases. Patch releases do not require header changes.

## Recognition

Contributors are recognized in:
- File headers for files they significantly modified
- The project README
- Release notes

If you have made a significant contribution, feel free to add yourself
to the relevant file headers and the README contributors section as
part of your pull request.
