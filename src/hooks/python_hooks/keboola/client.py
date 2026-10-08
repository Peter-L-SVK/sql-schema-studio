# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Keboola API Client (GPLv3)
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

Notes from real-world testing:
  * Queue API lives on a separate host: connection.* → queue.*
  * In branch context, `state` must not be sent on config update.
  * Input/output mapping lives under `configuration.storage`, NOT
    directly under `configuration`.
  * Input tables reject `primary_key` (that's an output-only field).
  * Output tables reject `column_types` (that's an input-only field).
  * kbcstorage's Tables.create() has no `incremental` kwarg.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

import requests

from src.hooks.python_hooks.keboola.engines import get_engine
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Try to import kbcstorage; if missing, we fail fast with a helpful message.
try:
    from kbcstorage.client import Client as KbcStorageClient
except ImportError:
    KbcStorageClient = None  # type: ignore[assignment,misc]
    logger.warning("kbcstorage not installed. Run: pip install kbcstorage")


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
            raise KeboolaError(
                f"Token verification failed: {e.response.status_code}"
            ) from e
        except requests.RequestException as e:
            raise KeboolaError(f"Network error: {e}") from e

    # ==================================================================
    # Storage API (via kbcstorage)
    # ==================================================================

    def upload_csv(self, bucket: str, table_name: str, csv_path: str) -> dict:
        """Upload CSV as a table, replacing any existing table with that name.

        The Storage API's tables.create() refuses to create a table whose
        display name already exists — even if we intend to replace the
        data. kbcstorage does not expose tables.delete(), so we call the
        Storage API directly with requests.

        If the delete fails (table didn't exist, or permission issue), we
        proceed and let create() report the real error.
        """
        path = Path(csv_path)
        if not path.exists():
            raise KeboolaError(f"CSV file not found: {csv_path}")

        table_id = f"{bucket}.{table_name}"

        # --- Try to delete any existing table with this name ---
        self._delete_table_if_exists(table_id)

        try:
            table = self.storage.tables.create(
                name=table_name,
                bucket_id=bucket,
                file_path=str(path),
            )
            logger.info(f"Uploaded {csv_path} → {table_id}")
            return table
        except Exception as e:
            raise KeboolaError(f"Upload failed: {e}") from e

    def _delete_table_if_exists(self, table_id: str) -> None:
        """Delete a Storage table via HTTP if it exists.

        Used before upload to work around tables.create() refusing to
        replace a table with the same display name. The Storage API
        requires the table to be deleted first.

        This is best-effort: any error is logged but not raised, so the
        caller can proceed and surface a more relevant error if needed.
        """
        url = f"{self.api_url}/v2/storage/tables/{table_id}"
        try:
            r = self.session.delete(url, timeout=30)
            if r.status_code in (200, 202, 204):
                logger.info(f"Deleted existing table {table_id} before upload")
            elif r.status_code == 404:
                logger.debug(f"Table {table_id} does not exist — nothing to delete")
            else:
                logger.warning(
                    f"Delete table {table_id} returned HTTP {r.status_code}: "
                    f"{r.text[:200]}"
                )
        except requests.RequestException as e:
            logger.debug(f"Delete table {table_id} failed: {e}")

    def download_table_csv(self, table_id: str, output_dir: str) -> str:
        """Download a table as CSV into output_dir.

        kbcstorage auto-stitches sliced files. Returns the path of the
        main exported file.

        Keboola's export_to_file names the file after the table, but the
        exact name varies by API version — sometimes 'out_cleaned_data.csv',
        sometimes 'out_cleaned_data' without an extension. We try a series
        of patterns and pick the newest matching file.
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

        table_short = table_id.split(".")[-1]

        # Try patterns in order — stop at the first one that finds a file.
        # Sorting by mtime ensures we get the freshest export if multiple
        # files happen to match.
        candidates: list[Path] = []
        for pattern in (f"{table_short}*.csv", f"{table_short}*", "*.csv", "*"):
            candidates = sorted(
                [p for p in out.glob(pattern) if p.is_file()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                break

        if not candidates:
            raise KeboolaError(f"No file found after export in {output_dir}")

        # If the file has no .csv suffix, rename it — downstream tools
        # (file manager, Excel, pandas) expect the extension.
        chosen = candidates[0]
        if chosen.suffix.lower() != ".csv":
            renamed = chosen.with_suffix(".csv")
            chosen.rename(renamed)
            chosen = renamed
            logger.info(f"Renamed download to add .csv suffix: {chosen.name}")

        logger.info(f"Downloaded {table_id} → {chosen}")
        return str(chosen)

    # ==================================================================
    # Configuration API — transformations
    # ==================================================================

    def _component_url(self, component_id: str, config_id: str | None = None) -> str:
        base = (
            f"{self.api_url}/v2/storage/branch/default/components/"
            f"{component_id}/configs"
        )
        return f"{base}/{config_id}" if config_id else base

    @staticmethod
    def _build_input_storage(input_table: str) -> dict:
        """Build a single input table mapping.

        Allowed fields for input.tables[]:
            source, destination, where_column, where_operator, where_values,
            columns, column_types, changed_since, days, limit, load_type,
            overwrite, use_view, source_branch_id, file_type,
            keep_internal_timestamp_column

        NOT allowed: primary_key (output-only).
        """
        input_short = input_table.split(".")[-1]
        return {
            "tables": [
                {
                    "source": input_table,
                    "destination": input_short,
                    "where_column": "",
                    "where_operator": "eq",
                    "where_values": [],
                    "columns": [],
                    "column_types": [],
                }
            ]
        }

    @staticmethod
    def _build_output_storage(output_table: str) -> dict:
        """Build a single output table mapping.

        Allowed fields for output.tables[]:
            source, destination, primary_key, write_always, delimiter,
            enclosure, columns, has_header, incremental, schema,
            distribution_key, deduplication_strategy, delete_where,
            delete_where_column, delete_where_operator, delete_where_values,
            description, manifest_type, metadata, column_metadata,
            table_metadata, tags, unload_strategy

        NOT allowed: column_types (input-only).
        """
        output_short = output_table.split(".")[-1]
        return {
            "tables": [
                {
                    "source": output_short,
                    "destination": output_table,
                    "primary_key": [],
                    "write_always": False,
                    "delimiter": ",",
                    "enclosure": '"',
                    "columns": [],
                }
            ]
        }

    def create_transformation(
        self,
        engine: str,
        name: str,
        sql_script: str,
        input_table: str,
        output_table: str,
    ) -> dict:
        """Create a new transformation config. Returns the created config.

        Note: Keboola expects input/output mapping under
        `configuration.storage`, NOT directly under `configuration`.
        """
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
                                    "script": [sql_script],
                                }
                            ],
                        }
                    ]
                },
                "storage": {
                    "input": self._build_input_storage(input_table),
                    "output": self._build_output_storage(output_table),
                },
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

        Note: In branch context, `state` must be stripped from the payload.
        Input/output mapping lives under `configuration.storage`, NOT
        directly under `configuration`.
        """
        eng = get_engine(engine)
        component_id = eng["component_id"]

        # Fetch current config so we don't destroy anything
        current = self._get_transformation(component_id, config_id)

        # Branch context forbids sending `state` on update
        current.pop("state", None)

        cfg = current.get("configuration", {})
        params = cfg.setdefault("parameters", {})
        blocks = params.setdefault("blocks", [])

        if not blocks:
            blocks.append({"name": "Main", "codes": []})
        codes = blocks[0].setdefault("codes", [])
        if not codes:
            codes.append({"name": "SQL", "script": []})
        codes[0]["script"] = [sql_script]

        if name is not None:
            current["name"] = name

        # Rebuild storage.input / storage.output under the right key
        storage = cfg.setdefault("storage", {})

        # Clean up legacy top-level `input` / `output` keys written by older
        # versions. Keboola rejects them at job runtime ("Unrecognized options
        # input, output under configuration"). Because we PUT back the whole
        # fetched config, they would otherwise survive every update forever.
        # Migrate them into `storage` only if storage lacks that side.
        for key in ("input", "output"):
            legacy = cfg.pop(key, None)
            if legacy is not None and key not in storage:
                storage[key] = (
                    legacy if isinstance(legacy, dict) else {"tables": legacy}
                )
                logger.info(f"Migrated legacy configuration.{key} → storage.{key}")

        if input_table is not None:
            storage["input"] = self._build_input_storage(input_table)

        if output_table is not None:
            storage["output"] = self._build_output_storage(output_table)

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
        """Trigger a transformation job via the Queue API.

        Note: The Queue API lives on a different host than the Storage API.
        For a regional stack like us-east4.gcp, the Queue host is
        https://queue.us-east4.gcp.keboola.com
        """
        eng = get_engine(engine)
        component_id = eng["component_id"]

        # Derive the Queue host from the Storage API URL
        # connection.us-east4.gcp.keboola.com -> queue.us-east4.gcp.keboola.com
        queue_host = self.api_url.replace("connection.", "queue.")
        url = f"{queue_host}/jobs"

        payload = {
            "mode": "run",
            "component": component_id,
            "config": config_id,
        }

        try:
            r = self.session.post(url, json=payload, timeout=15)
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
        # Queue jobs must be polled on the Queue host, not the Storage API
        # (/v2/storage/jobs only knows Storage jobs and would never resolve).
        queue_host = self.api_url.replace("connection.", "queue.")
        url = f"{queue_host}/jobs/{job_id}"
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

    def cancel_job(self, job_id: str) -> bool:
        """Request cancellation of a running queue job.

        Sends POST to the Queue API's /kill endpoint. Returns True on
        success (HTTP 200), False if the job couldn't be cancelled
        (already finished, not found, or API error).

        Note: This is best-effort. Even if the API call succeeds, the
        job may already be in a terminal state — the caller should not
        rely on cancellation having taken effect without re-checking.
        """
        queue_host = self.api_url.replace("connection.", "queue.")
        url = f"{queue_host}/jobs/{job_id}/kill"

        try:
            r = self.session.post(url, timeout=15)
            if r.status_code == 200:
                logger.info(f"Cancelled job {job_id}")
                return True
            logger.warning(
                f"Cancel job {job_id} returned HTTP {r.status_code}: "
                f"{r.text[:200]}"
            )
            return False
        except requests.RequestException as e:
            logger.error(f"Cancel job {job_id} failed: {e}")
            return False

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
