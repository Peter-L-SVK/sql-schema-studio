# ----------------------------------------------------------------------
# SQL Schema Studio 0.8 - Python-Perl Bridge (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""
Python from/to Perl data marshaling bridge
"""

from __future__ import annotations

import json
from typing import Dict, Any
from datetime import datetime, date
from decimal import Decimal


class DataBridge:
    """Converts data between Python and Perl compatible formats"""

    @staticmethod
    def python_to_json(obj: Any) -> Any:
        """Convert Python objects to JSON-safe format"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        elif isinstance(obj, set):
            return list(obj)
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        return obj

    @staticmethod
    def marshal_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare context for cross-language transfer"""
        # Remove non-serializable objects
        safe_context = {}
        for key, value in context.items():
            if key in ["connection_pool", "logger", "db_connector"]:
                continue
            try:
                json.dumps(value, default=DataBridge.python_to_json)
                safe_context[key] = value
            except (TypeError, ValueError):
                safe_context[key] = str(value)

        return safe_context

    @staticmethod
    def json_to_python(data: Any) -> Any:
        """Convert JSON data back to Python types"""
        if isinstance(data, dict):
            return {k: DataBridge.json_to_python(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [DataBridge.json_to_python(item) for item in data]
        return data
