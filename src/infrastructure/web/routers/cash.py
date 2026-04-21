"""Router de arqueo de caja.

Endpoints:
    GET  /api/cash/state                — estado del arqueo actualmente abierto
    POST /api/cash/open                 — abre un nuevo arqueo (o retorna el existente)
    POST /api/cash/close                — cierra el arqueo activo + dispara sync EOD
    POST /api/cash/movements            — registra un movimiento manual (ingreso/egreso)
    GET  /api/cash/history              — historial de cierres por rango de fechas
    GET  /api/cash/movements/{id}       — movimientos de un cierre específico
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.application.use_cases.add_cash_movement import AddCashMovement
from src.application.use_cases.close_cash_close import CloseCashClose
from src.application.use_cases.get_or_open_cash_close import GetOrOpenCashClose
from src.infrastructure.persistence.mariadb_cash_repository import MariadbCashRepository
from src.infrastructure.web.dependencies import get_cash_repo, get_session, require_auth

router = APIRouter(prefix="/api/cash", tags=["cash"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CashStateResponse(BaseModel):
    id: Optional[int]
    is_open: bool
    opened_at: Optional[str]
    opening_amount: str
    total_sales_cash: str
    total_sales_debit: str
    total_sales_transfer: str
    total_sales: str
    expected_cash: str


class OpenCashRequest(BaseModel):
    opening_amount: str = "0.00"   # Decimal como str para evitar float


class CloseCashRequest(BaseModel):
    closing_amount: str            # Decimal como str
    gross_profit_estimate: Optional[str] = None
    total_cost_estimate: Optional[str] = None


class AddMovementRequest(BaseModel):
    cash_close_id: int
    amount: str          # Decimal como str — positivo=ingreso, negativo=egreso
    description: str


class MovementResponse(BaseModel):
    id: int
    cash_close_id: int
    amount: str
    description: str
    created_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/state", response_model=CashStateResponse)
def get_cash_state(
    cash_repo: MariadbCashRepository = Depends(get_cash_repo),
    _auth: dict = Depends(require_auth),
):
    """Retorna el estado del arqueo de caja actualmente abierto.

    Si no hay ningún arqueo abierto, retorna ``{is_open: false, id: null}``.
    """
    cash_close = cash_repo.get_open()
    if cash_close is None:
        return CashStateResponse(
            id=None,
            is_open=False,
            opened_at=None,
            opening_amount="0.00",
            total_sales_cash="0.00",
            total_sales_debit="0.00",
            total_sales_transfer="0.00",
            total_sales="0.00",
            expected_cash="0.00",
        )

    totals = cash_repo.get_sales_totals_for_session(cash_close.id)
    total_cash = totals.get("EFECTIVO", Decimal("0.00"))
    total_debit = totals.get("DEBITO", Decimal("0.00"))
    total_transfer = totals.get("TRANSFERENCIA", Decimal("0.00"))
    total_all = total_cash + total_debit + total_transfer
    expected = cash_close.opening_amount + total_cash

    return CashStateResponse(
        id=cash_close.id,
        is_open=cash_close.is_open,
        opened_at=cash_close.opened_at.isoformat(),
        opening_amount=str(cash_close.opening_amount),
        total_sales_cash=str(total_cash),
        total_sales_debit=str(total_debit),
        total_sales_transfer=str(total_transfer),
        total_sales=str(total_all),
        expected_cash=str(expected),
    )


@router.post("/open", response_model=CashStateResponse)
def open_cash(
    body: OpenCashRequest,
    session: Session = Depends(get_session),
    cash_repo: MariadbCashRepository = Depends(get_cash_repo),
    _auth: dict = Depends(require_auth),
):
    """Abre un nuevo arqueo de caja o retorna el ya existente.

    Si ya hay un arqueo abierto, lo retorna sin modificarlo.
    """
    try:
        opening_amount = Decimal(body.opening_amount)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monto de apertura inválido: '{body.opening_amount}'",
        )

    try:
        cash_close = GetOrOpenCashClose(cash_repo).execute(opening_amount)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    open_totals = cash_repo.get_sales_totals_for_session(cash_close.id)
    ot_cash = open_totals.get("EFECTIVO", Decimal("0.00"))
    ot_debit = open_totals.get("DEBITO", Decimal("0.00"))
    ot_transfer = open_totals.get("TRANSFERENCIA", Decimal("0.00"))

    return CashStateResponse(
        id=cash_close.id,
        is_open=cash_close.is_open,
        opened_at=cash_close.opened_at.isoformat(),
        opening_amount=str(cash_close.opening_amount),
        total_sales_cash=str(ot_cash),
        total_sales_debit=str(ot_debit),
        total_sales_transfer=str(ot_transfer),
        total_sales=str(ot_cash + ot_debit + ot_transfer),
        expected_cash=str(cash_close.opening_amount + ot_cash),
    )


@router.get("/profit")
def get_profit(
    cash_repo: MariadbCashRepository = Depends(get_cash_repo),
    _auth: dict = Depends(require_auth),
):
    """Retorna la ganancia bruta estimada del arqueo actualmente abierto.

    Útil para mostrar el resumen de rentabilidad en el modal de cierre antes
    de confirmar. Devuelve ceros si no hay arqueo abierto o sin ventas.
    """
    cash_close = cash_repo.get_open()
    if cash_close is None or cash_close.id is None:
        return {
            "total_revenue": "0.00",
            "total_cost_estimate": "0.00",
            "gross_profit": "0.00",
            "margin_percent": "0.00",
            "total_sales_count": 0,
        }
    data = cash_repo.get_profit_data_for_session(cash_close.id)
    return {
        "total_revenue": str(data["total_revenue"]),
        "total_cost_estimate": str(data["total_cost_estimate"]),
        "gross_profit": str(data["gross_profit"]),
        "margin_percent": str(data["margin_percent"]),
        "total_sales_count": data["total_sales_count"],
    }


@router.post("/close")
def close_cash(
    body: CloseCashRequest,
    session: Session = Depends(get_session),
    cash_repo: MariadbCashRepository = Depends(get_cash_repo),
    auth: dict = Depends(require_auth),
):
    """Cierra el arqueo de caja activo y dispara la sincronización EOD.

    Calcula automáticamente la ganancia bruta estimada del período antes
    de persistir el cierre, sin depender de que el frontend la envíe.
    """
    try:
        closing_amount = Decimal(body.closing_amount)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monto de cierre inválido.",
        )

    try:
        # Obtener el arqueo abierto para calcular ganancia antes de cerrarlo
        cash_close = cash_repo.get_open()
        if cash_close is None:
            raise ValueError("No hay ningún arqueo de caja abierto para cerrar.")

        profit_data = cash_repo.get_profit_data_for_session(cash_close.id)
        gross = profit_data["gross_profit"]
        cost = profit_data["total_cost_estimate"]

        closed = CloseCashClose(cash_repo).execute(closing_amount, gross, cost)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Disparar sync EOD en background (no bloquea la respuesta)
    _trigger_eod_sync_if_configured(closed.id)

    margin = profit_data["margin_percent"]
    return {
        "id": closed.id,
        "closed_at": closed.closed_at.isoformat() if closed.closed_at else None,
        "closing_amount": str(closed.closing_amount),
        "total_sales": str(closed.total_sales.amount),
        "cash_difference": str(closed.cash_difference) if closed.cash_difference is not None else None,
        "gross_profit": str(gross),
        "total_cost_estimate": str(cost),
        "margin_percent": str(margin),
        "total_sales_count": profit_data["total_sales_count"],
    }


@router.post("/movements", response_model=MovementResponse)
def add_movement(
    body: AddMovementRequest,
    session: Session = Depends(get_session),
    cash_repo: MariadbCashRepository = Depends(get_cash_repo),
    _auth: dict = Depends(require_auth),
):
    """Registra un movimiento manual de caja (ingreso o egreso).

    El signo del monto determina la dirección:
    - Positivo: ingreso de efectivo (ej: "+2000.00" para reposición de cambio)
    - Negativo: egreso de efectivo (ej: "-500.00" para pago a proveedor)
    """
    try:
        amount = Decimal(body.amount)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monto inválido: '{body.amount}'",
        )

    try:
        movement = AddCashMovement(cash_repo).execute(
            cash_close_id=body.cash_close_id,
            amount=amount,
            description=body.description,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return MovementResponse(
        id=movement.id,
        cash_close_id=movement.cash_close_id,
        amount=str(movement.amount),
        description=movement.description,
        created_at=movement.created_at.isoformat(),
    )


@router.get("/history")
def list_cash_history(
    start: str = Query(..., description="Fecha inicio YYYY-MM-DD"),
    end: str = Query(..., description="Fecha fin YYYY-MM-DD"),
    cash_repo: MariadbCashRepository = Depends(get_cash_repo),
    _auth: dict = Depends(require_auth),
):
    """Lista los cierres de caja en un rango de fechas."""
    try:
        start_date = date_type.fromisoformat(start)
        end_date = date_type.fromisoformat(end)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato de fecha inválido. Use YYYY-MM-DD.")

    from decimal import ROUND_HALF_UP

    closes = cash_repo.list_by_date_range(start_date, end_date)

    # Query única para movimientos de todos los arqueos (evita N+1)
    close_ids = [cc.id for cc in closes if cc.id is not None]
    movements_totals = cash_repo.get_movements_totals_by_close_ids(close_ids)

    def _real_difference(cc) -> str | None:
        """Diferencia real: contado − (apertura + ventas_efectivo + movimientos_neto).

        Corrige el cash_difference del dominio que no incluye movimientos manuales.
        """
        if cc.closing_amount is None:
            return None
        net_mov = movements_totals.get(cc.id, Decimal("0"))
        expected = cc.opening_amount + cc.total_sales_cash + net_mov
        diff = (cc.closing_amount - expected).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return str(diff)

    def _margin(cc) -> str | None:
        """Margen sobre ventas: ganancia / revenue × 100."""
        if cc.gross_profit_estimate is None:
            return None
        rev = cc.total_sales.amount
        if rev == Decimal("0"):
            return "0.00"
        return str(
            (Decimal(str(cc.gross_profit_estimate)) / rev * 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )

    return [
        {
            "id": cc.id,
            "opened_at": cc.opened_at.isoformat(),
            "closed_at": cc.closed_at.isoformat() if cc.closed_at else None,
            "is_open": cc.is_open,
            "opening_amount": str(cc.opening_amount),
            "closing_amount": str(cc.closing_amount) if cc.closing_amount is not None else None,
            "total_sales_cash": str(cc.total_sales_cash),
            "total_sales_debit": str(cc.total_sales_debit),
            "total_sales_transfer": str(cc.total_sales_transfer),
            "total_sales": str(cc.total_sales.amount),
            "cash_difference": _real_difference(cc),
            "gross_profit": str(cc.gross_profit_estimate) if cc.gross_profit_estimate is not None else None,
            "total_cost_estimate": str(cc.total_cost_estimate) if cc.total_cost_estimate is not None else None,
            "margin_percent": _margin(cc),
        }
        for cc in closes
    ]


@router.get("/movements/{cash_close_id}")
def list_movements_for_close(
    cash_close_id: int,
    cash_repo: MariadbCashRepository = Depends(get_cash_repo),
    _auth: dict = Depends(require_auth),
):
    """Lista los movimientos manuales de un cierre de caja específico."""
    movements = cash_repo.list_by_cash_close(cash_close_id)
    return [
        {
            "id": m.id,
            "cash_close_id": m.cash_close_id,
            "amount": str(m.amount),
            "description": m.description,
            "created_at": m.created_at.isoformat(),
        }
        for m in movements
    ]


def _trigger_eod_sync_if_configured(cash_close_id: int) -> None:
    """Dispara la sincronización EOD si REMOTE_DATABASE_URL está configurada.

    Se ejecuta en un thread background para no bloquear la respuesta HTTP.
    Los errores de conexión al remoto se loguean pero no propagan al cliente.
    """
    import os
    import logging
    import threading

    remote_url = os.environ.get("REMOTE_DATABASE_URL")
    if not remote_url:
        return

    def _run() -> None:
        try:
            from src.infrastructure.sync.eod_sync import EodSync
            EodSync(remote_url=remote_url).sync(cash_close_id)
        except Exception:
            logging.getLogger(__name__).exception(
                "Sync EOD falló para cash_close_id=%s", cash_close_id
            )

    threading.Thread(target=_run, daemon=True).start()
