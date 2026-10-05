# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Plugin Registry (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""
Plugin discovery and registration
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any, Dict, List
from .base_plugin import BaseHook, BasePlugin, HookTrigger
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PluginRegistry:
    """Manages plugin discovery, loading, and lifecycle"""

    def __init__(self):
        self._hooks: dict[str, BaseHook | dict[str, Any]] = {}
        self._plugins: Dict[str, BasePlugin] = {}
        self._hook_triggers: Dict[HookTrigger, List[str]] = {}

        # Initialize trigger lists
        for trigger in HookTrigger:
            self._hook_triggers[trigger] = []

    def discover_plugins(self):
        """Discover and load all available plugins"""
        hooks_dir = Path(__file__).parent.parent / "hooks"

        # Load Python hooks
        python_hooks = hooks_dir / "python_hooks"
        if python_hooks.exists():
            for hook_file in python_hooks.glob("*.py"):
                if hook_file.name != "__init__.py":
                    self._load_python_hook(hook_file)

        # Perl hooks are loaded on-demand
        self._discover_perl_hooks(hooks_dir / "perl_hooks")

    def _load_python_hook(self, hook_path: Path):
        """Load a Python hook from file"""
        try:
            module_name = f"src.hooks.python_hooks.{hook_path.stem}"
            module = importlib.import_module(module_name)

            # Find BaseHook subclasses
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, BaseHook) and obj != BaseHook:

                    hook_instance = obj()
                    metadata = hook_instance.get_metadata()
                    hook_name = metadata.get("name", hook_path.stem)

                    self.register_hook(hook_name, hook_instance, metadata)

        except Exception as e:
            logger.warning(f"Failed to load hook {hook_path}: {e}")

    def _discover_perl_hooks(self, perl_dir: Path):
        """Discover Perl hooks (loaded on execution)"""
        if perl_dir.exists():
            for hook_file in perl_dir.glob("*.pm"):
                # Register Perl hooks as available but don't load yet
                hook_name = f"perl_{hook_file.stem}"
                self._hooks[hook_name] = {"type": "perl", "path": str(hook_file), "loaded": False}

    def register_hook(self, name: str, hook: BaseHook, metadata: Dict):
        """Register a hook and its triggers"""
        self._hooks[name] = hook

        triggers = metadata.get("triggers", [])
        for trigger_str in triggers:
            try:
                trigger = HookTrigger(trigger_str)
                self._hook_triggers[trigger].append(name)
            except ValueError:
                logger.warning(f"Invalid trigger '{trigger_str}' for hook {name}")

    def get_hooks_for_trigger(self, trigger: HookTrigger) -> List[BaseHook]:
        """Get all hooks registered for a specific trigger"""
        hook_names = self._hook_triggers.get(trigger, [])
        result: list[BaseHook] = []
        for name in hook_names:
            hook = self._hooks[name]
            if isinstance(hook, BaseHook):
                result.append(hook)
        return result

    def list_hooks(self) -> Dict[str, Any]:
        """List all registered hooks."""
        result = {}
        for name, hook in self._hooks.items():
            result[name] = hook
        return result
