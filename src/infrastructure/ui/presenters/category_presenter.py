"""Presenter de gestión de categorías (patrón MVP).

Lógica de presentación para el CRUD de categorías (solo ADMIN).
Sin dependencias de PySide6: Python puro, completamente testeable.

Responsabilidades:
- Validar nombre antes de guardar.
- Coordinar workers (ListCategoriesWorker, SaveCategoryWorker, DeleteCategoryWorker).
- Notificar a la vista los resultados de cada operación.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from src.domain.models.category import Category


@runtime_checkable
class ICategoryManagementView(Protocol):
    """Interfaz que la vista de gestión de categorías debe implementar."""

    def show_categories(self, categories: list[Category]) -> None:
        """Muestra la lista de categorías en el panel izquierdo.

        Args:
            categories: Lista de categorías a mostrar.
        """
        ...

    def show_loading(self, loading: bool) -> None:
        """Muestra u oculta el indicador de carga.

        Args:
            loading: True para mostrar el spinner, False para ocultarlo.
        """
        ...

    def show_success(self, message: str) -> None:
        """Muestra un mensaje de éxito en el status label.

        Args:
            message: Texto a mostrar.
        """
        ...

    def show_error(self, message: str) -> None:
        """Muestra un mensaje de error en el status label.

        Args:
            message: Texto a mostrar.
        """
        ...

    def clear_form(self) -> None:
        """Limpia el formulario y lo pone en modo 'nueva categoría'."""
        ...

    def set_form_enabled(self, enabled: bool) -> None:
        """Habilita o deshabilita los controles del formulario.

        Args:
            enabled: True para habilitar, False para deshabilitar.
        """
        ...


class CategoryPresenter:
    """Presenter para la vista de gestión de categorías.

    Args:
        view: Instancia que implementa ICategoryManagementView.

    Examples:
        >>> presenter = CategoryPresenter(view)
        >>> presenter.on_view_activated()
    """

    def __init__(self, view: ICategoryManagementView) -> None:
        self._view = view
        self._editing_category: Optional[Category] = None

    # ------------------------------------------------------------------
    # Ciclo de vida de la vista
    # ------------------------------------------------------------------

    def on_view_activated(self) -> None:
        """Carga la lista de categorías al activar la vista."""
        self._view.show_loading(True)
        self._view.clear_form()

    # ------------------------------------------------------------------
    # Callbacks de workers
    # ------------------------------------------------------------------

    def on_categories_loaded(self, categories: list[Category]) -> None:
        """Callback: recibe la lista de categorías desde ListCategoriesWorker.

        Args:
            categories: Lista de categorías cargadas desde la DB.
        """
        self._view.show_loading(False)
        self._view.show_categories(categories)

    def on_category_saved(self, category: Category) -> None:
        """Callback: categoría persistida exitosamente por SaveCategoryWorker.

        Recarga la lista completa para reflejar el cambio.

        Args:
            category: Entidad persistida con id asignado.
        """
        self._editing_category = None
        self._view.show_loading(False)
        self._view.set_form_enabled(True)
        accion = "actualizada" if category.id else "creada"
        self._view.show_success(f"Categoría '{category.name}' {accion} correctamente.")
        self._view.clear_form()

    def on_category_deleted(self, category_id: int) -> None:
        """Callback: categoría eliminada exitosamente por DeleteCategoryWorker.

        Args:
            category_id: ID de la categoría eliminada.
        """
        self._editing_category = None
        self._view.show_loading(False)
        self._view.set_form_enabled(True)
        self._view.show_success("Categoría eliminada. Los productos asociados quedaron sin categoría.")
        self._view.clear_form()

    def on_worker_error(self, message: str) -> None:
        """Callback: error en cualquier worker de categorías.

        Args:
            message: Descripción del error.
        """
        self._view.show_loading(False)
        self._view.set_form_enabled(True)
        self._view.show_error(f"Error: {message}")

    # ------------------------------------------------------------------
    # Acciones de la vista
    # ------------------------------------------------------------------

    def on_new_requested(self) -> None:
        """El usuario presionó 'Nueva categoría': limpia el formulario."""
        self._editing_category = None
        self._view.clear_form()

    def on_category_selected(self, category: Category) -> None:
        """El usuario seleccionó una categoría de la lista para editar.

        Args:
            category: Categoría seleccionada.
        """
        self._editing_category = category

    def on_save_requested(self, name: str) -> Optional[Category]:
        """Valida el nombre y retorna la entidad lista para persistir.

        La vista llama este método antes de lanzar el worker. Si retorna None
        hubo un error de validación y la vista debe abortar el save.

        Args:
            name: Nombre ingresado por el usuario (sin trim).

        Returns:
            ``Category`` lista para ser persistida, o ``None`` si la
            validación falla.
        """
        name = name.strip()
        if not name:
            self._view.show_error("El nombre de la categoría no puede estar vacío.")
            return None
        if len(name) > 100:
            self._view.show_error("El nombre no puede superar 100 caracteres.")
            return None

        if self._editing_category is not None:
            # Modo edición: reutiliza el objeto existente actualizando el nombre
            self._editing_category.name = name
            return self._editing_category

        return Category(name=name)

    def on_delete_requested(self) -> Optional[int]:
        """Retorna el ID de la categoría en edición para que la vista confirme y elimine.

        Returns:
            ID de la categoría seleccionada, o ``None`` si no hay ninguna en edición.
        """
        if self._editing_category is None or self._editing_category.id is None:
            self._view.show_error("Seleccioná una categoría de la lista para eliminar.")
            return None
        return self._editing_category.id

    @property
    def editing_category_name(self) -> str:
        """Nombre de la categoría en edición (para el diálogo de confirmación).

        Returns:
            Nombre de la categoría o cadena vacía si no hay ninguna seleccionada.
        """
        if self._editing_category is not None:
            return self._editing_category.name
        return ""
