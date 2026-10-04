# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Keboola API Client (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Keboola API client — hybrid wrapper.

Storage API (buckets, tables, files) is handled by the official
`kbcstorage` client so we get sliced-file stitching and error handling
for free. Configuration and Queue API (transformations, jobs) are
handled by `requests` because kbcstorage does not expose them.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import requests

from src.hooks.python_hooks.keboola.engines import get_engine
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Try to import kbcstorage; if missing, we fail fast with a helpful message.
try:
    from kbcstorage.client import Client as KbcStorageClient
except ImportError:
    KbcStorageClient = None  # type: ignore[assignment,misc]
    logger.warning(
        "kbcstorage not installed. Run: pip install kbcstorage"
    )


class KeboolaError(Exception):
    """Raised when a Keboola API call fails."""


class KeboolaClient:
    """Hybrid client for Keboola Storage + Configuration/Queue API."""

    def __init__(self, api_url: str, token: str):
        if KbcStorageClient is None:
            raise KeboolaError(
                "kbcstorage client not installed. Run: pip install kbcstorage"
            )
        if not token:
            raise KeboolaError("API token is empty")

        self.api_url = api_url.rstrip("/")
        self.token = token

        # Storage API — official client
        self.storage = KbcStorageClient(self.api_url, token)

        # Configuration + Queue API — raw HTTP
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-StorageApi-Token": token,
                "Content-Type": "application/json",
            }
        )

    # ==================================================================
    # Connection check
    # ==================================================================

    def verify_connection(self) -> dict[str, Any]:
        """Verify token by fetching project info. Raises KeboolaError on failure."""
        url = f"{self.api_url}/v2/storage/tokens/verify"
        try:
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            raise KeboolaError(f"Token verification failed: {e.response.status_code}") from e
        except requests.RequestException as e:
            raise KeboolaError(f"Network error: {e}") from e

    # ==================================================================
    # Storage API (via kbcstorage)
    # ==================================================================

    def upload_csv(self, bucket: str, table_name: str, csv_path: str) -> dict:
        """Upload CSV as a table. Creates or replaces the table.

        kbcstorage handles incremental uploads, primary keys, and the
        multipart file transfer for us.
        """
        path = Path(csv_path)
        if not path.exists():
            raise KeboolaError(f"CSV file not found: {csv_path}")

        try:
            table = self.storage.tables.create(
                name=table_name,
                bucket_id=bucket,
                file_path=str(path),
                incremental=False,  # full replace
            )
            logger.info(f"Uploaded {csv_path} → {bucket}.{table_name}")
            return table
        except Exception as e:
            raise KeboolaError(f"Upload failed: {e}") from e

    def download_table_csv(self, table_id: str, output_dir: str) -> str:
        """Download a table as CSV into output_dir.

        kbcstorage auto-stitches sliced files. Returns the path of the
        main exported file (first file in the directory after export).
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        try:
            self.storage.tables.export_to_file(
                table_id=table_id,
                path_name=str(out),
            )
        except Exception as e:
            raise KeboolaError(f"Download failed: {e}") from e

        # kbcstorage names the file after the table, e.g. "out_cleaned_data.csv"
        table_short = table_id.split(".")[-1]
        candidates = sorted(out.glob(f"{table_short}*.csv"))
        if not candidates:
            # Fallback: pick the newest .csv in the dir
            candidates = sorted(out.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)

        if not candidates:
            raise KeboolaError(f"No CSV found after export in {output_dir}")

        logger.info(f"Downloaded {table_id} → {candidates[0]}")
        return str(candidates[0])

    # ==================================================================
    # Configuration API — transformations
    # ==================================================================

    def _component_url(self, component_id: str, config_id: str | None = None) -> str:
        base = f"{self.api_url}/v2/storage/branch/default/components/{component_id}/configs"
        return f"{base}/{config_id}" if config_id else base

    def create_transformation(
        self,
        engine: str,
        name: str,
        sql_script: str,
        input_table: str,
        output_table: str,
    ) -> dict:
        """Create a new transformation config. Returns the created config."""
        eng = get_engine(engine)
        component_id = eng["component_id"]

        payload = {
            "name": name,
            "description": "Created by SQL Schema Studio",
            "configuration": {
                "parameters": {
                    "blocks": [
                        {
                            "name": "Main",
                            "codes": [
                                {
                                    "name": "SQL",
                                    "script": sql_script.splitlines(),
                                }
                            ],
                        }
                    ]
                },
                "input": [
                    {
                        "source": input_table,
                        "destination": input_table.split(".")[-1],
                    }
                ],
                "output": [
                    {
                        "source": output_table.split(".")[-1],
                        "destination": output_table,
                    }
                ],
            },
        }

        url = self._component_url(component_id)
        try:
            r = self.session.post(url, json=payload, timeout=30)
            r.raise_for_status()
            config = r.json()
            logger.info(
                f"Created transformation '{name}' (id={config.get('id')}) "
                f"on {eng['display_name']}"
            )
            return config
        except requests.HTTPError as e:
            body = e.response.text[:500]
            raise KeboolaError(
                f"Create transformation failed ({e.response.status_code}): {body}"
            ) from e

    def update_transformation(
        self,
        engine: str,
        config_id: str,
        sql_script: str,
        name: str | None = None,
        input_table: str | None = None,
        output_table: str | None = None,
    ) -> dict:
        """Update an existing transformation config.

        Only the SQL script (and optionally the name/mappings) is changed.
        Other fields (existing input/output mapping, block structure) are
        preserved by fetching the config first and patching it.
        """
        eng = get_engine(engine)
        component_id = eng["component_id"]

        # Fetch current config so we don't destroy anything
        current = self._get_transformation(component_id, config_id)

        cfg = current.get("configuration", {})
        params = cfg.setdefault("parameters", {})
        blocks = params.setdefault("blocks", [])

        if not blocks:
            blocks.append({"name": "Main", "codes": []})
        codes = blocks[0].setdefault("codes", [])
        if not codes:
            codes.append({"name": "SQL", "script": []})
        codes[0]["script"] = sql_script.splitlines()

        if name is not None:
            current["name"] = name

        if input_table is not None:
            cfg["input"] = [
                {
                    "source": input_table,
                    "destination": input_table.split(".")[-1],
                }
            ]
        if output_table is not None:
            cfg["output"] = [
                {
                    "source": output_table.split(".")[-1],
                    "destination": output_table,
                }
            ]

        url = self._component_url(component_id, config_id)
        try:
            r = self.session.put(url, json=current, timeout=30)
            r.raise_for_status()
            logger.info(f"Updated transformation id={config_id}")
            return r.json()
        except requests.HTTPError as e:
            body = e.response.text[:500]
            raise KeboolaError(
                f"Update transformation failed ({e.response.status_code}): {body}"
            ) from e

    def _get_transformation(self, component_id: str, config_id: str) -> dict:
        """Fetch a single transformation config."""
        url = self._component_url(component_id, config_id)
        try:
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            raise KeboolaError(
                f"Get transformation failed ({e.response.status_code}): "
                f"{e.response.text[:300]}"
            ) from e

    # ==================================================================
    # Queue API — jobs
    # ==================================================================

    def trigger_job(self, engine: str, config_id: str) -> dict:
        """Trigger a transformation job. Returns the job record."""
        eng = get_engine(engine)
        component_id = eng["component_id"]

        url = f"{self._component_url(component_id, config_id)}/jobs"
        try:
            r = self.session.post(url, json={"mode": "run"}, timeout=15)
            r.raise_for_status()
            job = r.json()
            logger.info(f"Triggered job id={job.get('id')} for config={config_id}")
            return job
        except requests.HTTPError as e:
            body = e.response.text[:500]
            raise KeboolaError(
                f"Trigger job failed ({e.response.status_code}): {body}"
            ) from e

    def wait_for_job(self, job_id: str, timeout: int = 300, poll: int = 2) -> dict:
        """Poll job status until finished or timeout.

        Returns the final job record. If timeout expires, returns a
        synthetic record with status="timeout".
        """
        url = f"{self.api_url}/v2/storage/jobs/{job_id}"
        start = time.time()
        while time.time() - start < timeout:
            try:
                r = self.session.get(url, timeout=15)
                r.raise_for_status()
                data = r.json()
            except requests.RequestException as e:
                logger.warning(f"Job poll error: {e}")
                time.sleep(poll)
                continue

            status = data.get("status")
            if data.get("isFinished") or status in ("success", "error", "terminated"):
                logger.info(f"Job {job_id} finished with status={status}")
                return data
            time.sleep(poll)

        logger.warning(f"Job {job_id} timed out after {timeout}s")
        return {"id": job_id, "status": "timeout", "isFinished": False}

    # ==================================================================
    # Helpers — open file in system file manager
    # ==================================================================

    @staticmethod
    def open_in_file_manager(path: str) -> None:
        """Open a file or folder in the OS default application.

        Uses xdg-open (universal on Linux). Non-blocking.
        """
        p = Path(path)
        target = str(p.parent if p.is_file() else p)
        try:
            subprocess.Popen(
                ["xdg-open", target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.warning("xdg-open not found; cannot open file manager")
