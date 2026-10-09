# SQL Schema Studio — Hook Development Guide

This guide covers the creation, licensing, and distribution of hooks for
SQL Schema Studio. Hooks extend the application with custom analysis,
automation, and integrations — from simple log parsers to full cloud
pipelines.

Hooks are written in **Python 3.12+** or **Perl 5.30+** and are loaded at
runtime by the plugin registry. They run inside a sandboxed executor with
memory and time limits, and are triggered by well-defined events.

## Table of Contents

1. [What Are Hooks?](#what-are-hooks)
2. [Hook Triggers](#hook-triggers)
3. [Hook Lifecycle](#hook-lifecycle)
4. [Writing a Python Hook](#writing-a-python-hook)
5. [Writing a Perl Hook](#writing-a-perl-hook)
6. [HookContext Reference](#hookcontext-reference)
7. [Sandbox Limits](#sandbox-limits)
8. [Licensing](#licensing)
9. [Distribution](#distribution)
10. [Testing](#testing)
11. [Common Pitfalls](#common-pitfalls)
12. [Complete Examples](#complete-examples)

---

## What Are Hooks?

Hooks are small pluggable modules that extend SQL Schema Studio's
functionality without modifying the core codebase. They can:

- **Analyze** database state (bloat, indexes, anomalies)
- **React** to events (query executed, schema changed, connection opened)
- **Transform** data (CSV validation, normalization, forecasting)
- **Integrate** with external systems (Keboola, logging, alerts)
- **Schedule** recurring tasks (vacuum advisor, log rotation)

Hooks are **isolated** — a failing hook cannot crash the application.
They are **sandboxed** — each hook has memory and CPU limits. They are
**independent** — you can enable, disable, or replace any hook without
touching the rest of the system.

### Built-in Hooks

SQL Schema Studio ships with these hooks out of the box:

| Hook | Language | Trigger | Purpose |
|------|----------|---------|---------|
| **Auto-Vacuum Advisor** | Python | `scheduled.interval` | Table bloat analysis + ML prediction |
| **Schema Anomaly Detector** | Python | `schema.changed` | 9 schema quality rules |
| **Synthetic Data Generator** | Python | `scheduled.interval` | Faker-based test data |
| **Forecasting** | Python | `query.executed` | Trend, moving average, anomalies |
| **Keboola Normalizer** | Python | `schema.changed`, `scheduled.interval` | Cloud CSV pipeline |
| **PostgreSQL Log Analyzer** | Perl | `scheduled.interval` | Log file analysis |

---

## Hook Triggers

Every hook declares which **triggers** it responds to. The plugin registry
routes matching events to matching hooks.

| Trigger | When It Fires | Typical Use |
|---------|---------------|-------------|
| `query.executed` | After a user runs a query | Logging, forecasting, alerting |
| `schema.changed` | After a DDL statement succeeds | Anomaly detection, index advisor |
| `connection.opened` | After a successful DB connection | Warm-up, schema sync |
| `connection.closed` | Before disconnecting | Cleanup, report generation |
| `migration.applied` | After a migration runs | Validation, drift detection |
| `performance.threshold` | When a query exceeds a configured duration | Alerting, profiling |
| `scheduled.interval` | On a timer (hook-defined interval) | Periodic analysis, cleanup |
| `application.startup` | Once, on app launch | Registration, sync |
| `application.shutdown` | Once, before app exit | Cleanup, flush |

A hook can register for **multiple triggers**:

```python
def get_metadata(self):
    return {
        "triggers": [
            HookTrigger.SCHEMA_CHANGED.value,
            HookTrigger.SCHEDULED_INTERVAL.value,
        ],
    }
```

---

## Hook Lifecycle

1. **Discovery** — `PluginRegistry.discover_plugins()` scans the hooks
   directory and imports every `*.py` file (Python) and registers every
   `*.pm` file (Perl).
2. **Instantiation** — the `Plugin` class is instantiated and
   `get_metadata()` is called to read the hook name and triggers.
3. **Registration** — the registry adds the hook to its trigger lists.
4. **Execution** — when a trigger fires, `execute(context)` is awaited
   inside the sandbox.
5. **Cleanup** — the sandbox enforces memory and time limits; on violation,
   the hook is aborted and an error is logged.

---

## Writing a Python Hook

### Minimum Viable Hook

Create a file at `src/hooks/python_hooks/my_hook.py`:

```python
from src.hooks.base_plugin import BaseHook, HookContext, HookTrigger


class Plugin(BaseHook):
    def get_metadata(self):
        return {
            "name": "My Hook",
            "version": "1.0.0",
            "author": "Your Name",
            "description": "Does something useful.",
            "triggers": [HookTrigger.QUERY_EXECUTED.value],
        }

    async def execute(self, context: HookContext) -> dict:
        # Hook logic goes here
        query = context.data.get("query", "")
        return {"status": "ok", "length": len(query)}
```

**Requirements:**
- The class **must** be named `Plugin`.
- It **must** subclass `BaseHook`.
- It **must** implement `get_metadata()` and `execute()`.

### Synchronous Hooks

For long-running analysis, implement `execute_sync()` instead. The
runner will call it from a worker thread:

```python
class Plugin(BaseHook):
    def execute_sync(self, conn_string: str) -> dict:
        import psycopg
        with psycopg.connect(conn_string) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM pg_stat_user_tables")
            return {"status": "ok", "tables": cur.fetchone()[0]}
```

The **`async execute()`** method takes precedence if both are defined.

### Using Connection Strings

The hook manager injects a live connection string into `context.data`:

```python
async def execute(self, context: HookContext) -> dict:
    conn_string = context.data.get("conn_string", "")
    if not conn_string:
        return {"error": "No active connection"}
    # ...
```

---

## Writing a Perl Hook

### Minimum Viable Perl Hook

Create a file at `src/hooks/perl_hooks/my_hook.pm`:

```perl
package my_hook;
use strict;
use warnings;
use JSON;

sub new {
    my $class = shift;
    return bless {}, $class;
}

sub get_metadata {
    return {
        name        => 'My Perl Hook',
        version     => '1.0.0',
        author      => 'Your Name',
        description => 'Does something useful.',
        triggers    => ['scheduled.interval'],
    };
}

sub execute {
    my ($self, $context) = @_;

    # $context is a decoded JSON hashref
    my $conn_string = $context->{data}{conn_string} || '';

    # ... hook logic ...

    return {
        status  => 'ok',
        message => 'Perl hook ran successfully',
    };
}

1;
```

**Requirements:**
- The package name **must** match the filename (`my_hook.pm` → `package my_hook`).
- It **must** implement `new`, `get_metadata()`, and `execute()`.
- It **must** end with `1;` (Perl module convention).

### JSON Bridge

The Perl executor serialises `HookContext` to JSON, pipes it to the
Perl script via stdin, and parses the JSON result from stdout. Any
Python object that is not JSON-serialisable is stringified by
`DataBridge.marshal_context()` before being sent.

- **Sent to Perl**: `context` as a JSON hashref on stdin.
- **Received from Perl**: the hook's return value as JSON on stdout.
- **Errors**: if the Perl script writes to stderr, the hook fails and the
  stderr content is surfaced as the error message.

### Example: PostgreSQL Log Analyzer

See `src/hooks/perl_hooks/log_parser.pm` for a full example that reads
PostgreSQL CSV logs, categorises errors, and returns recommendations.

---

## HookContext Reference

The `HookContext` dataclass is passed to every `execute()` call:

```python
@dataclass
class HookContext:
    trigger: HookTrigger
    database: str
    connection_pool: Any
    data: Dict[str, Any] = field(default_factory=dict)
    logger: Any = None
```

| Field | Type | Description |
|-------|------|-------------|
| `trigger` | `HookTrigger` | The event that fired this hook |
| `database` | `str` | Active database name |
| `connection_pool` | `Any` | Reserved for future use (usually `None`) |
| `data` | `dict` | Hook-specific payload |
| `logger` | `Any` | Optional logger injected by the runner |

### Standard `data` Keys

Hooks read from `context.data` using standard keys injected by the
runner. The available keys depend on the trigger:

| Trigger | Available Keys |
|---------|----------------|
| `query.executed` | `query`, `row_count`, `elapsed`, `success`, `conn_string` |
| `schema.changed` | `conn_string`, `statement`, `tables_affected` |
| `connection.opened` | `conn_string`, `profile_name` |
| `scheduled.interval` | `conn_string` |
| `application.startup` | `conn_string`, `profile_name` |

**Note:** `conn_string` is only present when a database connection is
active. Hooks should always check:

```python
conn_string = context.data.get("conn_string")
if not conn_string:
    return {"error": "No active connection"}
```

---

## Sandbox Limits

Every hook runs inside a `SandboxedExecutor` with these limits (see
`src/config.py`):

| Limit | Default | Config Key |
|-------|---------|------------|
| Memory | 512 MB | `HOOK_MEMORY_LIMIT_MB` |
| Execution time | 30 s | `HOOK_TIME_LIMIT_SECONDS` |

Hooks that exceed these limits are **aborted** and return an error to
the caller. They do not crash the application.

### What Hooks Cannot Do

The sandbox **does not** provide:
- Direct filesystem access outside the hook's config directory
- Network access without an explicit `requests` / `paramiko` import
- Subprocess spawning (except through the Perl executor's own path)
- Importing arbitrary system modules

Hooks that need network access (e.g. Keboola) use the standard library
`requests` and the hook's own API token from the system keyring.

### What Hooks Can Do

- Read from and write to the active database via `conn_string`
- Read configuration from `~/.config/sql-schema-studio/`
- Use any installed Python package (polars, scikit-learn, faker, ...)
- Log via `context.logger` or the standard `logging` module
- Return structured JSON results for display in the Hook Manager

---

## Licensing

Hooks that ship **with SQL Schema Studio** must be GPLv3+ to match the
application's license.

Hooks that you distribute **separately** may use any GPLv3-compatible
license (MIT, Apache 2.0, BSD-3-Clause).

### Recommended License Headers

**GPLv3+** (required for bundled hooks):

```python
# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - My Hook (GPLv3)
# Copyright (C) 2026 Your Name
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------
```

**Apache 2.0** (permissive, patent protection — for third-party hooks):

```python
# ----------------------------------------------------------------------
# My Hook
# Copyright (C) 2026 Your Name
# License: Apache 2.0 <https://www.apache.org/licenses/LICENSE-2.0.txt>
# ----------------------------------------------------------------------
```

**MIT** (simple permissive):

```python
# ----------------------------------------------------------------------
# My Hook
# Copyright (C) 2026 Your Name
# License: MIT <https://opensource.org/licenses/MIT>
# ----------------------------------------------------------------------
```

### License Compatibility

| Your Hook's License | Bundled with App? | Distributed Separately? |
|---------------------|-------------------|--------------------------|
| GPLv3+              | ✅ Yes            | ✅ Yes                   |
| MIT                 | ❌ No             | ✅ Yes                   |
| Apache 2.0          | ❌ No             | ✅ Yes                   |
| BSD-3-Clause        | ❌ No             | ✅ Yes                   |
| Proprietary         | ❌ No             | ⚠️ Only via private channels |

**Why?** SQL Schema Studio is GPLv3+. Bundling a non-GPLv3 hook would
require a license exception, which we don't grant for the official repo.
Separate distribution is fine — the user installs your hook themselves.

---

## Distribution

### For Built-in Hooks

Place your hook at `src/hooks/python_hooks/my_hook.py` (Python) or
`src/hooks/perl_hooks/my_hook.pm` (Perl) and submit a pull request.

### For Third-Party Hooks

Create a separate repository with this structure:

```
my-awesome-hook/
├── README.md
├── LICENSE
├── pyproject.toml          # for Python hooks
├── install.sh              # optional helper
├── my_hook.py              # the hook file
└── test_hook.py            # tests
```

**Installation instructions** for your users:

```bash
git clone https://github.com/you/my-awesome-hook.git
cd my-awesome-hook
./install.sh
```

### Example Install Script

```bash
#!/usr/bin/env sh
set -e

HOOK_NAME="my_hook"
HOOK_DIR="$HOME/.config/sql-schema-studio/hooks"

mkdir -p "$HOOK_DIR"
cp "$HOOK_NAME.py" "$HOOK_DIR/"

echo "✓ Hook $HOOK_NAME installed to $HOOK_DIR"
echo "  Restart SQL Schema Studio to activate it."
```

### README Template for Third-Party Hooks

```markdown
# My Awesome Hook for SQL Schema Studio

## Description
[What your hook does and what problem it solves]

## Installation
1. `git clone https://github.com/you/my-awesome-hook.git`
2. `cd my-awesome-hook && ./install.sh`
3. Restart SQL Schema Studio

## Triggers
- `schema.changed` — runs after every DDL statement

## Configuration
[Any user-editable config, e.g. JSON file in ~/.config/]

## License
[Your license], see LICENSE file.
```

---

## Testing

### Manual Testing

Run the hook from the command line by constructing a fake context:

```python
# test_my_hook.py
import asyncio
from src.hooks.base_plugin import HookContext, HookTrigger
from src.hooks.python_hooks.my_hook import Plugin

async def main():
    hook = Plugin()
    ctx = HookContext(
        trigger=HookTrigger.QUERY_EXECUTED,
        database="test_db",
        connection_pool=None,
        data={"query": "SELECT 1", "row_count": 1, "elapsed": 0.001},
    )
    result = await hook.execute(ctx)
    print(result)

asyncio.run(main())
```

### Unit Testing

Add a file at `tests/test_my_hook.py`:

```python
import pytest
from src.hooks.base_plugin import HookContext, HookTrigger
from src.hooks.python_hooks.my_hook import Plugin


@pytest.mark.asyncio
async def test_my_hook_returns_ok():
    hook = Plugin()
    ctx = HookContext(
        trigger=HookTrigger.QUERY_EXECUTED,
        database="test_db",
        connection_pool=None,
        data={"query": "SELECT 1"},
    )
    result = await hook.execute(ctx)
    assert result["status"] == "ok"


def test_my_hook_metadata():
    hook = Plugin()
    meta = hook.get_metadata()
    assert meta["name"] == "My Hook"
    assert "query.executed" in meta["triggers"]
```

Run with:

```bash
python3 -m pytest tests/test_my_hook.py -v
```

### Debug Logging

Use the application's logger to add debug output:

```python
from src.utils.logging import get_logger
logger = get_logger(__name__)

async def execute(self, context):
    logger.debug(f"Hook received context: {context.data}")
    ...
```

Logs appear in the **Log tab** of the results panel when the hook runs
inside the application.

---

## Common Pitfalls

| ❌ Don't | ✅ Do |
|---------|-------|
| Return non-JSON-serialisable values | Return `dict`, `list`, `str`, `int`, `float`, `bool`, `None` |
| Assume `conn_string` is always present | Check with `.get()` and return an error if missing |
| Use `print()` for output | Use `logger.info()` / `logger.debug()` |
| Block the event loop with `time.sleep()` | Use `asyncio.sleep()` in async hooks |
| Catch-all `except Exception: pass` | Log the exception, then return an error dict |
| Write to files outside the config dir | Return data and let the caller decide where to write |
| Hardcode API tokens | Store them in the system keyring |
| Import `os.system` / `subprocess.call` | Use `subprocess.Popen` with explicit args, or skip |

### Anti-Patterns

**Anti-pattern 1: Silent failures**

```python
# ❌
try:
    do_something()
except:
    pass
```

**Fix:**

```python
# ✅
try:
    do_something()
except Exception as e:
    logger.error(f"do_something failed: {e}")
    return {"error": str(e)}
```

**Anti-pattern 2: Blocking the event loop**

```python
# ❌ in an async hook
async def execute(self, context):
    time.sleep(5)  # blocks the entire application
    return {"status": "ok"}
```

**Fix:**

```python
# ✅
async def execute(self, context):
    await asyncio.sleep(5)
    return {"status": "ok"}
```

**Anti-pattern 3: Assuming hooks run alone**

```python
# ❌ — this hook assumes it's the only one running
async def execute(self, context):
    conn = psycopg.connect(context.data["conn_string"])
    conn.execute("DROP TABLE temp_workspace")  # could affect other hooks
```

**Fix:** Use uniquely-named temp tables or in-memory data structures.

---

## Complete Examples

### Python — Row Count Monitor

Fires after every query, logs the row count, and warns if a query
returned more than 100,000 rows.

```python
# src/hooks/python_hooks/row_count_monitor.py

from src.hooks.base_plugin import BaseHook, HookContext, HookTrigger
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Plugin(BaseHook):
    def get_metadata(self):
        return {
            "name": "Row Count Monitor",
            "version": "1.0.0",
            "author": "Your Name",
            "description": "Warns when a query returns a very large result set.",
            "triggers": [HookTrigger.QUERY_EXECUTED.value],
        }

    async def execute(self, context: HookContext) -> dict:
        row_count = context.data.get("row_count", 0)
        query = context.data.get("query", "")

        if row_count > 100_000:
            logger.warning(
                f"Large result set: {row_count:,} rows from {query[:80]}..."
            )
            return {
                "status": "warning",
                "message": f"Query returned {row_count:,} rows",
                "recommendation": "Add a LIMIT clause or refine the WHERE clause.",
            }

        return {"status": "ok", "row_count": row_count}
```

### Perl — Connection Auditor

Logs every successful connection to a file in the config directory.

```perl
# src/hooks/perl_hooks/connection_auditor.pm

package connection_auditor;
use strict;
use warnings;
use JSON;
use POSIX qw(strftime);

sub new {
    my $class = shift;
    return bless {}, $class;
}

sub get_metadata {
    return {
        name        => 'Connection Auditor',
        version     => '1.0.0',
        author      => 'Your Name',
        description => 'Logs every successful database connection.',
        triggers    => ['connection.opened'],
    };
}

sub execute {
    my ($self, $context) = @_;

    my $profile = $context->{data}{profile_name} || 'unknown';
    my $db      = $context->{database} || 'unknown';
    my $ts      = strftime('%Y-%m-%d %H:%M:%S', localtime);

    my $log_dir  = "$ENV{HOME}/.config/sql-schema-studio";
    my $log_file = "$log_dir/connection_audit.log";

    mkdir $log_dir unless -d $log_dir;

    if (open(my $fh, '>>', $log_file)) {
        print $fh "[$ts] connected: profile=$profile db=$db\n";
        close($fh);
    }

    return {
        status  => 'ok',
        message => 'Connection logged',
        log     => $log_file,
    };
}

1;
```

### Python — Scheduled Table Bloat Check

Runs every 6 hours and reports tables with >20% dead tuples.

```python
# src/hooks/python_hooks/bloat_check.py

from src.hooks.base_plugin import BaseHook, HookContext, HookTrigger
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Plugin(BaseHook):
    def get_metadata(self):
        return {
            "name": "Bloat Check",
            "version": "1.0.0",
            "author": "Your Name",
            "description": "Reports tables with >20% dead tuples.",
            "triggers": [HookTrigger.SCHEDULED_INTERVAL.value],
        }

    async def execute(self, context: HookContext) -> dict:
        conn_string = context.data.get("conn_string", "")
        if not conn_string:
            return {"error": "No active connection"}

        import psycopg

        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT schemaname, relname, n_dead_tup, n_live_tup
                    FROM pg_stat_user_tables
                    WHERE n_live_tup > 0
                      AND n_dead_tup * 100.0 / n_live_tup > 20
                    ORDER BY n_dead_tup DESC
                """)
                bloated = cur.fetchall()

        if not bloated:
            return {"status": "ok", "message": "No bloated tables"}

        return {
            "status": "warning",
            "message": f"{len(bloated)} bloated tables",
            "tables": [
                {
                    "schema": row[0],
                    "table": row[1],
                    "dead": row[2],
                    "live": row[3],
                    "ratio": round(row[2] / row[3] * 100, 1),
                }
                for row in bloated
            ],
        }
```

---

## Further Reading

- **`src/hooks/base_plugin.py`** — the `BaseHook`, `BasePlugin`, and
  `HookContext` definitions.
- **`src/hooks/registry.py`** — how hooks are discovered and registered.
- **`src/hooks/sandbox.py`** — the memory and time limits.
- **`src/hooks/python_hooks/`** — built-in Python hooks.
- **`src/hooks/perl_hooks/`** — built-in Perl hooks.
- **`CONTRIBUTING.md`** — general contribution guidelines.

---

*This document is part of SQL Schema Studio 0.9.5. It is licensed under
GPLv3+ and may be redistributed and modified under the same terms.*
