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

    return CashStateResponse(
        id=cash_close.id,
        is_open=cash_close.is_open,
        opened_at=cash_close.opened_at.isoformat(),
        opening_amount=str(cash_close.opening_amount),
        total_sales_cash=str(cash_close.total_sales_cash),
        total_sales_debit=str(cash_close.total_sales_debit),
        total_sales_transfer=str(cash_close.total_sales_transfer),
        total_sales=str(cash_close.total_sales.amount),
        expected_cash=str(cash_close.expected_cash.amount),
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

    return CashStateResponse(
        id=cash_close.id,
        is_open=cash_close.is_open,
        opened_at=cash_close.opened_at.isoformat(),
        opening_amount=str(cash_close.opening_amount),
        total_sales_cash=str(cash_close.total_sales_cash),
        total_sales_debit=str(cash_close.total_sales_debit),
        total_sales_transfer=str(cash_close.total_sales_transfer),
        total_sales=str(cash_close.total_sales.amount),
        expected_cash=str(cash_close.expected_cash.amount),
    )


@router.post("/close")
def close_cash(
    body: CloseCashRequest,
    session: Session = Depends(get_session),
    cash_repo: MariadbCashRepository = Depends(get_cash_repo),
    auth: dict = Depends(require_auth),
):
    """Cierra el arqueo de caja activo y dispara la sincronización EOD.

    La sincronización EOD se ejecuta en background si ``REMOTE_DATABASE_URL``
    está configurada en el entorno. Si no hay conexión al remoto, la operación
    de cierre igual se completa y se encola el sync para el próximo intento.
    """
    try:
        closing_amount = Decimal(body.closing_amount)
        gross = Decimal(body.gross_profit_estimate) if body.gross_profit_estimate else None
        cost = Decimal(body.total_cost_estimate) if body.total_cost_estimate else None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monto de cierre inválido.",
        )

    try:
        closed = CloseCashClose(cash_repo).execute(closing_amount, gross, cost)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Disparar sync EOD en background (no bloquea la respuesta)
    _trigger_eod_sync_if_configured(closed.id)

    return {
        "id": closed.id,
        "closed_at": closed.closed_at.isoformat() if closed.closed_at else None,
        "closing_amount": str(closed.closing_amount),
        "total_sales": str(closed.total_sales.amount),
        "cash_difference": str(closed.cash_difference) if closed.cash_difference is not None else None,
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

    closes = cash_repo.list_by_date_range(start_date, end_date)
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
            "cash_difference": str(cc.cash_difference) if cc.cash_difference is not None else None,
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
