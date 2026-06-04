# SQL Schema Studio — Roadmap

## v0.8.0 — Hooks + Optimization + AI/ML

### Hooks
- [ ] Auto-Vacuum Advisor — reads pg_stat_user_tables, calculates bloat ratio
- [ ] Schema Anomaly Detector — detects missing FKs, missing indexes, denormalization
- [ ] PostgreSQL Log Analyzer (Perl) — parses PostgreSQL log files
- [ ] Kebola normalization hook — detects denormalized schemas, suggests fixes

### Optimization
- [x] Big O: hash map O(1) for FK lookup in schema designer
- [ ] Streaming/yield for large result sets (execute_stream)
- [ ] Lazy loading in browser (only expanded nodes)

### AI/ML
- [ ] Polars replacing pandas for analytics
- [ ] Query pattern clustering (scikit-learn KMeans + Polars)
- [ ] Index impact prediction (XGBoost/RandomForest)
- [ ] Workload classification (OLTP/OLAP/Mixed)

### Infrastructure
- [ ] Move requirements to pyproject.toml
- [ ] RPM/DEB packaging scripts
- [ ] Install script for Fedora/Debian

---

## v0.9.0 — Schema Designer Pro + Migrations

### Multi-Tab Editor
- [ ] Tabbed SQL editor (multiple .sql files open at once)
- [ ] Ctrl+T new tab, Ctrl+W close tab
- [ ] Unsaved changes indicator (•)
- [ ] Drag tabs to reorder
- [ ] Tab context menu (close, close others, close all)
- [ ] Restore open tabs on startup (session persistence)

### Schema Designer
- [ ] Color schemes — blue, green, orange, red, purple, gray
- [ ] Bidirectional FK with cascade rules (ON DELETE/ON UPDATE)
- [ ] FK Editor dialog (direction, rules)
- [ ] Directional arrows (↔, →, ←)
- [ ] Zoom and pan for canvas

### Migrations
- [ ] Migration generator with up/down SQL diffs
- [ ] Schema comparison (live DB vs designer)
- [ ] Migration versioning

### Export/Import
- [ ] Export schema to GraphQL
- [ ] Export to SQL dump (pg_dump compatible)
- [ ] Import from pg_dump

### Graph Analysis
- [ ] Graph visualization of table dependencies
- [ ] Force-directed/hierarchical/radial layout
- [ ] Nodes as tables, edges as FK
- [ ] Node size by row/column count

### AI/ML Extensions
- [ ] Prophet — database growth prediction (capacity planning)
- [ ] XGBoost — more accurate index impact prediction
- [ ] Anomaly detection — slow query detection vs history

---

## v1.0.0 — Beta Release

### Stabilization
- [ ] Complete test suite (unit, integration, UI)
- [ ] Performance benchmarking
- [ ] Bug fixing (from community)
- [ ] Code freeze 2 weeks before release

### Documentation
- [ ] LaTeX manual (PDF + EPUB)
- [ ] AI-powered documentation reader
- [ ] Tutorial videos / screencasts
- [ ] API documentation for hooks

### Distribution
- [ ] Official RPM and DEB packages
- [ ] Flatpak / AppImage
- [ ] PyPI package
- [ ] Windows installer (WSL2 helper)

### Community
- [ ]  Discord server
- [ ] Plugin marketplace (GitHub topics)
- [ ] Contributing guide v1.0

---

## v1.1+ — Future Ideas

### Advanced Features
- [ ] Visual query builder (drag-and-drop JOINs, WHERE)
- [ ] Multi-database support (MySQL/MariaDB, SQLite)
- [ ] Data editor with inline editing
- [ ] SSH tunneling for remote connections
- [ ] Dark mode / light mode toggle
- [ ] Tabs for multiple open SQL files
- [ ] Query profiler (execution timeline)

### AI/ML
- [ ] Cython optimization for critical paths
- [ ] Semantic SQL query analysis (sentence-transformers)
- [ ] Auto-complete SQL with ML model
- [ ] Intelligent SQL formatting

### Collaboration
- [ ] Multi-user mode (shared connections)
- [ ] Git integration for schemas
- [ ] CI/CD pipeline for migrations
- [ ] Cloud sync (GitHub Gist, Pastebin)
