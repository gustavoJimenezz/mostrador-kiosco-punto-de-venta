"""Tests unitarios para src/infrastructure/database_launcher.py.

Todos los tests corren sin base de datos real ni proceso mysqld.exe.
subprocess.Popen y psutil se mockean completamente.
"""

from __future__ import annotations

import configparser
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.database_launcher import (
    _build_connection_url,
    _health_check,
    _is_mysqld_running,
    _read_config,
    _start_mysqld,
    launch_mariadb,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_SAMPLE_INI = """\
[database]
host     = localhost
port     = 3306
user     = root
password =
database = kiosco_pos
"""

_EXPECTED_URL = "mysql+pymysql://root:@localhost:3306/kiosco_pos"


def _make_config(ini_text: str = _SAMPLE_INI) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read_string(ini_text)
    return cfg


# ---------------------------------------------------------------------------
# _read_config
# ---------------------------------------------------------------------------


def test_read_config_returns_configparser(tmp_path: Path) -> None:
    ini_file = tmp_path / "database.ini"
    ini_file.write_text(_SAMPLE_INI)

    cfg = _read_config(ini_file)

    assert cfg.getint("database", "port") == 3306
    assert cfg.get("database", "host") == "localhost"


def test_read_config_missing_file_returns_empty(tmp_path: Path) -> None:
    cfg = _read_config(tmp_path / "inexistente.ini")

    assert "database" not in cfg


# ---------------------------------------------------------------------------
# _build_connection_url
# ---------------------------------------------------------------------------


def test_build_connection_url_standard() -> None:
    cfg = _make_config()
    assert _build_connection_url(cfg) == _EXPECTED_URL


def test_build_connection_url_custom_port() -> None:
    cfg = _make_config("[database]\nhost=127.0.0.1\nport=3307\nuser=pos\npassword=secret\ndatabase=pos_db\n")
    url = _build_connection_url(cfg)
    assert url == "mysql+pymysql://pos:secret@127.0.0.1:3307/pos_db"


def test_build_connection_url_defaults_when_section_missing() -> None:
    cfg = configparser.ConfigParser()  # sin sección [database]
    url = _build_connection_url(cfg)
    assert url == "mysql+pymysql://root:@localhost:3306/kiosco_pos"


# ---------------------------------------------------------------------------
# _is_mysqld_running
# ---------------------------------------------------------------------------


def test_is_mysqld_running_returns_true_when_process_found() -> None:
    mock_proc = MagicMock()
    mock_proc.info = {"name": "mysqld.exe"}

    with patch("src.infrastructure.database_launcher.psutil.process_iter", return_value=[mock_proc]):
        assert _is_mysqld_running() is True


def test_is_mysqld_running_returns_false_when_not_found() -> None:
    mock_proc = MagicMock()
    mock_proc.info = {"name": "python.exe"}

    with patch("src.infrastructure.database_launcher.psutil.process_iter", return_value=[mock_proc]):
        assert _is_mysqld_running() is False


def test_is_mysqld_running_ignores_access_denied() -> None:
    import psutil

    bad_proc = MagicMock()
    # info es un MagicMock cuyo __getitem__ lanza AccessDenied
    bad_proc.info = MagicMock()
    bad_proc.info.__getitem__ = MagicMock(side_effect=psutil.AccessDenied(pid=99))

    with patch("src.infrastructure.database_launcher.psutil.process_iter", return_value=[bad_proc]):
        assert _is_mysqld_running() is False


# ---------------------------------------------------------------------------
# _start_mysqld
# ---------------------------------------------------------------------------


def test_start_mysqld_calls_popen_with_correct_args(tmp_path: Path) -> None:
    mysqld_bin = tmp_path / "mysqld.exe"
    mysqld_bin.touch()

    with patch("src.infrastructure.database_launcher.subprocess.Popen") as mock_popen:
        _start_mysqld(mysqld_bin, port=3306)

    args_called = mock_popen.call_args[0][0]
    assert str(mysqld_bin) in args_called
    assert "--port=3306" in args_called
    assert "--console" in args_called


def test_start_mysqld_uses_create_no_window_flag(tmp_path: Path) -> None:
    mysqld_bin = tmp_path / "mysqld.exe"
    mysqld_bin.touch()

    import subprocess as _subprocess

    with patch("src.infrastructure.database_launcher.subprocess.Popen") as mock_popen:
        _start_mysqld(mysqld_bin, port=3306)

    kwargs = mock_popen.call_args[1]
    expected_flag = getattr(_subprocess, "CREATE_NO_WINDOW", 0)
    assert kwargs.get("creationflags") == expected_flag


# ---------------------------------------------------------------------------
# _health_check
# ---------------------------------------------------------------------------


def test_health_check_returns_true_on_first_success() -> None:
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with patch("src.infrastructure.database_launcher.sqlalchemy.create_engine", return_value=mock_engine):
        result = _health_check(_EXPECTED_URL, retries=3, delay=0.0)

    assert result is True
    assert mock_engine.connect.call_count == 1


def test_health_check_retries_and_returns_false_on_all_failures() -> None:
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception("Connection refused")

    with patch("src.infrastructure.database_launcher.sqlalchemy.create_engine", return_value=mock_engine):
        with patch("src.infrastructure.database_launcher.time.sleep"):
            result = _health_check(_EXPECTED_URL, retries=3, delay=0.0)

    assert result is False
    assert mock_engine.connect.call_count == 3


def test_health_check_succeeds_on_second_attempt() -> None:
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)

    mock_engine = MagicMock()
    mock_engine.connect.side_effect = [Exception("timeout"), mock_conn]

    with patch("src.infrastructure.database_launcher.sqlalchemy.create_engine", return_value=mock_engine):
        with patch("src.infrastructure.database_launcher.time.sleep"):
            result = _health_check(_EXPECTED_URL, retries=3, delay=0.0)

    assert result is True
    assert mock_engine.connect.call_count == 2


# ---------------------------------------------------------------------------
# launch_mariadb (integración de todas las partes)
# ---------------------------------------------------------------------------


def test_launch_mariadb_starts_mysqld_when_not_running(tmp_path: Path) -> None:
    """Si mysqld.exe existe y no está corriendo, debe iniciarlo."""
    ini_file = tmp_path / "database.ini"
    ini_file.write_text(_SAMPLE_INI)
    vendor_path = tmp_path / "mariadb"
    mysqld_bin = vendor_path / "bin" / "mysqld.exe"
    mysqld_bin.parent.mkdir(parents=True)
    mysqld_bin.touch()

    with (
        patch("src.infrastructure.database_launcher._is_mysqld_running", return_value=False),
        patch("src.infrastructure.database_launcher._start_mysqld") as mock_start,
        patch("src.infrastructure.database_launcher._health_check", return_value=True),
    ):
        result = launch_mariadb(vendor_path, ini_file, connection_url=_EXPECTED_URL)

    assert result is True
    mock_start.assert_called_once()


def test_launch_mariadb_skips_start_when_already_running(tmp_path: Path) -> None:
    ini_file = tmp_path / "database.ini"
    ini_file.write_text(_SAMPLE_INI)
    vendor_path = tmp_path / "mariadb"
    mysqld_bin = vendor_path / "bin" / "mysqld.exe"
    mysqld_bin.parent.mkdir(parents=True)
    mysqld_bin.touch()

    with (
        patch("src.infrastructure.database_launcher._is_mysqld_running", return_value=True),
        patch("src.infrastructure.database_launcher._start_mysqld") as mock_start,
        patch("src.infrastructure.database_launcher._health_check", return_value=True),
    ):
        launch_mariadb(vendor_path, ini_file, connection_url=_EXPECTED_URL)

    mock_start.assert_not_called()


def test_launch_mariadb_skips_start_when_binary_missing(tmp_path: Path) -> None:
    """En Linux/desarrollo, sin mysqld.exe debe ir directo al health check."""
    ini_file = tmp_path / "database.ini"
    ini_file.write_text(_SAMPLE_INI)
    vendor_path = tmp_path / "mariadb"  # sin crear mysqld_bin

    with (
        patch("src.infrastructure.database_launcher._start_mysqld") as mock_start,
        patch("src.infrastructure.database_launcher._health_check", return_value=True),
    ):
        result = launch_mariadb(vendor_path, ini_file, connection_url=_EXPECTED_URL)

    assert result is True
    mock_start.assert_not_called()


def test_launch_mariadb_returns_false_when_health_check_fails(tmp_path: Path) -> None:
    ini_file = tmp_path / "database.ini"
    ini_file.write_text(_SAMPLE_INI)
    vendor_path = tmp_path / "mariadb"

    with patch("src.infrastructure.database_launcher._health_check", return_value=False):
        result = launch_mariadb(vendor_path, ini_file, connection_url=_EXPECTED_URL)

    assert result is False


def test_launch_mariadb_builds_url_from_ini_when_not_provided(tmp_path: Path) -> None:
    ini_file = tmp_path / "database.ini"
    ini_file.write_text(_SAMPLE_INI)
    vendor_path = tmp_path / "mariadb"

    with patch("src.infrastructure.database_launcher._health_check", return_value=True) as mock_hc:
        launch_mariadb(vendor_path, ini_file)

    called_url = mock_hc.call_args[0][0]
    assert called_url == _EXPECTED_URL
