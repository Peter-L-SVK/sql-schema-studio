# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Keboola Tests (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# ----------------------------------------------------------------------

"""Tests for Keboola client, profiles, and engines (mocked)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.hooks.python_hooks.keboola.engines import ENGINES, get_engine, list_engines
from src.hooks.python_hooks.keboola.profiles import (
    KeboolaProfile,
    ProfileManager,
    KEYRING_SERVICE,
)


# =====================================================================
# Engines
# =====================================================================


class TestEngines:
    def test_bigquery_engine_exists(self):
        eng = get_engine("bigquery")
        assert eng["component_id"] == "keboola.google-bigquery-transformation"
        assert eng["identifier_quote"] == "`"

    def test_snowflake_engine_exists(self):
        eng = get_engine("snowflake")
        assert eng["component_id"] == "keboola.snowflake-transformation"
        assert eng["identifier_quote"] == '"'

    def test_unknown_engine_raises(self):
        with pytest.raises(ValueError, match="Unknown engine"):
            get_engine("oracle")

    def test_list_engines_returns_tuples(self):
        result = list_engines()
        assert len(result) == 2
        ids = [r[0] for r in result]
        assert "bigquery" in ids
        assert "snowflake" in ids


# =====================================================================
# Profiles
# =====================================================================


class TestKeboolaProfile:
    def test_default_values(self):
        p = KeboolaProfile(name="test")
        assert p.engine == "bigquery"
        assert p.api_url == "https://connection.keboola.com"
        assert p.transformation_id is None
        assert p.auto_download is True

    def test_validate_reports_missing_token(self):
        p = KeboolaProfile(name="test")
        with patch.object(p, "get_token", return_value=""):
            errors = p.validate()
        assert any("token" in e.lower() for e in errors)

    def test_validate_reports_bad_engine(self):
        p = KeboolaProfile(name="test", engine="oracle")
        with patch.object(p, "get_token", return_value="fake-token"):
            errors = p.validate()
        assert any("engine" in e.lower() for e in errors)

    def test_validate_clean_profile(self):
        p = KeboolaProfile(name="test")
        with patch.object(p, "get_token", return_value="fake-token"):
            assert p.validate() == []

    def test_to_dict_excludes_token(self):
        p = KeboolaProfile(name="test")
        d = p.to_dict()
        assert "token" not in d
        assert d["name"] == "test"

    def test_save_and_get_token_uses_keyring(self):
        p = KeboolaProfile(name="keyring-test")
        with patch("keyring.set_password") as mock_set:
            p.save_token("secret")
        mock_set.assert_called_once_with(
            KEYRING_SERVICE, "keyring-test/token", "secret"
        )


class TestProfileManager:
    @pytest.fixture
    def temp_config(self, tmp_path, monkeypatch):
        """Redirect profiles file to a temp dir."""
        fake_dir = tmp_path / "config"
        fake_dir.mkdir()
        fake_file = fake_dir / "keboola_profiles.json"
        monkeypatch.setattr(
            "src.hooks.python_hooks.keboola.profiles.CONFIG_DIR", fake_dir
        )
        monkeypatch.setattr(
            "src.hooks.python_hooks.keboola.profiles.PROFILES_FILE", fake_file
        )
        return fake_file

    def test_empty_manager(self, temp_config):
        mgr = ProfileManager()
        assert mgr.list_names() == []
        assert mgr.active is None

    def test_add_and_get(self, temp_config):
        mgr = ProfileManager()
        p = KeboolaProfile(name="test", engine="bigquery")
        mgr.add(p)
        assert mgr.get("test") is not None
        assert mgr.active_name == "test"  # first added becomes active

    def test_add_persists_to_json(self, temp_config):
        mgr = ProfileManager()
        mgr.add(KeboolaProfile(name="persisted"))
        assert temp_config.exists()
        with open(temp_config) as f:
            data = json.load(f)
        assert "persisted" in data["profiles"]
        assert data["active_profile"] == "persisted"

    def test_remove_clears_active(self, temp_config):
        mgr = ProfileManager()
        mgr.add(KeboolaProfile(name="a"))
        mgr.add(KeboolaProfile(name="b"))
        mgr.set_active("a")
        with patch.object(KeboolaProfile, "delete_token"):
            mgr.remove("a")
        assert "a" not in mgr.list_names()
        assert mgr.active_name == "b"

    def test_load_existing_json(self, temp_config):
        # Write a file first
        temp_config.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_config, "w") as f:
            json.dump(
                {
                    "active_profile": "loaded",
                    "profiles": {"loaded": {"name": "loaded", "engine": "snowflake"}},
                },
                f,
            )
        mgr = ProfileManager()
        assert mgr.active_name == "loaded"
        assert mgr.active is not None
        assert mgr.active.engine == "snowflake"


# =====================================================================
# Client (mock network)
# =====================================================================


class TestKeboolaClient:
    @pytest.fixture
    def mock_storage(self):
        with patch("src.hooks.python_hooks.keboola.client.KbcStorageClient") as m:
            yield m

    def test_missing_token_raises(self, mock_storage):
        from src.hooks.python_hooks.keboola.client import KeboolaClient, KeboolaError

        with pytest.raises(KeboolaError, match="token is empty"):
            KeboolaClient("https://connection.keboola.com", "")

    def test_create_transformation_builds_correct_payload(self, mock_storage):
        from src.hooks.python_hooks.keboola.client import KeboolaClient

        client = KeboolaClient("https://connection.keboola.com", "fake")

        with patch.object(client.session, "post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"id": "12345", "name": "test"},
            )
            mock_post.return_value.raise_for_status = MagicMock()

            result = client.create_transformation(
                engine="bigquery",
                name="Test",
                sql_script="SELECT 1;",
                input_table="in.c-test.raw",
                output_table="out.c-test.clean",
            )

        assert result["id"] == "12345"
        call_kwargs = mock_post.call_args
        url = call_kwargs[0][0]
        assert "google-bigquery-transformation" in url
        assert "configs" in url

    def test_wait_for_job_success(self, mock_storage):
        from src.hooks.python_hooks.keboola.client import KeboolaClient

        client = KeboolaClient("https://connection.keboola.com", "fake")

        with patch.object(client.session, "get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"id": "1", "status": "success", "isFinished": True},
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = client.wait_for_job("1", timeout=5)
        assert result["status"] == "success"

    def test_wait_for_job_timeout(self, mock_storage):
        from src.hooks.python_hooks.keboola.client import KeboolaClient

        client = KeboolaClient("https://connection.keboola.com", "fake")

        with patch.object(client.session, "get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"id": "1", "status": "running", "isFinished": False},
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = client.wait_for_job("1", timeout=2, poll=1)
        assert result["status"] == "timeout"

    def test_open_in_file_manager_uses_xdg_open(self, tmp_path):
        from src.hooks.python_hooks.keboola.client import KeboolaClient

        f = tmp_path / "test.csv"
        f.write_text("a,b\n1,2\n")

        with patch("subprocess.Popen") as mock_popen:
            KeboolaClient.open_in_file_manager(str(f))
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "xdg-open"
            assert args[1] == str(tmp_path)  # parent dir
