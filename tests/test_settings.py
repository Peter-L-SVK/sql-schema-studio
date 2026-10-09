# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Settings Tests (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Tests for Settings — JSON persistence and deep merge."""

import json

import pytest

from src.utils.settings import Settings


@pytest.fixture
def temp_settings_file(tmp_path, monkeypatch):
    """Redirect SETTINGS_FILE and CONFIG_DIR to a temp directory."""
    fake_dir = tmp_path / "config"
    fake_dir.mkdir()
    fake_file = fake_dir / "settings.json"

    monkeypatch.setattr("src.utils.settings.CONFIG_DIR", fake_dir)
    monkeypatch.setattr("src.utils.settings.SETTINGS_FILE", fake_file)

    return fake_file


class TestDefaults:
    def test_empty_settings_uses_defaults(self, temp_settings_file):
        s = Settings()
        assert s.get("editor", "font") == "Monospace 12"
        assert s.get("editor", "tab_width") == 4
        assert s.get("general", "confirm_close") is True
        assert s.get("window", "width") == 1200

    def test_get_missing_key_returns_default_arg(self, temp_settings_file):
        s = Settings()
        assert s.get("editor", "nonexistent") is None
        assert s.get("editor", "nonexistent", "fallback") == "fallback"

    def test_get_missing_section_returns_default(self, temp_settings_file):
        s = Settings()
        assert s.get("nonexistent_section", "key", "default") == "default"


class TestSetGet:
    def test_set_and_get_round_trip(self, temp_settings_file):
        s = Settings()
        s.set("editor", "font", "Fira Code 14")
        assert s.get("editor", "font") == "Fira Code 14"

    def test_set_creates_new_section(self, temp_settings_file):
        s = Settings()
        s.set("new_section", "key", "value")
        assert s.get("new_section", "key") == "value"

    def test_get_section_returns_dict(self, temp_settings_file):
        s = Settings()
        editor = s.get_section("editor")
        assert isinstance(editor, dict)
        assert "font" in editor
        assert "tab_width" in editor

    def test_get_nonexistent_section_returns_empty_dict(self, temp_settings_file):
        s = Settings()
        assert s.get_section("nonexistent") == {}


class TestPersistence:
    def test_save_writes_json(self, temp_settings_file):
        s = Settings()
        s.set("editor", "font", "Custom Font 20")
        s.save()

        assert temp_settings_file.exists()
        with open(temp_settings_file) as f:
            data = json.load(f)
        assert data["editor"]["font"] == "Custom Font 20"

    def test_load_reads_existing_json(self, temp_settings_file):
        # Write a file with custom values
        temp_settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_settings_file, "w") as f:
            json.dump(
                {
                    "editor": {"font": "Loaded Font 16", "tab_width": 8},
                    "general": {"confirm_close": False},
                },
                f,
            )

        s = Settings()
        assert s.get("editor", "font") == "Loaded Font 16"
        assert s.get("editor", "tab_width") == 8
        assert s.get("general", "confirm_close") is False
        # Defaults must still be present for keys not in the file
        assert s.get("editor", "show_line_numbers") is True

    def test_save_load_round_trip(self, temp_settings_file):
        s1 = Settings()
        s1.set("editor", "font", "Round Trip 12")
        s1.set("general", "restore_session", True)
        s1.save()

        s2 = Settings()
        assert s2.get("editor", "font") == "Round Trip 12"
        assert s2.get("general", "restore_session") is True


class TestDeepMerge:
    def test_partial_section_merge(self, temp_settings_file):
        """Only some keys in a section — the rest come from DEFAULTS."""
        temp_settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_settings_file, "w") as f:
            json.dump({"editor": {"font": "Only Font Changed"}}, f)

        s = Settings()
        assert s.get("editor", "font") == "Only Font Changed"
        # All other editor defaults must survive
        assert s.get("editor", "tab_width") == 4
        assert s.get("editor", "show_line_numbers") is True
        assert s.get("editor", "color_scheme") == "classic"

    def test_new_section_added(self, temp_settings_file):
        temp_settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_settings_file, "w") as f:
            json.dump({"custom_section": {"key": "value"}}, f)

        s = Settings()
        assert s.get("custom_section", "key") == "value"
        # Standard sections still present
        assert s.get("editor", "font") == "Monospace 12"


class TestErrorHandling:
    def test_malformed_json_falls_back_to_defaults(self, temp_settings_file):
        temp_settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_settings_file, "w") as f:
            f.write("{ this is not valid json")

        s = Settings()
        # Should not crash — falls back to defaults
        assert s.get("editor", "font") == "Monospace 12"

    def test_save_creates_directory(self, tmp_path, monkeypatch):
        """If CONFIG_DIR doesn't exist, save() should create it."""
        fake_dir = tmp_path / "does" / "not" / "exist"
        fake_file = fake_dir / "settings.json"
        monkeypatch.setattr("src.utils.settings.CONFIG_DIR", fake_dir)
        monkeypatch.setattr("src.utils.settings.SETTINGS_FILE", fake_file)

        s = Settings()
        s.set("editor", "font", "Created Dir 12")
        s.save()
        assert fake_file.exists()
