"""Diálogo de informe detallado previo al cierre de caja.

Muestra un resumen completo del período antes de que el cajero confirme
el arqueo. Organizado en tres secciones:

1. Rentabilidad (foco principal): ganancia bruta estimada y margen.
2. Conciliación de efectivo: saldo teórico vs. contado, diferencia.
3. Detalle de ventas por método de pago y movimientos manuales.

El cierre de caja solo se ejecuta si el usuario presiona "Confirmar y cerrar".
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.models.cash_close import CashClose
from src.domain.models.cash_movement import CashMovement


class CashCloseReportDialog(QDialog):
    """Diálogo modal con el informe de cierre de caja.

    Permite al cajero revisar todos los datos del período antes de
    confirmar el cierre. El diálogo retorna ``QDialog.DialogCode.Accepted``
    solo si el usuario presiona "Confirmar y cerrar caja".

    Args:
        cash_close: Arqueo actualmente abierto.
        report_data: Diccionario con ``closing_amount``, ``movements``,
            ``sales_totals`` y ``profit`` (ver ``LoadCashReportWorker``).
        parent: Widget padre (opcional).
    """

    def __init__(
        self,
        cash_close: CashClose,
        report_data: dict,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Informe de Cierre de Caja")
        self.setModal(True)
        self.resize(620, 760)
        self.setMinimumSize(560, 600)

        self._cash_close = cash_close
        self._report_data = report_data

        from src.infrastructure.ui.theme import setup_rounded_modal
        self._container = setup_rounded_modal(self)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construye el layout completo del informe."""
        root = QVBoxLayout(self._container)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Título
        title = QLabel("Informe de Cierre de Caja")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        # Período
        self._add_period_label(root)
        root.addWidget(self._make_separator())

        # Área con scroll para el contenido
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(14)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Rentabilidad (FOCO PRINCIPAL)
        self._build_profit_section(content_layout)
        content_layout.addWidget(self._make_separator())

        # 2. Ventas por método de pago
        self._build_sales_section(content_layout)
        content_layout.addWidget(self._make_separator())

        # 3. Conciliación de efectivo
        self._build_cash_reconciliation_section(content_layout)
        content_layout.addWidget(self._make_separator())

        # 4. Movimientos manuales
        self._build_movements_section(content_layout)

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        root.addWidget(scroll, stretch=1)

        # Botones
        root.addWidget(self._make_separator())
        self._build_buttons(root)

    def _add_period_label(self, layout: QVBoxLayout) -> None:
        """Agrega la etiqueta con el período de apertura y hora de cierre."""
        from datetime import datetime

        from src.infrastructure.ui.theme import TEXT_SECONDARY_COLOR

        apertura = self._cash_close.opened_at.strftime("%d/%m/%Y  %H:%M")
        cierre = datetime.now().strftime("%d/%m/%Y  %H:%M")
        lbl = QLabel(f"Período:  {apertura}  →  {cierre}")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY_COLOR}; font-size: 11px;")
        layout.addWidget(lbl)

    def _build_profit_section(self, layout: QVBoxLayout) -> None:
        """Sección de rentabilidad — foco visual principal."""
        profit = self._report_data.get("profit", {})
        revenue: Decimal = profit.get("total_revenue", Decimal("0"))
        cost: Decimal = profit.get("total_cost_estimate", Decimal("0"))
        gross_profit: Decimal = profit.get("gross_profit", Decimal("0"))
        margin: Decimal = profit.get("margin_percent", Decimal("0"))
        count: int = profit.get("total_sales_count", 0)

        section_lbl = self._make_section_title(
            "Rentabilidad del Período  (ganancia bruta estimada)"
        )
        layout.addWidget(section_lbl)

        from src.infrastructure.ui.theme import DANGER_COLOR, SUCCESS_COLOR

        # Tarjeta destacada de ganancia
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card_color = SUCCESS_COLOR if gross_profit >= Decimal("0") else DANGER_COLOR
        card.setStyleSheet(
            f"background-color: {card_color}10; border: 2px solid {card_color}; border-radius: 8px;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)

        profit_big = QLabel(f"${gross_profit:,.2f}")
        profit_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        profit_font = QFont()
        profit_font.setPointSize(22)
        profit_font.setBold(True)
        profit_big.setFont(profit_font)
        profit_big.setStyleSheet(f"color: {card_color};")
        card_layout.addWidget(profit_big)

        sub = QLabel(f"Ganancia Bruta Estimada  —  Margen promedio: {margin:.1f}%")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {card_color}; font-size: 11px;")
        card_layout.addWidget(sub)
        layout.addWidget(card)

        # Tabla de detalle
        from src.infrastructure.ui.theme import TEXT_HINT_COLOR

        rows = [
            ("Total Facturado (ventas)", f"${revenue:,.2f}", None),
            ("(-) Costo de Mercadería Vendida *", f"${cost:,.2f}", None),
            ("(=) Ganancia Bruta Estimada", f"${gross_profit:,.2f}", card_color),
            ("Margen promedio", f"{margin:.1f}%", card_color),
            ("Cantidad de ventas del período", str(count), None),
        ]
        layout.addWidget(self._make_table(rows))

        note = QLabel("* Costo calculado al valor actual de cada producto (estimación).")
        note.setStyleSheet(f"color: {TEXT_HINT_COLOR}; font-size: 10px;")
        layout.addWidget(note)

    def _build_sales_section(self, layout: QVBoxLayout) -> None:
        """Sección de ventas desglosadas por método de pago."""
        layout.addWidget(self._make_section_title("Ventas del Período por Método de Pago"))
        totals = self._report_data.get("sales_totals", {})
        cash = totals.get("EFECTIVO", Decimal("0"))
        debit = totals.get("DEBITO", Decimal("0"))
        transfer = totals.get("TRANSFERENCIA", Decimal("0"))
        total = cash + debit + transfer

        from src.infrastructure.ui.theme import INFO_COLOR

        rows = [
            ("Efectivo", f"${cash:,.2f}", None),
            ("Débito", f"${debit:,.2f}", None),
            ("Transferencia", f"${transfer:,.2f}", None),
            ("TOTAL VENTAS", f"${total:,.2f}", INFO_COLOR),
        ]
        layout.addWidget(self._make_table(rows, bold_last=True))

    def _build_cash_reconciliation_section(self, layout: QVBoxLayout) -> None:
        """Sección de conciliación de efectivo físico."""
        layout.addWidget(self._make_section_title("Conciliación de Efectivo"))

        totals = self._report_data.get("sales_totals", {})
        cash_sales = totals.get("EFECTIVO", Decimal("0"))
        movements: list[CashMovement] = self._report_data.get("movements", [])
        net_movements = sum((m.amount for m in movements), Decimal("0"))
        closing_amount: Decimal = self._report_data.get("closing_amount", Decimal("0"))

        opening = self._cash_close.opening_amount
        theoretical_cash = opening + cash_sales + net_movements
        difference = closing_amount - theoretical_cash

        from src.infrastructure.ui.theme import DANGER_COLOR, INFO_COLOR, SUCCESS_COLOR

        if difference >= Decimal("0"):
            diff_str = f"${difference:,.2f}  (Sobrante)"
            diff_color = SUCCESS_COLOR
        else:
            diff_str = f"${abs(difference):,.2f}  (Faltante)"
            diff_color = DANGER_COLOR

        mov_sign = "+" if net_movements >= Decimal("0") else ""
        rows = [
            ("Monto Inicial (Apertura)", f"${opening:,.2f}", None),
            ("(+) Ventas en Efectivo", f"${cash_sales:,.2f}", None),
            (
                "(+/−) Movimientos Manuales (neto)",
                f"{mov_sign}${net_movements:,.2f}",
                None,
            ),
            ("(=) Saldo Teórico en Caja", f"${theoretical_cash:,.2f}", INFO_COLOR),
            ("(×) Monto Contado (Real)", f"${closing_amount:,.2f}", None),
            ("Diferencia de Caja", diff_str, diff_color),
        ]
        layout.addWidget(self._make_table(rows))

    def _build_movements_section(self, layout: QVBoxLayout) -> None:
        """Sección de tabla de movimientos manuales del período."""
        layout.addWidget(self._make_section_title("Movimientos Manuales del Período"))
        movements: list[CashMovement] = self._report_data.get("movements", [])

        if not movements:
            from src.infrastructure.ui.theme import TEXT_HINT_COLOR

            lbl = QLabel("No se registraron movimientos manuales en este período.")
            lbl.setStyleSheet(f"color: {TEXT_HINT_COLOR}; font-style: italic;")
            layout.addWidget(lbl)
            return

        table = QTableWidget(len(movements), 3)
        table.setHorizontalHeaderLabels(["Hora", "Descripción", "Monto"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setFixedHeight(min(140, 34 + len(movements) * 30))
        table.verticalHeader().setVisible(False)

        from src.infrastructure.ui.theme import DANGER_COLOR, SUCCESS_COLOR

        for i, mov in enumerate(movements):
            hora = mov.created_at.strftime("%H:%M")
            signo = "+" if mov.is_income else "−"
            monto_str = f"{signo}${abs(mov.amount):,.2f}"
            color = QColor(SUCCESS_COLOR) if mov.is_income else QColor(DANGER_COLOR)

            table.setItem(i, 0, QTableWidgetItem(hora))
            table.setItem(i, 1, QTableWidgetItem(mov.description))
            monto_item = QTableWidgetItem(monto_str)
            monto_item.setForeground(color)
            table.setItem(i, 2, monto_item)

        layout.addWidget(table)

        # Subtotal movimientos
        net = sum((m.amount for m in movements), Decimal("0"))
        sign = "+" if net >= Decimal("0") else ""
        from src.infrastructure.ui.theme import TEXT_PRIMARY_COLOR

        sub = QLabel(f"Neto movimientos manuales: {sign}${net:,.2f}")
        sub.setStyleSheet(f"color: {TEXT_PRIMARY_COLOR}; font-size: 11px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(sub)

    def _build_buttons(self, layout: QVBoxLayout) -> None:
        """Agrega los botones de acción al pie del diálogo."""
        from src.infrastructure.ui.theme import get_btn_primary_stylesheet, get_btn_secondary_stylesheet

        row = QHBoxLayout()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(get_btn_secondary_stylesheet())
        btn_cancel.clicked.connect(self.reject)

        btn_confirm = QPushButton("Confirmar y cerrar caja")
        btn_confirm.setStyleSheet(get_btn_primary_stylesheet())
        btn_confirm.clicked.connect(self.accept)
        btn_confirm.setDefault(True)

        row.addWidget(btn_cancel)
        row.addStretch()
        row.addWidget(btn_confirm)
        layout.addLayout(row)

    # ------------------------------------------------------------------
    # Helpers de widgets reutilizables
    # ------------------------------------------------------------------

    @staticmethod
    def _make_section_title(text: str) -> QLabel:
        """Crea un label de título de sección."""
        from src.infrastructure.ui.theme import TEXT_PRIMARY_COLOR

        lbl = QLabel(text)
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        lbl.setFont(font)
        lbl.setStyleSheet(f"color: {TEXT_PRIMARY_COLOR};")
        return lbl

    @staticmethod
    def _make_separator() -> QFrame:
        """Crea una línea horizontal separadora."""
        from src.infrastructure.ui.theme import PALETTE

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {PALETTE.border};")
        return line

    @staticmethod
    def _make_table(
        rows: list[tuple[str, str, Optional[str]]],
        bold_last: bool = False,
    ) -> QTableWidget:
        """Crea una tabla de dos columnas (Concepto · Monto) sin encabezado visible.

        Args:
            rows: Lista de (concepto, monto, color_hex_o_None).
            bold_last: Si True, pone en negrita la última fila.

        Returns:
            QTableWidget configurado como tabla de solo lectura.
        """
        table = QTableWidget(len(rows), 2)
        table.horizontalHeader().setVisible(False)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setShowGrid(False)
        table.setFrameShape(QFrame.Shape.NoFrame)

        # Columna "Concepto" ocupa 60%, "Monto" el resto
        table.setColumnWidth(0, 360)
        table.horizontalHeader().setStretchLastSection(True)

        row_height = 26
        table.setFixedHeight(row_height * len(rows) + 4)

        for i, (concepto, monto, color) in enumerate(rows):
            is_last = i == len(rows) - 1

            item_concepto = QTableWidgetItem(concepto)
            item_monto = QTableWidgetItem(monto)
            item_monto.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            if color:
                q_color = QColor(color)
                item_concepto.setForeground(q_color)
                item_monto.setForeground(q_color)

            if bold_last and is_last:
                font = QFont()
                font.setBold(True)
                item_concepto.setFont(font)
                item_monto.setFont(font)

            table.setItem(i, 0, item_concepto)
            table.setItem(i, 1, item_monto)
            table.setRowHeight(i, row_height)

        return table
