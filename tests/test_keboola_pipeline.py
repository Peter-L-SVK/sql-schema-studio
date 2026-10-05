# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Keboola Pipeline Tests (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# ----------------------------------------------------------------------

"""Tests for the Keboola transformation pipeline (mocked client)."""

from unittest.mock import MagicMock, patch

import pytest

from src.hooks.python_hooks.keboola.profiles import KeboolaProfile
from src.hooks.python_hooks.keboola.pipeline import (
    TransformationPipeline,
    PipelineReport,
)


@pytest.fixture
def profile():
    p = KeboolaProfile(
        name="test",
        engine="bigquery",
        bucket="in.c-test",
        input_table="csv_input",
        output_table="out_cleaned",
        transformation_id=None,
        sql_script="CREATE OR REPLACE TABLE `out_cleaned` AS SELECT 1;",
        auto_download=False,
    )
    return p


@pytest.fixture
def pipeline(profile, tmp_path):
    """Pipeline with mocked client."""
    with patch.object(KeboolaProfile, "get_token", return_value="fake-token"):
        with patch(
            "src.hooks.python_hooks.keboola.pipeline.KeboolaClient"
        ) as mock_client:
            p = TransformationPipeline(profile)
            p.client = MagicMock()
            yield p


class TestPipelineSteps:
    def test_upload_step_success(self, pipeline, tmp_path):
        csv = tmp_path / "input.csv"
        csv.write_text("a,b\n1,2\n")
        pipeline.client.upload_csv.return_value = {"rowsCount": 1}

        step = pipeline._step_upload(str(csv))
        assert step.status == "ok"
        assert step.detail["rows"] == 1
        pipeline.client.upload_csv.assert_called_once()

    def test_upload_step_error(self, pipeline, tmp_path):
        from src.hooks.python_hooks.keboola.client import KeboolaError

        csv = tmp_path / "input.csv"
        csv.write_text("a,b\n1,2\n")
        pipeline.client.upload_csv.side_effect = KeboolaError("boom")

        step = pipeline._step_upload(str(csv))
        assert step.status == "error"
        assert "boom" in step.error

    def test_transform_step_creates_new(self, pipeline, profile):
        pipeline.client.create_transformation.return_value = {"id": "99999"}
        step = pipeline._step_transform()
        assert step.status == "ok"
        assert step.detail["action"] == "create"
        assert step.detail["config_id"] == "99999"
        assert profile.transformation_id == "99999"  # persisted

    def test_transform_step_updates_existing(self, pipeline, profile):
        profile.transformation_id = "12345"
        pipeline.client.update_transformation.return_value = {"id": "12345"}
        step = pipeline._step_transform()
        assert step.status == "ok"
        assert step.detail["action"] == "update"

    def test_trigger_step(self, pipeline, profile):
        profile.transformation_id = "12345"
        pipeline.client.trigger_job.return_value = {"id": "job-1"}
        step = pipeline._step_trigger()
        assert step.status == "ok"
        assert step.detail["job_id"] == "job-1"

    def test_wait_step_success(self, pipeline):
        pipeline.client.wait_for_job.return_value = {
            "id": "job-1",
            "status": "success",
            "isFinished": True,
        }
        step = pipeline._step_wait("job-1")
        assert step.status == "ok"

    def test_wait_step_job_failed(self, pipeline):
        pipeline.client.wait_for_job.return_value = {
            "id": "job-1",
            "status": "error",
            "isFinished": True,
            "result": {"message": "SQL syntax error"},
        }
        step = pipeline._step_wait("job-1")
        assert step.status == "error"
        assert "SQL syntax error" in step.error

    def test_wait_step_timeout(self, pipeline):
        pipeline.client.wait_for_job.return_value = {
            "id": "job-1",
            "status": "timeout",
            "isFinished": False,
        }
        step = pipeline._step_wait("job-1", timeout=1)
        assert step.status == "error"
        assert "did not finish" in step.error


class TestPipelineRun:
    def test_full_success(self, pipeline, profile, tmp_path):
        csv = tmp_path / "input.csv"
        csv.write_text("a,b\n1,2\n")
        profile.auto_download = True

        pipeline.client.upload_csv.return_value = {"rowsCount": 1}
        pipeline.client.create_transformation.return_value = {"id": "99999"}
        pipeline.client.trigger_job.return_value = {"id": "job-1"}
        pipeline.client.wait_for_job.return_value = {
            "id": "job-1",
            "status": "success",
            "isFinished": True,
        }
        pipeline.client.download_table_csv.return_value = "/tmp/out_cleaned.csv"

        report = pipeline.run(str(csv))

        assert report.status == "ok"
        assert report.downloaded_csv == "/tmp/out_cleaned.csv"
        assert len(report.steps) == 5
        assert all(s.status == "ok" for s in report.steps)

    def test_upload_failure_stops_pipeline(self, pipeline, tmp_path):
        from src.hooks.python_hooks.keboola.client import KeboolaError

        csv = tmp_path / "input.csv"
        csv.write_text("a,b\n1,2\n")
        pipeline.client.upload_csv.side_effect = KeboolaError("upload failed")

        report = pipeline.run(str(csv))
        assert report.status == "error"
        assert "upload failed" in report.error
        # Only the upload step should have run
        assert len(report.steps) == 1
        assert report.steps[0].name == "upload"

    def test_wait_failure_stops_pipeline(self, pipeline, profile, tmp_path):
        csv = tmp_path / "input.csv"
        csv.write_text("a,b\n1,2\n")

        pipeline.client.upload_csv.return_value = {"rowsCount": 1}
        pipeline.client.create_transformation.return_value = {"id": "99999"}
        pipeline.client.trigger_job.return_value = {"id": "job-1"}
        pipeline.client.wait_for_job.return_value = {
            "id": "job-1",
            "status": "error",
            "isFinished": True,
            "result": {"message": "syntax error"},
        }

        report = pipeline.run(str(csv))
        assert report.status == "error"
        assert "syntax error" in report.error

    def test_download_failure_is_warning(self, pipeline, profile, tmp_path):
        from src.hooks.python_hooks.keboola.client import KeboolaError

        csv = tmp_path / "input.csv"
        csv.write_text("a,b\n1,2\n")
        profile.auto_download = True

        pipeline.client.upload_csv.return_value = {"rowsCount": 1}
        pipeline.client.create_transformation.return_value = {"id": "99999"}
        pipeline.client.trigger_job.return_value = {"id": "job-1"}
        pipeline.client.wait_for_job.return_value = {
            "id": "job-1",
            "status": "success",
            "isFinished": True,
        }
        pipeline.client.download_table_csv.side_effect = KeboolaError("download failed")

        report = pipeline.run(str(csv))
        # Transformation succeeded — status stays ok, download warning logged
        assert report.status == "ok"
        assert "download warning" in (report.error or "").lower()

    def test_progress_callback_fires(self, profile, tmp_path):
        csv = tmp_path / "input.csv"
        csv.write_text("a,b\n1,2\n")

        events = []

        def on_progress(step: str, message: str):
            events.append((step, message))

        with patch.object(KeboolaProfile, "get_token", return_value="fake-token"):
            with patch(
                "src.hooks.python_hooks.keboola.pipeline.KeboolaClient"
            ) as mock_client:
                p = TransformationPipeline(profile, on_progress=on_progress)
                p.client = MagicMock()
                p.client.upload_csv.return_value = {"rowsCount": 1}
                p.client.create_transformation.return_value = {"id": "99999"}
                p.client.trigger_job.return_value = {"id": "job-1"}
                p.client.wait_for_job.return_value = {
                    "id": "job-1",
                    "status": "success",
                    "isFinished": True,
                }
                p.run(str(csv))

        step_names = [e[0] for e in events]
        assert "upload" in step_names
        assert "transform" in step_names
        assert "trigger" in step_names
        assert "wait" in step_names
        assert "done" in step_names

    def test_report_to_dict(self):
        r = PipelineReport(status="ok", output_table="out.c.x")
        d = r.to_dict()
        assert d["status"] == "ok"
        assert d["output_table"] == "out.c.x"
        assert isinstance(d["steps"], list)
