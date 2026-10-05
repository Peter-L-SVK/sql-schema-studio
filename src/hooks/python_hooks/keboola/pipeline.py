# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Keboola Pipeline Orchestration (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""End-to-end Keboola transformation pipeline.

Orchestrates the full flow:
    1. Upload CSV to Keboola Storage
    2. Create or update a transformation config
    3. Trigger the transformation job
    4. Poll until the job finishes
    5. Download the cleaned output table as CSV
    6. Return a structured report

The pipeline is synchronous (uses requests + kbcstorage under the hood).
Callers on the GTK thread should wrap it in asyncio.to_thread().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from src.hooks.python_hooks.keboola.client import KeboolaClient, KeboolaError
from src.hooks.python_hooks.keboola.engines import get_engine
from src.hooks.python_hooks.keboola.profiles import KeboolaProfile
from src.utils.logging import get_logger

logger = get_logger(__name__)


# Type alias for the progress callback
ProgressCallback = Callable[[str, str], None]


@dataclass
class PipelineStep:
    """Result of a single pipeline step."""

    name: str
    status: str  # "ok" | "error" | "skipped"
    duration: float = 0.0
    detail: dict = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "step": self.name,
            "status": self.status,
            "duration": round(self.duration, 2),
            "detail": self.detail,
            "error": self.error,
        }


@dataclass
class PipelineReport:
    """Full report of a pipeline run."""

    status: str = "ok"  # "ok" | "error"
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0
    steps: list[PipelineStep] = field(default_factory=list)
    output_table: str = ""
    downloaded_csv: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": round(self.duration_seconds, 2),
            "steps": [s.to_dict() for s in self.steps],
            "output_table": self.output_table,
            "downloaded_csv": self.downloaded_csv,
            "error": self.error,
        }


class TransformationPipeline:
    """Orchestrates the full CSV → Keboola → cleaned CSV flow."""

    def __init__(
        self,
        profile: KeboolaProfile,
        on_progress: Optional[ProgressCallback] = None,
    ):
        self.profile = profile
        self.on_progress = on_progress

        token = profile.get_token()
        if not token:
            raise KeboolaError(
                f"Profile '{profile.name}' has no API token in keyring. "
                "Open the configuration dialog and set it."
            )

        self.client = KeboolaClient(profile.api_url, token)
        self.engine_config = get_engine(profile.engine)

    # ==================================================================
    # Helpers
    # ==================================================================

    def _progress(self, step: str, message: str) -> None:
        """Fire the progress callback if one was supplied."""
        logger.info(f"[pipeline] {step}: {message}")
        if self.on_progress:
            try:
                self.on_progress(step, message)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    def _output_table_id(self) -> str:
        """Build the fully-qualified output table id (bucket.table)."""
        prefix = self.engine_config["default_output_prefix"]
        return f"{prefix}.{self.profile.output_table}"

    def _input_table_id(self) -> str:
        """Build the fully-qualified input table id (bucket.table)."""
        return f"{self.profile.bucket}.{self.profile.input_table}"

    # ==================================================================
    # Steps
    # ==================================================================

    def _step_upload(self, csv_path: str) -> PipelineStep:
        """Upload the CSV file to Keboola Storage."""
        step = PipelineStep(name="upload", status="ok")
        start = datetime.now()

        self._progress("upload", f"Uploading {Path(csv_path).name} → {self.profile.bucket}")
        try:
            table = self.client.upload_csv(
                bucket=self.profile.bucket,
                table_name=self.profile.input_table,
                csv_path=csv_path,
            )
            step.detail = {
                "table_id": f"{self.profile.bucket}.{self.profile.input_table}",
                "rows": table.get("rowsCount") if isinstance(table, dict) else None,
            }
        except KeboolaError as e:
            step.status = "error"
            step.error = str(e)
        step.duration = (datetime.now() - start).total_seconds()
        return step

    def _step_transform(self) -> PipelineStep:
        """Create a new transformation or update the existing one."""
        step = PipelineStep(name="transform", status="ok")
        start = datetime.now()

        is_update = bool(self.profile.transformation_id)
        action = "Updating" if is_update else "Creating"
        self._progress(
            "transform",
            f"{action} transformation on {self.engine_config['display_name']}",
        )

        try:
            if is_update:
                config = self.client.update_transformation(
                    engine=self.profile.engine,
                    config_id=self.profile.transformation_id,  # type: ignore[arg-type]
                    sql_script=self.profile.sql_script,
                    name=f"SQL Schema Studio - {self.profile.output_table}",
                    input_table=self._input_table_id(),
                    output_table=self._output_table_id(),
                )
            else:
                config = self.client.create_transformation(
                    engine=self.profile.engine,
                    name=f"SQL Schema Studio - {self.profile.output_table}",
                    sql_script=self.profile.sql_script,
                    input_table=self._input_table_id(),
                    output_table=self._output_table_id(),
                )
                # Persist the new config id back into the profile so the
                # next run updates instead of creating yet another config.
                new_id = config.get("id")
                if new_id:
                    self.profile.transformation_id = str(new_id)

            step.detail = {
                "config_id": config.get("id"),
                "action": "update" if is_update else "create",
            }
        except KeboolaError as e:
            step.status = "error"
            step.error = str(e)
        step.duration = (datetime.now() - start).total_seconds()
        return step

    def _step_trigger(self) -> PipelineStep:
        """Trigger the transformation job."""
        step = PipelineStep(name="trigger", status="ok")
        start = datetime.now()

        self._progress("trigger", "Triggering job")
        try:
            job = self.client.trigger_job(
                engine=self.profile.engine,
                config_id=self.profile.transformation_id,  # type: ignore[arg-type]
            )
            step.detail = {"job_id": job.get("id")}
        except KeboolaError as e:
            step.status = "error"
            step.error = str(e)
        step.duration = (datetime.now() - start).total_seconds()
        return step

    def _step_wait(self, job_id: str, timeout: int = 300) -> PipelineStep:
        """Poll the job until it finishes or times out."""
        step = PipelineStep(name="wait", status="ok")
        start = datetime.now()

        self._progress("wait", f"Waiting for job {job_id} (timeout {timeout}s)")
        try:
            final = self.client.wait_for_job(job_id, timeout=timeout)
            status = final.get("status")
            step.detail = {
                "job_id": job_id,
                "final_status": status,
                "finished": final.get("isFinished", False),
            }

            if status == "timeout":
                step.status = "error"
                step.error = f"Job did not finish within {timeout}s"
            elif status != "success":
                # Extract the actual error message from the job payload
                result = final.get("result", {}) or {}
                message = result.get("message") or result.get("error") or status
                step.status = "error"
                step.error = f"Job failed: {message}"
        except Exception as e:
            step.status = "error"
            step.error = str(e)

        step.duration = (datetime.now() - start).total_seconds()
        return step

    def _step_download(self) -> PipelineStep:
        """Download the output table as CSV."""
        step = PipelineStep(name="download", status="ok")
        start = datetime.now()

        output_id = self._output_table_id()
        self._progress("download", f"Downloading {output_id} → {self.profile.download_dir}")

        try:
            path = self.client.download_table_csv(
                table_id=output_id,
                output_dir=self.profile.download_dir,
            )
            step.detail = {"path": path, "table_id": output_id}
        except KeboolaError as e:
            step.status = "error"
            step.error = str(e)
        step.duration = (datetime.now() - start).total_seconds()
        return step

    # ==================================================================
    # Public entry point
    # ==================================================================

    def run(self, csv_path: str, timeout: int = 300) -> PipelineReport:
        """Run the full pipeline. Never raises — errors go into the report.

        Args:
            csv_path: Path to the raw CSV file to upload.
            timeout: Max seconds to wait for the transformation job.

        Returns:
            PipelineReport with per-step details and final status.
        """
        report = PipelineReport()
        report.started_at = datetime.now().isoformat()
        start_time = datetime.now()

        logger.info(
            f"Pipeline started — profile='{self.profile.name}' "
            f"engine='{self.profile.engine}' csv='{csv_path}'"
        )

        try:
            # 1. Upload
            upload = self._step_upload(csv_path)
            report.steps.append(upload)
            if upload.status == "error":
                report.status = "error"
                report.error = upload.error
                return self._finalize(report, start_time)

            # 2. Create or update transformation
            transform = self._step_transform()
            report.steps.append(transform)
            if transform.status == "error":
                report.status = "error"
                report.error = transform.error
                return self._finalize(report, start_time)

            # 3. Trigger job
            trigger = self._step_trigger()
            report.steps.append(trigger)
            if trigger.status == "error":
                report.status = "error"
                report.error = trigger.error
                return self._finalize(report, start_time)

            job_id = trigger.detail.get("job_id")
            if not job_id:
                report.status = "error"
                report.error = "Trigger step returned no job id"
                return self._finalize(report, start_time)

            # 4. Wait for completion
            wait = self._step_wait(str(job_id), timeout=timeout)
            report.steps.append(wait)
            if wait.status == "error":
                report.status = "error"
                report.error = wait.error
                return self._finalize(report, start_time)

            # 5. Download cleaned CSV
            report.output_table = self._output_table_id()
            if self.profile.auto_download:
                download = self._step_download()
                report.steps.append(download)
                if download.status == "error":
                    # Download failure is NOT fatal — the transformation
                    # already succeeded. Report it but keep status="ok".
                    report.error = f"Download warning: {download.error}"
                else:
                    report.downloaded_csv = download.detail.get("path", "")
            else:
                report.steps.append(
                    PipelineStep(
                        name="download",
                        status="skipped",
                        detail={"reason": "auto_download disabled"},
                    )
                )

        except Exception as e:
            # Catch-all for unexpected errors
            logger.exception(f"Pipeline crashed unexpectedly: {e}")
            report.status = "error"
            report.error = f"Unexpected error: {e}"

        return self._finalize(report, start_time)

    def _finalize(self, report: PipelineReport, start_time: datetime) -> PipelineReport:
        """Fill in the timing fields and fire a final progress event."""
        report.finished_at = datetime.now().isoformat()
        report.duration_seconds = (datetime.now() - start_time).total_seconds()

        if report.status == "ok":
            self._progress("done", f"Pipeline finished in {report.duration_seconds:.1f}s")
        else:
            self._progress("error", report.error or "Pipeline failed")

        logger.info(
            f"Pipeline finished — status={report.status} "
            f"duration={report.duration_seconds:.1f}s"
        )
        return report
