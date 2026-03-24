"""Presenter del punto de venta (patrón MVP).

Contiene toda la lógica de presentación: gestión del carrito, cálculo del
total, validaciones de UI. Sin dependencias de PySide6 — Python puro,
completamente testeable sin Qt instalado.

Arquitectura:
    MainWindow (View) llama métodos del presenter con datos ya resueltos.
    Los workers QThread corren en MainWindow y llaman callbacks del presenter
    una vez que la operación DB completó. El presenter nunca bloquea.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from src.domain.models.price import Price
from src.domain.models.product import Product
from src.domain.models.sale import PaymentMethod, Sale
from src.domain.ports.draft_cart_repository import DraftCartRepository


@runtime_checkable
class ISaleView(Protocol):
    """Interfaz que la vista (MainWindow) debe implementar.

    Define el contrato entre el Presenter y cualquier implementación
    de vista (Qt en producción, FakeView en tests).
    """

    def show_product_in_cart(self, product: Product, quantity: int) -> None:
        """Agrega o actualiza la fila del producto en la tabla del carrito.

        Args:
            product: Producto a mostrar/actualizar.
            quantity: Cantidad actualizada en el carrito.
        """
        ...

    def update_total(self, total: Price) -> None:
        """Actualiza el label del total de la venta en pantalla.

        Args:
            total: Monto total calculado del carrito actual.
        """
        ...

    def show_search_results(self, products: list[Product]) -> None:
        """Muestra la lista de resultados de búsqueda por nombre.

        Args:
            products: Lista de productos que coinciden con la búsqueda.
        """
        ...

    def clear_cart_display(self) -> None:
        """Limpia visualmente la tabla del carrito (no el estado interno)."""
        ...

    def show_error(self, message: str) -> None:
        """Muestra un mensaje de error al usuario.

        Args:
            message: Texto del error a mostrar.
        """
        ...

    def show_stock_error(self, message: str) -> None:
        """Muestra un diálogo de error de stock (bloqueante) al usuario.

        Se usa cuando no se puede agregar un producto al carrito por falta
        de stock, para que el cajero entienda claramente por qué no se agregó.

        Args:
            message: Texto del error a mostrar en el diálogo.
        """
        ...

    def show_sale_confirmed(self, sale: Sale) -> None:
        """Muestra confirmación de venta exitosa y limpia la UI.

        Args:
            sale: Venta confirmada con su ID y total.
        """
        ...

    def show_change_dialog(self, total: Price) -> bool:
        """Muestra el diálogo de vuelto para pago en efectivo (F12).

        Args:
            total: Monto total de la venta a cobrar.

        Returns:
            True si el cajero confirmó el cobro, False si canceló.
        """
        ...


class SalePresenter:
    """Presenter del punto de venta (MVP).

    Gestiona el estado del carrito y coordina las acciones del cajero.
    Python puro: no importa PySide6, completamente testeable.

    El estado interno del carrito es::

        _cart: dict[product_id, (Product, quantity)]

    Flujo de barcode:
        MainWindow crea SearchByBarcodeWorker → worker emite product_found →
        MainWindow llama presenter.on_barcode_found(product).

    Flujo de confirmar venta:
        F4 → MainWindow llama presenter.on_confirm_sale_requested() →
        presenter llama view.show_change_dialog(total) → retorna bool →
        si confirmado, retorna PaymentMethod.CASH → MainWindow crea
        ProcessSaleWorker → worker emite sale_completed →
        MainWindow llama presenter.on_sale_completed(sale).

    Args:
        view: Objeto que implementa ISaleView.
    """

    def __init__(
        self,
        view: ISaleView,
        draft_repo: Optional[DraftCartRepository] = None,
    ) -> None:
        """Inicializa el presenter con la vista inyectada.

        Args:
            view: Implementación de ISaleView (MainWindow o FakeView en tests).
            draft_repo: Repositorio opcional para persistir el carrito en curso.
                        Si es None, el carrito no se persiste (tests unitarios).
        """
        self._view = view
        self._draft_repo = draft_repo
        self._cart: dict[int, tuple[Product, int]] = {}

    # ------------------------------------------------------------------
    # Callbacks de workers (resultados de operaciones DB asíncronas)
    # ------------------------------------------------------------------

    def on_barcode_found(self, product: Product) -> None:
        """Maneja el resultado exitoso de búsqueda por barcode.

        Llamado por MainWindow cuando SearchByBarcodeWorker emite product_found.

        Args:
            product: Producto encontrado en la DB.
        """
        self._add_product_to_cart(product)

    def on_barcode_not_found(self, barcode: str) -> None:
        """Maneja el caso en que el barcode no existe en el catálogo.

        Args:
            barcode: Código de barras que no se encontró.
        """
        self._view.show_error(f"Producto no encontrado: '{barcode}'")

    def on_search_error(self, error_message: str) -> None:
        """Maneja errores de DB durante cualquier búsqueda.

        Args:
            error_message: Descripción del error recibida desde el worker.
        """
        self._view.show_error(f"Error al buscar: {error_message}")

    def on_search_results_ready(self, products: list[Product]) -> None:
        """Maneja los resultados de búsqueda por nombre.

        Llamado por MainWindow cuando SearchByNameWorker emite results_ready.

        Args:
            products: Lista de productos encontrados (puede ser vacía).
        """
        if not products:
            self._view.show_error("No se encontraron productos con ese nombre.")
        else:
            self._view.show_search_results(products)

    def on_sale_completed(self, sale: Sale) -> None:
        """Maneja la confirmación de venta exitosa.

        Llamado por MainWindow cuando ProcessSaleWorker emite sale_completed.
        Muestra la confirmación y limpia el carrito para la próxima venta.

        Args:
            sale: Venta persistida en la DB.
        """
        self._view.show_sale_confirmed(sale)
        self._clear_cart()

    def on_sale_error(self, error_message: str) -> None:
        """Maneja un error durante el procesamiento de la venta.

        El carrito NO se limpia para que el cajero pueda reintentar.

        Args:
            error_message: Descripción del error recibida desde el worker.
        """
        self._view.show_error(f"Error al procesar la venta: {error_message}")

    # ------------------------------------------------------------------
    # Acciones directas del cajero (síncronas)
    # ------------------------------------------------------------------

    def on_product_selected_from_list(self, product: Product) -> None:
        """Agrega al carrito un producto seleccionado de la lista de búsqueda.

        Args:
            product: Producto seleccionado por el cajero.
        """
        self._add_product_to_cart(product)

    def on_confirm_sale_requested(self) -> Optional[PaymentMethod]:
        """Maneja F4: valida carrito y solicita el método de pago.

        Retorna el PaymentMethod para que MainWindow lance ProcessSaleWorker,
        o None si el carrito está vacío o el cajero canceló el diálogo.

        Returns:
            PaymentMethod seleccionado, o None.
        """
        if not self._cart:
            self._view.show_error("Carrito vacío. Escanee un producto primero.")
            return None

        confirmed = self._view.show_change_dialog(self.get_total())
        return PaymentMethod.CASH if confirmed else None

    def on_cash_payment_requested(self) -> Optional[PaymentMethod]:
        """Maneja F12: valida carrito y muestra ChangeDialog (efectivo implícito).

        Retorna PaymentMethod.CASH si el cajero confirmó el cobro en efectivo,
        o None si el carrito está vacío o el cajero canceló el diálogo.

        Returns:
            PaymentMethod.CASH si confirmado, None en caso contrario.
        """
        if not self._cart:
            self._view.show_error("Carrito vacío. Escanee un producto primero.")
            return None

        confirmed = self._view.show_change_dialog(self.get_total())
        return PaymentMethod.CASH if confirmed else None

    def on_new_sale(self) -> None:
        """F1: Inicia una nueva venta limpiando el carrito."""
        self._clear_cart()

    def on_cash_close(self) -> None:
        """F10: Inicia el cierre de caja.

        Note:
            Stub para Ticket 3.1. Se implementa completamente en un ticket posterior.
        """
        self._view.show_error("Cierre de caja: funcionalidad disponible próximamente.")

    def on_remove_selected_item(self, product_id: int) -> None:
        """Elimina un producto del carrito y refresca la UI.

        Args:
            product_id: ID del producto a eliminar del carrito.
        """
        if product_id in self._cart:
            del self._cart[product_id]
            self._refresh_cart_display()
            self._save_draft()

    def on_quantity_changed(self, product_id: int, new_quantity: int) -> None:
        """Actualiza la cantidad de un producto en el carrito.

        Si new_quantity <= 0, elimina el producto del carrito.
        Si new_quantity supera el stock disponible, muestra error y no actualiza.

        Args:
            product_id: ID del producto a actualizar.
            new_quantity: Nueva cantidad deseada.
        """
        if product_id not in self._cart:
            return

        product, _ = self._cart[product_id]

        if new_quantity <= 0:
            del self._cart[product_id]
        elif new_quantity > product.stock:
            self._view.show_stock_error(
                f"Sin stock suficiente para '{product.name}'.\n"
                f"Disponible: {product.stock}."
            )
            return
        else:
            self._cart[product_id] = (product, new_quantity)

        self._refresh_cart_display()
        self._save_draft()

    # ------------------------------------------------------------------
    # Consultas de estado (solo lectura, para MainWindow)
    # ------------------------------------------------------------------

    def has_active_sale_items(self) -> bool:
        """Retorna True si hay ítems cargados en el carrito actual.

        Usado por MainWindow para adaptar el mensaje del modal de confirmación
        de cierre: si hay venta en curso, advierte sobre pérdida de datos.

        Returns:
            bool: True si el carrito tiene al menos un producto.
        """
        return bool(self._cart)

    def get_cart(self) -> dict[int, tuple[Product, int]]:
        """Retorna una copia del carrito actual.

        Returns:
            Dict ``{product_id: (Product, quantity)}``. Copia defensiva.
        """
        return dict(self._cart)

    def get_total(self) -> Price:
        """Calcula el total del carrito sumando todos los subtotales.

        Returns:
            Price con la suma de (current_price × quantity) por cada ítem.
        """
        total = Price("0")
        for product, quantity in self._cart.values():
            total = total + product.current_price * quantity
        return total

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    def _add_product_to_cart(self, product: Product) -> None:
        """Agrega o incrementa un producto en el carrito y actualiza la UI.

        Bloquea la operación si no hay stock disponible para la cantidad
        solicitada y muestra un mensaje de error al cajero.

        Args:
            product: Producto a agregar (requiere id asignado — no None).
        """
        if product.id is None:
            self._view.show_error(
                f"Producto sin ID en base de datos: '{product.name}'"
            )
            return

        if product.id in self._cart:
            current_product, current_qty = self._cart[product.id]
            new_qty = current_qty + 1
            if new_qty > product.stock:
                self._view.show_stock_error(
                    f"Sin stock suficiente para '{product.name}'.\n"
                    f"Disponible: {product.stock}, en carrito: {current_qty}."
                )
                return
            self._cart[product.id] = (current_product, new_qty)
        else:
            if product.stock == 0:
                self._view.show_stock_error(
                    f"'{product.name}' no tiene stock disponible."
                )
                return
            self._cart[product.id] = (product, 1)

        _, quantity = self._cart[product.id]
        self._view.show_product_in_cart(product, quantity)
        self._view.update_total(self.get_total())
        self._save_draft()

    def restore_from_draft(self, items: list[tuple[Product, int]]) -> None:
        """Restaura el carrito desde un borrador guardado en disco.

        Llamado desde main.py al inicio si existe un draft previo. Puebla
        el carrito directamente (sin validar stock, ya validado por el
        caso de uso RestoreDraftCart) y refresca la visualización.

        Args:
            items: Lista de ``(Product, quantity)`` validados y con stock
                   disponible, proporcionada por ``RestoreDraftCart.execute()``.
        """
        for product, quantity in items:
            if product.id is not None:
                self._cart[product.id] = (product, quantity)
        if self._cart:
            self._refresh_cart_display()
            self._save_draft()

    def _clear_cart(self) -> None:
        """Limpia el carrito, resetea la UI a estado inicial y borra el borrador."""
        self._cart.clear()
        if self._draft_repo is not None:
            self._draft_repo.clear()
        self._view.clear_cart_display()
        self._view.update_total(Price("0"))

    def _refresh_cart_display(self) -> None:
        """Refresca completamente la tabla del carrito y el total."""
        self._view.clear_cart_display()
        for product, quantity in self._cart.values():
            self._view.show_product_in_cart(product, quantity)
        self._view.update_total(self.get_total())

    def _save_draft(self) -> None:
        """Persiste el estado actual del carrito en el repositorio de borrador.

        No hace nada si no se inyectó un repositorio de borrador (tests o
        instancias sin persistencia).
        """
        if self._draft_repo is not None:
            self._draft_repo.save(
                {pid: qty for pid, (_, qty) in self._cart.items()}
            )
