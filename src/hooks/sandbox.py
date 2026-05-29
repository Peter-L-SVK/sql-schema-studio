# ----------------------------------------------------------------------
# SQL Schema Studio 0.6 - Sandbox Executor (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""
Secure execution environment for hooks
"""

from __future__ import annotations

import asyncio
import resource
from typing import Dict, Any

from src.config import HOOK_MEMORY_LIMIT_MB, HOOK_TIME_LIMIT_SECONDS


class SandboxedExecutor:
    """Executes hooks with resource limits and restrictions"""

    def __init__(
        self,
        memory_limit_mb: int = HOOK_MEMORY_LIMIT_MB,
        time_limit_seconds: int = HOOK_TIME_LIMIT_SECONDS,
        restricted_modules: list | None = None,
    ):
        self.memory_limit = memory_limit_mb * 1024 * 1024
        self.time_limit = time_limit_seconds
        self.restricted_modules = restricted_modules or [
            "os.system",
            "subprocess.call",
            "shutil.rmtree",
        ]

    async def execute_python(self, hook, context) -> dict[str, Any]:
        """Execute Python hook with resource limits"""
        try:
            # Set memory limit
            resource.setrlimit(resource.RLIMIT_AS, (self.memory_limit, self.memory_limit))

            # Execute with timeout
            async with asyncio.timeout(self.time_limit):
                result = await hook.execute(context)
                return dict(result) if isinstance(result, dict) else {"result": result}

        except asyncio.TimeoutError:
            return {"error": f"Execution exceeded {self.time_limit}s limit"}
        except MemoryError:
            return {"error": "Memory limit exceeded"}
        except Exception as e:
            return {"error": str(e)}

    async def execute_perl(
        self, perl_executor, hook_path: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Perl hook with resource limits"""
        # Perl execution happens in subprocess with its own limits
        from typing import cast

        return cast(
            dict[str, Any], await perl_executor.execute(hook_path, context, self.time_limit)
        )

    def validate_code(self, code: str) -> bool:
        """Check code for dangerous operations"""
        dangerous_patterns = [
            "import os",
            "import subprocess",
            "__import__",
            "eval(",
            "exec(",
            "open(",
            "file(",
        ]

        for pattern in dangerous_patterns:
            if pattern in code:
                return False
        return True
