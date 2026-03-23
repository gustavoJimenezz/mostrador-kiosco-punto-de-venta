"""Presenter MVP para la vista de edición de stock (StockEditView).

Python puro: no importa PySide6. Completamente testeable con FakeStockEditView.

Flujo principal:
    Usuario ingresa código de barras
    → Vista lanza SearchByBarcodeWorker
    → on_barcode_found() muestra formulario con datos del producto

    Usuario ingresa nombre parcial
    → Vista lanza SearchByNameWorker
    → on_search_results_ready() muestra lista o va directo al formulario

    Usuario confirma ajuste de stock
    → on_confirm_stock_edit_requested() valida y retorna (product, operation, qty)
    → Vista lanza UpdateStockWorker
    → on_stock_updated() actualiza tabla de sesión y resetea formulario
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from src.domain.models.product import Product


@runtime_checkable
class IStockEditView(Protocol):
    """Contrato entre StockEditPresenter y StockEditView."""

    def show_search_results(self, products: list[Product]) -> None:
        """Muestra la lista de productos encontrados por nombre.

        Args:
            products: Lista de productos a mostrar.
        """
        ...

    def show_product_form(self, product: Product) -> None:
        """Muestra el formulario de ajuste con los datos del producto.

        Args:
            product: Producto seleccionado para editar stock.
        """
        ...

    def show_status(self, message: str, is_error: bool = False) -> None:
        """Muestra un mensaje de estado al usuario.

        Args:
            message: Texto a mostrar.
            is_error: Si True, mostrar en estilo de error.
        """
        ...

    def add_or_update_edited_row(self, product: Product) -> None:
        """Agrega o actualiza la fila del producto en la tabla de sesión.

        Args:
            product: Producto con stock ya actualizado.
        """
        ...

    def get_operation(self) -> str:
        """Retorna la operación seleccionada por el usuario.

        Returns:
            ``"increment"`` o ``"decrement"``.
        """
        ...

    def get_quantity(self) -> int:
        """Retorna la cantidad ingresada en el spinbox.

        Returns:
            Entero positivo.
        """
        ...

    def reset_form(self) -> None:
        """Resetea el formulario: spinbox=1, radio_add=True, foco al buscador."""
        ...


class StockEditPresenter:
    """Presenter para la edición de stock (MVP).

    Python puro: no importa PySide6. Completamente testeable con FakeStockEditView.

    Args:
        view: Objeto que implementa IStockEditView.
    """

    def __init__(self, view: IStockEditView) -> None:
        self._view = view
        self._selected_product: Optional[Product] = None

    # ------------------------------------------------------------------
    # Callbacks de búsqueda (conectados a SearchByBarcodeWorker /
    # SearchByNameWorker desde la vista)
    # ------------------------------------------------------------------

    def on_barcode_found(self, product: Product) -> None:
        """Recibe el producto encontrado por código de barras.

        Args:
            product: Producto encontrado.
        """
        self._selected_product = product
        self._view.show_product_form(product)

    def on_barcode_not_found(self, barcode: str) -> None:
        """Informa que no se encontró ningún producto con ese código.

        Args:
            barcode: Código de barras que no arrojó resultados.
        """
        self._view.show_status(f"No encontrado: '{barcode}'", is_error=True)

    def on_search_results_ready(self, products: list[Product]) -> None:
        """Recibe los resultados de una búsqueda por nombre.

        Si la lista está vacía muestra error; si tiene un único elemento va
        directo al formulario; si tiene varios muestra la lista de selección.

        Args:
            products: Lista de productos encontrados.
        """
        if not products:
            self._view.show_status("No se encontraron productos.", is_error=True)
            return
        if len(products) == 1:
            self._selected_product = products[0]
            self._view.show_product_form(products[0])
        else:
            self._view.show_search_results(products)

    def on_product_selected_from_list(self, product: Product) -> None:
        """Usuario seleccionó un producto de la lista de resultados.

        Args:
            product: Producto seleccionado.
        """
        self._selected_product = product
        self._view.show_product_form(product)

    def on_confirm_stock_edit_requested(
        self,
    ) -> Optional[tuple[Product, str, int]]:
        """Valida el estado del formulario y retorna los datos para el worker.

        Returns:
            ``(product, operation, quantity)`` si la validación pasa, o ``None``
            si hay errores (en ese caso muestra el error en la vista).
        """
        if self._selected_product is None:
            self._view.show_status(
                "Seleccione un producto antes de confirmar.", is_error=True
            )
            return None

        qty = self._view.get_quantity()
        if qty <= 0:
            self._view.show_status(
                "La cantidad debe ser mayor a cero.", is_error=True
            )
            return None

        operation = self._view.get_operation()
        return (self._selected_product, operation, qty)

    # ------------------------------------------------------------------
    # Callbacks de workers (llamados desde la vista tras completar)
    # ------------------------------------------------------------------

    def on_stock_updated(self, product: Product) -> None:
        """Recibe el producto actualizado por UpdateStockWorker.

        Args:
            product: Producto con stock ya persistido.
        """
        self._view.add_or_update_edited_row(product)
        self._view.reset_form()
        self._view.show_status(
            f"Stock actualizado: '{product.name}' → {product.stock} u."
        )

    def on_worker_error(self, error: str) -> None:
        """Recibe un mensaje de error de cualquier worker.

        Args:
            error: Mensaje de error del worker.
        """
        self._view.show_status(f"Error: {error}", is_error=True)
