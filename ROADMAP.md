# SQL Schema Studio — Roadmap

## v0.8.0 — Hooks + Optimization

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

### Deferred to v0.9.0
- Streaming/yield, lazy loading, Polars, Kebola hook

---

## v0.9.0 — Schema Designer Pro + Multi-Tab Editor

### Multi-Tab System
- [x] Tabbed SQL editor (Ctrl+T, Ctrl+W, drag tabs)
- [ ] Unsaved changes indicator (•)
- [ ] Restore open tabs on startup
- [ ] Tabbed results panel

### Schema Designer
- [x] Color schemes — blue, green, orange, red, purple, gray
- [x] Bidirectional FK with cascade rules (ON DELETE/ON UPDATE)
- [ ] FK Editor dialog (direction, rules)
- [ ] Directional arrows (↔, →, ←)
- [x] Zoom and pan for canvas

### Export/Import
- [ ] Export schema to GraphQL
- [ ] Export to SQL dump (pg_dump compatible)

### AI/ML Extensions
- [x] Streaming/yield for large result sets
- [ ] Lazy loading in browser
- [x] Polars replacing pandas
- [x] Keboola normalization hook
- [x] Prophet — database growth prediction
- [x] XGBoost — index impact prediction

### Infrastructure
- [x] SSH tunnel support

### Deferred to v1.0.0
- [ ] Desktop launcher (.desktop file)

#### Migrations
- [ ] Migration generator with up/down SQL diffs
- [ ] Schema comparison (live DB vs designer)

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
- [ ] Official RPM and DEB packages
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
- [ ] Dark mode / light mode toggle
- [ ] Query profiler (execution timeline)

### AI/ML
- [ ] Cython optimization for critical paths
- [ ] Semantic SQL query analysis (sentence-transformers)
- [ ] Auto-complete SQL with ML model

### Collaboration
- [ ] Git integration for schemas
- [ ] CI/CD pipeline for migrations
