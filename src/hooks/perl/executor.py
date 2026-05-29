# ----------------------------------------------------------------------
# SQL Schema Studio 0.6 - Perl Hook Executor (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""
Perl5 hook executor via subprocess IPC
"""

from __future__ import annotations

import json
import asyncio
from pathlib import Path
from typing import Dict, Any, cast


class PerlHookExecutor:
    """Execute Perl5 hooks in subprocess with JSON IPC"""

    def __init__(self, perl_binary: str = "/usr/bin/perl"):
        self.perl = perl_binary

    async def execute(
        self, hook_path: str, context: Dict[str, Any], timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute Perl hook with JSON serialization bridge"""

        perl_script = self._generate_wrapper(hook_path)

        process = await asyncio.create_subprocess_exec(
            self.perl,
            "-e",
            perl_script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(json.dumps(context).encode()), timeout=timeout
            )

            if process.returncode != 0:
                return {"error": stderr.decode(), "return_code": process.returncode}

            return cast(dict[str, Any], json.loads(stdout.decode()))

        except asyncio.TimeoutError:
            process.kill()
            return {"error": "Perl hook execution timeout"}

    def _generate_wrapper(self, hook_path: str) -> str:
        """Wrap Perl hook with JSON I/O"""
        return f"""
        use strict;
        use warnings;
        use JSON;
        use lib '{Path(hook_path).parent}';

        my $json_input = do {{ local $/; <STDIN> }};
        my $context = decode_json($json_input);

        require '{Path(hook_path).stem}';
        my $hook = {Path(hook_path).stem}->new();
        my $result = $hook->execute($context);

        print encode_json($result);
        """
