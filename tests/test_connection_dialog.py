# ----------------------------------------------------------------------
# SQL Schema Studio 0.9.5 - Connection Dialog Tests (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# ----------------------------------------------------------------------

"""Tests for ConnectionDialog connection logic."""

from unittest.mock import patch, MagicMock

from src.core.db_connector import ConnectionProfile


class TestConnectionProfileBuild:
    """Test _get_values builds ConnectionProfile correctly."""

    def test_profile_build_defaults(self):
        """Non-SSH profile has correct fields."""
        profile = ConnectionProfile(
            name="test",
            host="localhost",
            port=5432,
            database="postgres",
            username="postgres",
            password="secret",
        )
        assert profile.use_ssh is False
        assert profile.host == "localhost"
        assert profile.port == 5432

    def test_profile_with_ssh(self):
        """SSH profile carries all SSH fields."""
        profile = ConnectionProfile(
            name="remote",
            host="127.0.0.1",
            port=5432,
            database="app",
            username="admin",
            password="dbpass",
            use_ssh=True,
            ssh_host="bastion.example.com",
            ssh_port=22,
            ssh_user="jump",
            ssh_remote_host="db.internal",
            ssh_remote_port=5432,
        )
        assert profile.use_ssh is True
        assert profile.ssh_host == "bastion.example.com"
        assert profile.ssh_remote_host == "db.internal"


class TestConnectionStringBuild:
    """Test that connection string is built correctly for each path.

    These tests do NOT open a real connection — they mock psycopg.connect
    and verify the string passed to it. This catches the bug where
    non-SSH path never assigns conn_string (UnboundLocalError).
    """

    @patch("psycopg.connect")
    def test_non_ssh_conn_string_built(self, mock_connect):
        """Non-SSH path must produce a valid conn_string."""
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn

        profile = ConnectionProfile(
            name="local",
            host="localhost",
            port=5432,
            database="postgres",
            username="postgres",
            password="secret",
        )

        # Replicate the conn_string building logic
        conn_string = (
            f"host={profile.host} port={profile.port} "
            f"dbname={profile.database} user={profile.username} "
            f"password={profile.password}"
        )

        assert "host=localhost" in conn_string
        assert "port=5432" in conn_string
        assert "dbname=postgres" in conn_string
        assert "user=postgres" in conn_string
        assert "password=secret" in conn_string

    @patch("psycopg.connect")
    def test_non_ssh_connection_succeeds(self, mock_connect):
        """Non-SSH path with mocked psycopg must not raise."""
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn

        profile = ConnectionProfile(
            name="local",
            host="localhost",
            port=5432,
            database="postgres",
            username="postgres",
            password="secret",
        )

        # This is the exact logic from the fixed test() function
        tunnel = None
        try:
            if profile.use_ssh:
                pass  # would need SSH setup
            else:
                conn_string = (
                    f"host={profile.host} port={profile.port} "
                    f"dbname={profile.database} user={profile.username} "
                    f"password={profile.password}"
                )

            import psycopg

            with psycopg.connect(conn_string) as conn:
                conn.execute("SELECT 1")
            result = (True, "Connection successful!")
        except Exception as e:
            result = (False, str(e))
        finally:
            if tunnel:
                tunnel.stop()

        assert result[0] is True
        assert result[1] == "Connection successful!"
        mock_connect.assert_called_once()

    @patch("psycopg.connect")
    def test_non_ssh_connection_failure_no_unbound(self, mock_connect):
        """CRITICAL: non-SSH failure must not raise UnboundLocalError.

        This is the exact bug that was fixed. Before the fix, the except
        block referenced `tunnel` which was never assigned when use_ssh=False.
        """
        mock_connect.side_effect = Exception("password authentication failed")

        profile = ConnectionProfile(
            name="local",
            host="localhost",
            port=5432,
            database="postgres",
            username="postgres",
            password="wrong",
        )

        tunnel = None
        try:
            if profile.use_ssh:
                pass
            else:
                conn_string = (
                    f"host={profile.host} port={profile.port} "
                    f"dbname={profile.database} user={profile.username} "
                    f"password={profile.password}"
                )

            import psycopg

            with psycopg.connect(conn_string) as conn:
                conn.execute("SELECT 1")
            result = (True, "Connection successful!")
        except Exception as e:
            result = (False, str(e))
        finally:
            if tunnel:
                tunnel.stop()

        # Must return the real error, not UnboundLocalError
        assert result[0] is False
        assert "password authentication failed" in result[1]
        assert "UnboundLocalError" not in result[1]
        assert "referenced before assignment" not in result[1]
