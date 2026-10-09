# SQL Schema Studio — Roadmap

## v0.8.0 — Hooks + Optimization (released)

### Hooks
- [x] Auto-Vacuum Advisor — reads pg_stat_user_tables, calculates bloat ratio
- [x] Schema Anomaly Detector — detects missing FKs, missing indexes, denormalization
- [x] PostgreSQL Log Analyzer (Perl) — parses PostgreSQL log files
- [x] JSON export for hook results

### Optimization
- [x] Big O: hash map O(1) for FK lookup in schema designer

### Infrastructure
- [x] Move requirements to pyproject.toml
- [x] RPM/DEB packaging scripts

---

## v0.9.0 — Schema Designer Pro + Multi-Tab Editor (released)

### Multi-Tab System
- [x] Tabbed SQL editor (Ctrl+T, Ctrl+W, drag tabs)
- [x] Unsaved changes indicator (•)
- [x] Restore open tabs on startup
- [x] Tabbed results panel

### Schema Designer
- [x] Color schemes — blue, green, orange, red, purple, gray
- [x] Zoom and pan for canvas
- [ ] Bidirectional FK with cascade rules (ON DELETE/ON UPDATE)
- [ ] FK Editor dialog (direction, rules)
- [ ] Directional arrows (↔, →, ←)

### AI/ML Extensions
- [x] Streaming/yield for large result sets
- [x] Polars replacing pandas
- [x] Keboola normalization hook
- [x] Prophet — database growth prediction
- [x] XGBoost — index impact prediction
- [ ] Lazy loading in browser

### Infrastructure
- [x] SSH tunnel support
- [x] Support for desktop launcher (.desktop file)

### Migrations (deferred to v0.9.9)
- [ ] Migration generator with up/down SQL diffs
- [ ] Schema comparison (live DB vs designer)

### Export/Import (deferred to v0.9.9)
- [ ] Export schema to GraphQL
- [ ] Export to SQL dump (pg_dump compatible)

---

## v0.9.5 — Service Pack 1 (released)

### Keboola Integration (New)
- [x] Client, profiles, engines (BigQuery, Snowflake)
- [x] Transformation pipeline (upload → transform → trigger → wait → download)
- [x] Editor bridge (SQL edited in main editor, `keboola://` URI)
- [x] Profile management (JSON + system keyring)
- [x] Pipeline cancellation with server-side job kill
- [x] Upload replaces existing table (no manual cleanup)
- [x] Downloaded CSV always gets `.csv` extension

### Schema Cache
- [x] In-memory cache with 5-minute TTL
- [x] DDL invalidation (CREATE/ALTER/DROP/TRUNCATE/RENAME)
- [x] Cache hit/miss logging

### Query History
- [x] Category filter (SELECT/INSERT/UPDATE/DELETE/DDL/Other)
- [x] Robust load for entries outside default window
- [x] Refresh Entry button
- [x] Clear History confirmation

### Editor & UI
- [x] Independent editor/terminal theme mode (Auto/Light/Dark)
- [x] Table preview without auto-execution (DBeaver-style)
- [x] Aligned results table columns
- [x] `format_data_type()` — shortened PostgreSQL type names
- [x] Log tab fix (application logger instead of root)

### Bug Fixes
- [x] 13 critical bug fixes (connection, hooks, query executor, settings, schema designer, editor, browser, keboola)

### Tests
- [x] 212 unit tests across 12 suites

---

## v0.9.9 — Service Pack 2 (planned)

### Schema Designer
- [ ] FK Editor dialog (direction, ON DELETE / ON UPDATE rules)
- [ ] Bidirectional FK arrows (↔, →, ←)
- [ ] Cascade rules editor

### Migration Tools
- [ ] Migration generator with up/down SQL diffs
- [ ] Schema comparison (live DB vs designer)
- [ ] Export schema to GraphQL
- [ ] Export to SQL dump (pg_dump compatible)

### Browser
- [ ] Lazy loading for large schemas (1000+ tables)

---

## v1.0.0 — Beta Release

### Stabilization
- [ ] Complete test suite (unit, integration, UI)
- [ ] Performance benchmarking
- [ ] Bug fixing (from community)
- [ ] Code freeze 2 weeks before release

### Schema Analysis
- [ ] Star/Snowflake schema detection and visualization
- [ ] Schema normalization suggestions
- [ ] Entity relationship diagram export

### Documentation
- [ ] LaTeX manual (PDF + EPUB)
- [ ] AI-powered documentation reader
- [ ] API documentation for hooks

### Distribution
- [ ] Official RPM and DEB packages (via Fedora COPR / Debian repos)
- [ ] Flatpak / AppImage
- [ ] PyPI package
- [ ] Windows installer (WSL2 helper)

---

## v1.1+ — Future Ideas

### Advanced Features
- [ ] Visual query builder (drag-and-drop JOINs, WHERE)
- [ ] Multi-database support (MySQL/MariaDB, SQLite)
- [ ] Data editor with inline editing
- [ ] Graph visualization of table dependencies
- [ ] Query profiler (execution timeline)

### AI/ML
- [ ] Cython optimization for critical paths
- [ ] Semantic SQL query analysis (sentence-transformers)
- [ ] Auto-complete SQL with ML model
- [ ] DuckDB transformation engine for Keboola

### Collaboration
- [ ] Git integration for schemas
- [ ] CI/CD pipeline for migrations
