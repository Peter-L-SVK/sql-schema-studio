# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - SSH Tunnel (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""SSH tunnel for remote PostgreSQL connections via paramiko."""

import os
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import paramiko
from paramiko import SSHClient, AutoAddPolicy

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SSHTunnelConfig:
    """Configuration for an SSH tunnel."""
    enabled: bool = False
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_password: str = field(default="", repr=False)
    ssh_key_path: str = ""
    remote_host: str = "localhost"
    remote_port: int = 5432
    local_bind_port: int = 0


class SSHTunnel:
    """Manages an SSH tunnel for remote database connections."""

    def __init__(self, config: SSHTunnelConfig):
        self.config = config
        self._client: Optional[SSHClient] = None
        self._local_port: int = 0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> tuple[bool, Optional[int], Optional[str]]:
        """Start SSH tunnel using direct-tcpip channel (local forwarding)."""
        if not self.config.enabled:
            return True, None, None

        try:
            self._client = SSHClient()
            self._client.set_missing_host_key_policy(AutoAddPolicy())

            connect_kwargs = {
                "hostname": self.config.ssh_host,
                "port": self.config.ssh_port,
                "username": self.config.ssh_user,
                "timeout": 10,
            }

            if self.config.ssh_key_path:
                key_path = os.path.expanduser(self.config.ssh_key_path)
                try:
                    key = paramiko.RSAKey.from_private_key_file(key_path)
                except paramiko.SSHException:
                    try:
                        key = paramiko.Ed25519Key.from_private_key_file(key_path)
                    except paramiko.SSHException:
                        key = paramiko.ECDSAKey.from_private_key_file(key_path)
                connect_kwargs["pkey"] = key
                logger.info(f"Using SSH key: {key_path}")
            elif self.config.ssh_password:
                connect_kwargs["password"] = self.config.ssh_password
                logger.info("Using SSH password authentication")
            else:
                connect_kwargs["allow_agent"] = True
                connect_kwargs["look_for_keys"] = True
                logger.info("Trying SSH agent / default keys")

            self._client.connect(**connect_kwargs)
            logger.info(f"SSH connected to {self.config.ssh_host}:{self.config.ssh_port}")

            transport = self._client.get_transport()
            if not transport:
                raise RuntimeError("Failed to get SSH transport")

            transport.set_keepalive(30)

            if self.config.local_bind_port == 0:
                sock = socket.socket()
                sock.bind(("", 0))
                self._local_port = sock.getsockname()[1]
                sock.close()
            else:
                self._local_port = self.config.local_bind_port

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._forward_loop, daemon=True)
            self._thread.start()

            # Give the socket time to start listening
            time.sleep(0.1)

            logger.info(
                f"SSH tunnel established: localhost:{self._local_port} -> "
                f"{self.config.remote_host}:{self.config.remote_port}"
            )
            return True, self._local_port, None

        except paramiko.AuthenticationException as e:
            logger.error(f"SSH authentication failed: {e}")
            return False, None, f"Authentication failed: {e}"
        except Exception as e:
            logger.error(f"SSH tunnel failed: {e}")
            return False, None, f"SSH tunnel error: {e}"

    def _forward_loop(self):
        """Main loop for local port forwarding using direct-tcpip channel."""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("127.0.0.1", self._local_port))
            server_socket.listen(100)

            while not self._stop_event.is_set():
                server_socket.settimeout(1.0)
                try:
                    client_sock, addr = server_socket.accept()
                    t = threading.Thread(
                        target=self._handle_connection,
                        args=(client_sock,),
                        daemon=True,
                    )
                    t.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if not self._stop_event.is_set():
                        logger.error(f"Accept error: {e}")
                    break

            server_socket.close()
        except Exception as e:
            logger.error(f"Forward loop error: {e}")

    def _handle_connection(self, client_sock):
        """Handle a single local connection by creating an SSH channel."""
        try:
            transport = self._client.get_transport()
            if not transport:
                client_sock.close()
                return

            dest_addr = (self.config.remote_host, self.config.remote_port)
            source_addr = ("127.0.0.1", self._local_port)

            channel = transport.open_channel("direct-tcpip", dest_addr, source_addr)
            if not channel:
                logger.error("Failed to open direct-tcpip channel")
                client_sock.close()
                return

            threading.Thread(
                target=self._forward_data,
                args=(client_sock, channel),
                daemon=True,
            ).start()
            threading.Thread(
                target=self._forward_data,
                args=(channel, client_sock),
                daemon=True,
            ).start()

        except Exception as e:
            logger.error(f"Handle connection error: {e}")
            client_sock.close()

    def _forward_data(self, src, dst):
        """Forward data from src to dst."""
        try:
            while not self._stop_event.is_set():
                data = src.recv(1024)
                if not data:
                    break
                dst.send(data)
        except Exception:
            pass
        finally:
            try:
                src.close()
                dst.close()
            except Exception:
                pass

    def stop(self):
        """Stop the SSH tunnel."""
        logger.info("Stopping SSH tunnel...")
        self._stop_event.set()
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        logger.info("SSH tunnel stopped")

    @property
    def local_port(self) -> int:
        return self._local_port

    @property
    def is_active(self) -> bool:
        return self._client is not None


def get_postgres_conn_string_with_ssh(
    ssh_config: SSHTunnelConfig,
    db_config: dict,
) -> tuple[str, Optional[SSHTunnel], Optional[str]]:
    """Build a PostgreSQL connection string, optionally via SSH tunnel.

    Returns (conn_string, tunnel, error_message).
    """
    if not ssh_config.enabled:
        conn_string = (
            f"host={db_config['host']} port={db_config['port']} "
            f"dbname={db_config['database']} user={db_config['username']} "
            f"password={db_config.get('password', '')}"
        )
        return conn_string, None, None

    tunnel = SSHTunnel(ssh_config)
    success, local_port, error = tunnel.start()
    if not success:
        return "", None, error

    conn_string = (
        f"host=127.0.0.1 port={local_port} "
        f"dbname={db_config['database']} user={db_config['username']} "
        f"password={db_config.get('password', '')}"
    )
    return conn_string, tunnel, None
