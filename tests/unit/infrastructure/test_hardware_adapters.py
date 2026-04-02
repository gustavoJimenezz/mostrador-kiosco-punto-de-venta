"""Tests unitarios para src/infrastructure/hardware/.

Verifica los adaptadores de impresora (CUPS y Null) y la fábrica
cross-platform ``get_printer_adapter()``.

Todos los tests corren sin CUPS ni hardware real: subprocess se mockea.
"""

from __future__ import annotations

import subprocess
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.domain.models.sale import PaymentMethod, Sale, SaleItem
from src.domain.ports.printer_base import PrinterBase
from src.infrastructure.hardware.cups_printer_adapter import CupsPrinterAdapter
from src.infrastructure.hardware.null_printer_adapter import NullPrinterAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sale(with_items: bool = True) -> Sale:
    """Construye una Sale de prueba con un ítem o con total_snapshot."""
    if with_items:
        item = SaleItem(product_id=42, quantity=3, price_at_sale=Decimal("150.00"))
        return Sale(payment_method=PaymentMethod.CASH, items=[item])
    # Simula carga desde historial sin ítems
    return Sale(
        payment_method=PaymentMethod.TRANSFER,
        items=[],
        total_snapshot=Decimal("500.00"),
    )


# ---------------------------------------------------------------------------
# NullPrinterAdapter
# ---------------------------------------------------------------------------

class TestNullPrinterAdapter:
    def test_implements_printer_base_protocol(self):
        assert isinstance(NullPrinterAdapter(), PrinterBase)

    def test_print_ticket_outputs_to_stdout(self, capsys):
        sale = _make_sale()
        NullPrinterAdapter().print_ticket(sale)
        captured = capsys.readouterr()
        assert "[NullPrinter]" in captured.out
        assert str(sale.id) in captured.out

    def test_print_ticket_shows_total(self, capsys):
        sale = _make_sale()
        NullPrinterAdapter().print_ticket(sale)
        captured = capsys.readouterr()
        assert "450.00" in captured.out  # 3 × 150.00

    def test_print_ticket_works_with_snapshot_sale(self, capsys):
        sale = _make_sale(with_items=False)
        NullPrinterAdapter().print_ticket(sale)
        captured = capsys.readouterr()
        assert "[NullPrinter]" in captured.out


# ---------------------------------------------------------------------------
# get_printer_adapter() — detección de plataforma
# ---------------------------------------------------------------------------

class TestGetPrinterAdapter:
    def test_linux_returns_cups_adapter(self):
        with patch.object(sys, "platform", "linux"):
            from src.infrastructure.hardware import get_printer_adapter
            with patch(
                "src.infrastructure.hardware.cups_printer_adapter.CupsPrinterAdapter._resolve_printer_name",
                return_value="Ticketera",
            ):
                adapter = get_printer_adapter()
        assert isinstance(adapter, CupsPrinterAdapter)

    def test_win32_returns_null_adapter(self):
        with patch.object(sys, "platform", "win32"):
            from src.infrastructure.hardware import get_printer_adapter
            adapter = get_printer_adapter()
        assert isinstance(adapter, NullPrinterAdapter)

    def test_other_platform_returns_null_adapter(self):
        with patch.object(sys, "platform", "darwin"):
            from src.infrastructure.hardware import get_printer_adapter
            adapter = get_printer_adapter()
        assert isinstance(adapter, NullPrinterAdapter)

    def test_returned_adapter_implements_printer_base(self):
        with patch.object(sys, "platform", "win32"):
            from src.infrastructure.hardware import get_printer_adapter
            adapter = get_printer_adapter()
        assert isinstance(adapter, PrinterBase)


# ---------------------------------------------------------------------------
# CupsPrinterAdapter — resolución de impresora
# ---------------------------------------------------------------------------

class TestCupsPrinterAdapterResolution:
    def test_uses_env_variable_when_set(self, monkeypatch):
        monkeypatch.setenv("CUPS_PRINTER", "MiTicketera")
        adapter = CupsPrinterAdapter()
        assert adapter._printer_name == "MiTicketera"

    def test_autodetects_first_printer_from_lpstat(self, monkeypatch):
        monkeypatch.delenv("CUPS_PRINTER", raising=False)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"Ticketera\nOtra_Impresora\n"
        with patch("subprocess.run", return_value=mock_result):
            adapter = CupsPrinterAdapter()
        assert adapter._printer_name == "Ticketera"

    def test_returns_none_when_lpstat_not_found(self, monkeypatch):
        monkeypatch.delenv("CUPS_PRINTER", raising=False)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            adapter = CupsPrinterAdapter()
        assert adapter._printer_name is None

    def test_returns_none_when_lpstat_returns_empty(self, monkeypatch):
        monkeypatch.delenv("CUPS_PRINTER", raising=False)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b""
        with patch("subprocess.run", return_value=mock_result):
            adapter = CupsPrinterAdapter()
        assert adapter._printer_name is None

    def test_returns_none_when_lpstat_fails(self, monkeypatch):
        monkeypatch.delenv("CUPS_PRINTER", raising=False)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        with patch("subprocess.run", return_value=mock_result):
            adapter = CupsPrinterAdapter()
        assert adapter._printer_name is None


# ---------------------------------------------------------------------------
# CupsPrinterAdapter — print_ticket
# ---------------------------------------------------------------------------

class TestCupsPrinterAdapterPrintTicket:
    def _adapter_with_printer(self, monkeypatch) -> CupsPrinterAdapter:
        monkeypatch.setenv("CUPS_PRINTER", "Ticketera")
        return CupsPrinterAdapter()

    def _adapter_without_printer(self, monkeypatch) -> CupsPrinterAdapter:
        monkeypatch.delenv("CUPS_PRINTER", raising=False)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            return CupsPrinterAdapter()

    def test_calls_lp_with_correct_args(self, monkeypatch):
        adapter = self._adapter_with_printer(monkeypatch)
        sale = _make_sale()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            adapter.print_ticket(sale)
        args = mock_run.call_args[0][0]
        assert args[0] == "lp"
        assert args[1] == "-d"
        assert args[2] == "Ticketera"
        assert args[3] == "-"

    def test_sends_ticket_bytes_to_stdin(self, monkeypatch):
        adapter = self._adapter_with_printer(monkeypatch)
        sale = _make_sale()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            adapter.print_ticket(sale)
        sent_bytes = mock_run.call_args[1]["input"]
        assert isinstance(sent_bytes, bytes)
        assert b"KIOSCO POS" in sent_bytes
        assert b"EFECTIVO" in sent_bytes

    def test_does_not_raise_when_lp_returns_error(self, monkeypatch):
        adapter = self._adapter_with_printer(monkeypatch)
        sale = _make_sale()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = b"cups error: printer not found"
        with patch("subprocess.run", return_value=mock_result):
            adapter.print_ticket(sale)  # no debe lanzar excepción

    def test_does_not_raise_when_lp_not_installed(self, monkeypatch):
        adapter = self._adapter_with_printer(monkeypatch)
        sale = _make_sale()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            adapter.print_ticket(sale)  # no debe lanzar excepción

    def test_does_not_raise_on_timeout(self, monkeypatch):
        adapter = self._adapter_with_printer(monkeypatch)
        sale = _make_sale()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("lp", 15)):
            adapter.print_ticket(sale)  # no debe lanzar excepción

    def test_skips_lp_call_when_no_printer(self, monkeypatch):
        adapter = self._adapter_without_printer(monkeypatch)
        sale = _make_sale()
        with patch("subprocess.run") as mock_run:
            adapter.print_ticket(sale)
        mock_run.assert_not_called()

    def test_ticket_includes_sale_items(self, monkeypatch):
        adapter = self._adapter_with_printer(monkeypatch)
        sale = _make_sale(with_items=True)
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            adapter.print_ticket(sale)
        ticket_text = mock_run.call_args[1]["input"].decode("utf-8")
        assert "#42" in ticket_text  # product_id del ítem
        assert "150,00" in ticket_text or "150.00" in ticket_text

    def test_ticket_works_with_snapshot_sale_no_items(self, monkeypatch):
        adapter = self._adapter_with_printer(monkeypatch)
        sale = _make_sale(with_items=False)
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            adapter.print_ticket(sale)  # no debe fallar con items vacío
        ticket_text = mock_run.call_args[1]["input"].decode("utf-8")
        assert "500,00" in ticket_text or "500.00" in ticket_text
