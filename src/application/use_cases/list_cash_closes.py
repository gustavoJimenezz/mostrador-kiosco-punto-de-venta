"""Caso de uso: listar cierres de caja por rango de fechas."""

from __future__ import annotations

from datetime import date

from src.domain.models.cash_close import CashClose


class ListCashCloses:
    """Lista los arqueos de caja comprendidos en un rango de fechas.

    Args:
        repo: Repositorio que implementa ``list_by_date_range``.

    Examples:
        >>> uc = ListCashCloses(repo)
        >>> closes = uc.execute(date(2026, 3, 1), date(2026, 3, 31))
    """

    def __init__(self, repo) -> None:
        self._repo = repo

    def execute(self, start: date, end: date) -> list[CashClose]:
        """Retorna los arqueos cuya apertura cae dentro del rango dado.

        Args:
            start: Fecha de inicio (inclusivo).
            end: Fecha de fin (inclusivo).

        Returns:
            Lista de CashClose ordenada por ``opened_at`` descendente.

        Raises:
            ValueError: Si ``start`` es posterior a ``end``.
        """
        if start > end:
            raise ValueError(
                "La fecha de inicio no puede ser posterior a la fecha de fin."
            )
        return self._repo.list_by_date_range(start, end)
