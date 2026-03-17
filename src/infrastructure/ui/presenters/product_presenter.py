"""Presenter MVP para la vista de gestión de productos (ProductManagementView).

Python puro: no importa PySide6. Completamente testeable con FakeProductManagementView.

Flujo principal:
    Pestaña activada
    → ProductPresenter.on_view_activated()
    → Vista lanza ListAllProductsWorker
    → on_products_loaded() puebla la lista

    Usuario selecciona producto
    → Vista lanza LoadProductWorker
    → on_product_fetched() puebla el formulario

    Usuario edita costo o margen
    → on_cost_changed() / on_margin_changed() → view.set_final_price_display()
    → on_final_price_changed() → view.set_margin_display()  (recíproco)

    Usuario guarda
    → on_save_requested() valida y retorna Product (o None)
    → Vista lanza SaveProductWorker
    → on_save_completed() actualiza estado
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional, Protocol, runtime_checkable

from src.domain.models.category import Category
from src.domain.models.product import Product


@runtime_checkable
class IProductManagementView(Protocol):
    """Contrato entre ProductPresenter y ProductManagementView."""

    def show_product_list(self, products: list[Product]) -> None:
        """Puebla la lista lateral con todos los productos.

        Args:
            products: Lista de productos a mostrar.
        """
        ...

    def show_product_in_form(self, product: Product, categories: list[Category]) -> None:
        """Carga los datos de un producto en el formulario.

        Args:
            product: Producto a mostrar en el formulario.
            categories: Lista de categorías para el combo.
        """
        ...

    def clear_form(self) -> None:
        """Limpia todos los campos del formulario para un nuevo producto."""
        ...

    def set_final_price_display(self, price: Decimal) -> None:
        """Actualiza el campo de precio final sin disparar señales.

        Args:
            price: Precio de venta calculado.
        """
        ...

    def set_margin_display(self, margin: Decimal) -> None:
        """Actualiza el campo de margen sin disparar señales.

        Args:
            margin: Porcentaje de margen calculado.
        """
        ...

    def show_status(self, message: str, is_error: bool = False) -> None:
        """Muestra un mensaje de estado al usuario.

        Args:
            message: Texto a mostrar.
            is_error: Si True, mostrar en estilo de error.
        """
        ...

    def show_delete_confirmation(self, product_name: str) -> bool:
        """Muestra un diálogo de confirmación antes de eliminar.

        Args:
            product_name: Nombre del producto a eliminar.

        Returns:
            True si el usuario confirma la eliminación.
        """
        ...

    def set_save_button_enabled(self, enabled: bool) -> None:
        """Habilita o deshabilita el botón "Guardar".

        Args:
            enabled: True para habilitar.
        """
        ...

    def set_delete_button_enabled(self, enabled: bool) -> None:
        """Habilita o deshabilita el botón "Eliminar".

        Args:
            enabled: True para habilitar (solo cuando hay producto seleccionado).
        """
        ...

    def get_form_data(self) -> dict:
        """Retorna los datos actuales del formulario.

        Returns:
            Dict con claves: barcode, name, category_id, stock, min_stock,
            cost, margin, final_price.
        """
        ...


def _to_decimal(value: str) -> Optional[Decimal]:
    """Convierte un string a Decimal, retorna None si no es válido.

    Args:
        value: String numérico a convertir.

    Returns:
        Decimal o None si el string no es un número válido.
    """
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


class ProductPresenter:
    """Presenter para la gestión de productos (MVP).

    Python puro: no importa PySide6. Completamente testeable con FakeProductManagementView.

    Args:
        view: Objeto que implementa IProductManagementView.
    """

    def __init__(self, view: IProductManagementView) -> None:
        self._view = view
        self._selected_product: Optional[Product] = None
        self._current_cost: Decimal = Decimal("0")

    # ------------------------------------------------------------------
    # Handlers de acciones del usuario (delegan workers a la vista)
    # ------------------------------------------------------------------

    def on_view_activated(self) -> None:
        """Señal que la pestaña fue activada; la vista lanza ListAllProductsWorker."""
        self._view.show_status("Cargando productos…")

    def on_product_selected(self, product_id: int) -> None:
        """Usuario seleccionó un producto de la lista; la vista lanza LoadProductWorker.

        Args:
            product_id: ID del producto seleccionado.
        """
        self._view.show_status(f"Cargando producto #{product_id}…")

    def on_new_product_requested(self) -> None:
        """Usuario pulsó '+ Nuevo': limpia formulario y deselecciona producto actual."""
        self._selected_product = None
        self._current_cost = Decimal("0")
        self._view.clear_form()
        self._view.set_delete_button_enabled(False)
        self._view.show_status("Nuevo producto. Complete los datos y guarde.")

    def on_cost_changed(self, cost_str: str) -> None:
        """Usuario modificó el costo: actualiza estado interno y recalcula precio final.

        Caso A: precio = costo × (1 + margen / 100).
        Solo actualiza si el costo es un número válido y positivo.

        Args:
            cost_str: Valor del campo costo como string.
        """
        cost = _to_decimal(cost_str)
        if cost is None or cost < Decimal("0"):
            self._current_cost = Decimal("0")
            return
        self._current_cost = cost

        form = self._view.get_form_data()
        margin = _to_decimal(str(form.get("margin", "0")))
        if margin is None:
            margin = Decimal("0")
        self._recalculate_price(self._current_cost, margin)

    def on_margin_changed(self, margin_str: str) -> None:
        """Usuario modificó el margen: recalcula precio final (Caso A).

        Args:
            margin_str: Valor del campo margen como string.
        """
        margin = _to_decimal(margin_str)
        if margin is None or margin < Decimal("0"):
            return
        self._recalculate_price(self._current_cost, margin)

    def on_final_price_changed(self, price_str: str) -> None:
        """Usuario modificó el precio final: recalcula margen (Caso B).

        Caso B: margen = ((precio / costo) - 1) × 100.
        Guard: si costo == 0, no actualiza para evitar división por cero.

        Args:
            price_str: Valor del campo precio final como string.
        """
        if self._current_cost == Decimal("0"):
            return
        price = _to_decimal(price_str)
        if price is None or price < Decimal("0"):
            return
        margin = ((price / self._current_cost) - Decimal("1")) * Decimal("100")
        margin = margin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self._view.set_margin_display(margin)

    def on_save_requested(self) -> Optional[Product]:
        """Valida el formulario y construye el objeto Product.

        Retorna el Product si la validación es exitosa, None si hay errores.
        La vista es la responsable de lanzar SaveProductWorker con el producto.

        Returns:
            Product construido o None si hay errores de validación.
        """
        data = self._view.get_form_data()

        barcode = str(data.get("barcode", "")).strip()
        if not barcode:
            self._view.show_status("El código de barras es obligatorio.", is_error=True)
            return None

        name = str(data.get("name", "")).strip()
        if not name:
            self._view.show_status("El nombre del producto es obligatorio.", is_error=True)
            return None

        cost = _to_decimal(str(data.get("cost", "0")))
        if cost is None or cost < Decimal("0"):
            self._view.show_status("El costo debe ser un número no negativo.", is_error=True)
            return None

        margin = _to_decimal(str(data.get("margin", "0")))
        if margin is None or margin < Decimal("0"):
            self._view.show_status("El margen debe ser un número no negativo.", is_error=True)
            return None

        try:
            stock = int(data.get("stock", 0))
            min_stock = int(data.get("min_stock", 0))
        except (ValueError, TypeError):
            self._view.show_status("Stock y stock mínimo deben ser enteros.", is_error=True)
            return None

        category_id = data.get("category_id")
        if category_id is not None:
            try:
                category_id = int(category_id)
            except (ValueError, TypeError):
                category_id = None

        try:
            product = Product(
                barcode=barcode,
                name=name,
                current_cost=cost,
                margin_percent=margin,
                stock=stock,
                min_stock=min_stock,
                category_id=category_id,
                id=self._selected_product.id if self._selected_product else None,
            )
        except ValueError as exc:
            self._view.show_status(str(exc), is_error=True)
            return None

        return product

    def on_delete_requested(self) -> bool:
        """Solicita confirmación para eliminar el producto seleccionado.

        Retorna True si el usuario confirmó y hay producto seleccionado.
        La vista es la responsable de lanzar DeleteProductWorker.

        Returns:
            True si se debe proceder con la eliminación.
        """
        if self._selected_product is None:
            self._view.show_status("No hay producto seleccionado para eliminar.", is_error=True)
            return False
        return self._view.show_delete_confirmation(self._selected_product.name)

    # ------------------------------------------------------------------
    # Callbacks de workers (llamados desde la vista tras completar)
    # ------------------------------------------------------------------

    def on_products_loaded(self, products: list[Product]) -> None:
        """Recibe la lista de productos cargada por ListAllProductsWorker.

        Args:
            products: Lista de productos del catálogo.
        """
        self._view.show_product_list(products)
        self._view.show_status(f"{len(products)} producto(s) en catálogo.")

    def on_product_fetched(self, data: dict) -> None:
        """Recibe producto + categorías cargados por LoadProductWorker.

        Args:
            data: Dict con claves ``product`` (Product) y ``categories`` (list[Category]).
        """
        product: Optional[Product] = data.get("product")
        categories: list[Category] = data.get("categories", [])
        if product is None:
            self._view.show_status("Producto no encontrado.", is_error=True)
            return
        self._selected_product = product
        self._current_cost = product.current_cost
        self._view.show_product_in_form(product, categories)
        self._view.set_delete_button_enabled(True)
        self._view.show_status(f"Producto '{product.name}' cargado.")

    def on_save_completed(self, product: Product) -> None:
        """Recibe el producto persistido por SaveProductWorker.

        Args:
            product: Producto guardado (con id asignado por DB).
        """
        self._selected_product = product
        self._current_cost = product.current_cost
        self._view.set_delete_button_enabled(True)
        self._view.show_status(f"Producto '{product.name}' guardado correctamente.")

    def on_delete_completed(self) -> None:
        """Recibe la confirmación de eliminación de DeleteProductWorker."""
        self._selected_product = None
        self._current_cost = Decimal("0")
        self._view.clear_form()
        self._view.set_delete_button_enabled(False)
        self._view.show_status("Producto eliminado.")

    def on_worker_error(self, error: str) -> None:
        """Recibe un mensaje de error de cualquier worker.

        Args:
            error: Mensaje de error del worker.
        """
        self._view.show_status(f"Error: {error}", is_error=True)

    # ------------------------------------------------------------------
    # Lógica de cálculo recíproco (privada)
    # ------------------------------------------------------------------

    def _recalculate_price(self, cost: Decimal, margin: Decimal) -> None:
        """Caso A: precio = costo × (1 + margen / 100).

        Solo actualiza si el costo es > 0.

        Args:
            cost: Costo del producto en ARS.
            margin: Porcentaje de margen.
        """
        if cost <= Decimal("0"):
            return
        price = cost * (Decimal("1") + margin / Decimal("100"))
        price = price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self._view.set_final_price_display(price)
