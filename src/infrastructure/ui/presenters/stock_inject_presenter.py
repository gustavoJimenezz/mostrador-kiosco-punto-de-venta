"""Presenter MVP para la vista de inyección directa de stock (StockInjectView).

Python puro: no importa PySide6. Completamente testeable con FakeStockInjectView.

Flujo principal:
    Usuario ingresa cantidad + código de barras → Enter
    → Vista lanza SearchByBarcodeWorker
    → on_barcode_found() valida qty y retorna (product, qty) → Vista lanza UpdateStockWorker
    → on_stock_injected() actualiza tabla y limpia buscador

    Usuario ingresa cantidad + texto parcial → Enter
    → Vista lanza SearchByNameWorker
    → on_search_results_ready():
        · 0 resultados  → error
        · 1 resultado   → inyección automática (mismo flujo que barcode)
        · N resultados  → show_search_results, usuario selecciona
    → on_product_selected_from_list() valida qty y retorna (product, qty) → Vista lanza worker
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from src.domain.models.product import Product


@runtime_checkable
class IStockInjectView(Protocol):
    """Contrato entre StockInjectPresenter y StockInjectView."""

    def show_search_results(self, products: list[Product]) -> None:
        """Muestra la lista de productos encontrados por nombre.

        Args:
            products: Lista de productos a mostrar.
        """
        ...

    def show_status(self, message: str, is_error: bool = False) -> None:
        """Muestra un mensaje de estado al usuario.

        Args:
            message: Texto a mostrar.
            is_error: Si True, mostrar en estilo de error.
        """
        ...

    def add_or_update_injected_row(self, product: Product) -> None:
        """Agrega o actualiza la fila del producto en la tabla de sesión.

        Args:
            product: Producto con stock ya actualizado.
        """
        ...

    def get_quantity(self) -> int:
        """Retorna la cantidad del spinbox.

        Returns:
            Entero >= 1.
        """
        ...

    def clear_search(self) -> None:
        """Limpia el campo de búsqueda y devuelve el foco al spinbox."""
        ...


class StockInjectPresenter:
    """Presenter para la inyección directa de stock (MVP).

    Python puro: no importa PySide6. Completamente testeable con FakeStockInjectView.

    Args:
        view: Objeto que implementa IStockInjectView.
    """

    def __init__(self, view: IStockInjectView) -> None:
        self._view = view
        self._last_injected_qty: int = 0

    # ------------------------------------------------------------------
    # Callbacks de búsqueda
    # ------------------------------------------------------------------

    def on_barcode_found(self, product: Product) -> Optional[tuple[Product, int]]:
        """Recibe el producto encontrado por código de barras.

        Valida que la cantidad sea > 0. Si es válida retorna ``(product, qty)``
        para que la vista lance ``UpdateStockWorker``; si no, muestra error
        y retorna ``None``.

        Args:
            product: Producto encontrado.

        Returns:
            ``(product, qty)`` si la validación pasa, ``None`` si hay error.
        """
        qty = self._view.get_quantity()
        if qty <= 0:
            self._view.show_status(
                "Ingrese una cantidad mayor a cero antes de buscar.", is_error=True
            )
            return None
        self._last_injected_qty = qty
        return (product, qty)

    def on_barcode_not_found(self, barcode: str) -> None:
        """Informa que no se encontró ningún producto con ese código.

        Args:
            barcode: Código de barras que no arrojó resultados.
        """
        self._view.show_status(f"No encontrado: '{barcode}'", is_error=True)

    def on_search_results_ready(
        self, products: list[Product]
    ) -> Optional[tuple[Product, int]]:
        """Recibe los resultados de una búsqueda por nombre.

        - 0 resultados → muestra error, retorna None.
        - 1 resultado  → inyección automática (delega a ``on_barcode_found``).
        - N resultados → muestra lista de selección, retorna None.

        Args:
            products: Lista de productos encontrados.

        Returns:
            ``(product, qty)`` si hay exactamente 1 resultado y la cantidad es
            válida; ``None`` en los demás casos.
        """
        if not products:
            self._view.show_status("No se encontraron productos.", is_error=True)
            return None
        if len(products) == 1:
            return self.on_barcode_found(products[0])
        self._view.show_search_results(products)
        return None

    def on_product_selected_from_list(
        self, product: Product
    ) -> Optional[tuple[Product, int]]:
        """Usuario seleccionó un producto de la lista de resultados.

        Reutiliza la misma validación de cantidad que ``on_barcode_found``.

        Args:
            product: Producto seleccionado.

        Returns:
            ``(product, qty)`` si la cantidad es válida, ``None`` si hay error.
        """
        return self.on_barcode_found(product)

    # ------------------------------------------------------------------
    # Callbacks de workers
    # ------------------------------------------------------------------

    def on_stock_injected(self, product: Product) -> None:
        """Recibe el producto actualizado por ``UpdateStockWorker``.

        Args:
            product: Producto con stock ya persistido.
        """
        self._view.add_or_update_injected_row(product)
        self._view.clear_search()
        self._view.show_status(
            f"✓ '{product.name}': +{self._last_injected_qty} u. → Stock: {product.stock}"
        )

    def on_worker_error(self, error: str) -> None:
        """Recibe un mensaje de error de cualquier worker.

        Args:
            error: Mensaje de error del worker.
        """
        self._view.show_status(f"Error: {error}", is_error=True)
