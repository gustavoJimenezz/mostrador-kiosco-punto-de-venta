"""Implementación en memoria de SaleRepository para tests unitarios.

No requiere base de datos. Cumple el contrato definido en el puerto
SaleRepository. Usada en los tests del caso de uso ProcessSale.
"""

from __future__ import annotations

from src.domain.models.sale import Sale


class InMemorySaleRepository:
    """Repositorio de ventas en memoria que implementa SaleRepository.

    Almacena ventas en una lista. Registra si ``save`` fue llamado y
    permite simular fallos lanzando la excepción configurada en
    ``fail_with``.

    Examples:
        >>> repo = InMemorySaleRepository()
        >>> sale = Sale(payment_method=PaymentMethod.CASH, items=[item])
        >>> saved = repo.save(sale)
        >>> len(repo.saved)
        1
    """

    def __init__(self) -> None:
        self.saved: list[Sale] = []
        self.fail_with: Exception | None = None

    def save(self, sale: Sale) -> Sale:
        """Persiste la venta en memoria.

        Args:
            sale: Entidad Sale a guardar.

        Returns:
            La misma instancia de Sale recibida.

        Raises:
            Exception: Si ``fail_with`` está configurado, lo lanza antes
                de persistir, simulando un fallo de transacción.
        """
        if self.fail_with is not None:
            raise self.fail_with
        self.saved.append(sale)
        return sale
