"""Puertos de salida: contratos de persistencia para arqueo de caja.

Define las interfaces que los adaptadores de infraestructura deben
implementar para gestionar sesiones de caja y movimientos manuales.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from src.domain.models.cash_close import CashClose
from src.domain.models.cash_movement import CashMovement


@runtime_checkable
class CashCloseRepository(Protocol):
    """Puerto de salida para persistencia de arqueos de caja.

    Examples:
        >>> class MockCashRepo:
        ...     def get_open(self) -> Optional[CashClose]: return None
        ...     def save(self, c: CashClose) -> CashClose: return c
        >>> isinstance(MockCashRepo(), CashCloseRepository)
        True
    """

    def get_open(self) -> Optional[CashClose]:
        """Retorna el arqueo abierto actualmente, o None si no hay ninguno.

        Solo puede haber un arqueo abierto al mismo tiempo.

        Returns:
            CashClose con ``closed_at=None``, o None si no existe.
        """
        ...

    def save(self, cash_close: CashClose) -> CashClose:
        """Persiste (INSERT o UPDATE) el arqueo de caja.

        Args:
            cash_close: Entidad a persistir.

        Returns:
            CashClose con ``id`` asignado por la DB.
        """
        ...


@runtime_checkable
class CashMovementRepository(Protocol):
    """Puerto de salida para persistencia de movimientos manuales de caja.

    Examples:
        >>> class MockMovRepo:
        ...     def save(self, m: CashMovement) -> CashMovement: return m
        ...     def list_by_cash_close(self, cid: int) -> list[CashMovement]: return []
        >>> isinstance(MockMovRepo(), CashMovementRepository)
        True
    """

    def save(self, movement: CashMovement) -> CashMovement:
        """Persiste un movimiento manual de caja.

        Args:
            movement: Entidad CashMovement a insertar.

        Returns:
            CashMovement con ``id`` asignado por la DB.
        """
        ...

    def list_by_cash_close(self, cash_close_id: int) -> list[CashMovement]:
        """Lista todos los movimientos de un arqueo de caja.

        Args:
            cash_close_id: ID del arqueo de caja.

        Returns:
            Lista de CashMovement ordenada por ``created_at`` ascendente.
        """
        ...
