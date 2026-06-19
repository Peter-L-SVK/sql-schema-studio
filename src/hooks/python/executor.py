# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Python Hook Executor (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Python hook executor"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Dict, Any, List
from ..base_plugin import BaseHook, HookContext
from ..sandbox import SandboxedExecutor


class PythonHookExecutor:
    """Manages Python hook lifecycle"""

    def __init__(self, sandbox: SandboxedExecutor | None = None):
        self.sandbox = sandbox or SandboxedExecutor()
        self._loaded_hooks: Dict[str, BaseHook] = {}
        self._metrics: Dict[str, List[float]] = {}

    async def load_hook(self, hook_path: Path) -> BaseHook:
        """Dynamic import with validation"""
        spec = importlib.util.spec_from_file_location(hook_path.stem, hook_path)  # type: ignore[attr-defined]
        module = importlib.util.module_from_spec(spec)  # type: ignore[attr-defined]
        spec.loader.exec_module(module)

        hook_instance = module.Plugin()

        if hook_instance.validate():
            metadata = hook_instance.get_metadata()
            self._loaded_hooks[metadata["name"]] = hook_instance
            hook_instance = module.Plugin()
            # Add assertion to narrow the type:
            assert isinstance(hook_instance, BaseHook)

        raise ValueError(f"Hook validation failed: {hook_path}")

    async def execute_hook(self, hook_name: str, context: HookContext) -> Dict[str, Any]:
        """Execute a loaded hook with sandboxing"""
        hook = self._loaded_hooks.get(hook_name)
        if not hook:
            return {"error": f"Hook not found: {hook_name}"}

        result = await self.sandbox.execute_python(hook, context)
        return result
