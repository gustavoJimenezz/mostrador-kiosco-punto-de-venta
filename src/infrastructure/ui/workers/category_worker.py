"""Workers QThread para operaciones CRUD de categorías.

Cada worker recibe una ``session_factory`` (callable) en lugar de una
``Session`` porque cada QThread necesita su propia sesión de SQLAlchemy.

Workers disponibles:
    ListCategoriesWorker  — lista todas las categorías.
    SaveCategoryWorker    — persiste (INSERT/UPDATE) una categoría.
    DeleteCategoryWorker  — elimina una categoría por ID.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal

from src.domain.models.category import Category


class ListCategoriesWorker(QThread):
    """Worker que lista todas las categorías ordenadas por nombre.

    Signals:
        categories_loaded (list): Emitida con la lista de ``Category``.
        error_occurred (str): Emitida con mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
        parent: QObject padre (opcional).
    """

    categories_loaded = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, session_factory: Callable, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory

    def run(self) -> None:
        """Ejecuta la consulta de categorías en el hilo separado."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_category_repository import (
                MariaDbCategoryRepository,
            )

            repo = MariaDbCategoryRepository(session)
            categories = repo.list_all()
            self.categories_loaded.emit(categories)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


class SaveCategoryWorker(QThread):
    """Worker que persiste una categoría (INSERT si id es None, UPDATE si tiene id).

    Signals:
        category_saved (Category): Emitida con la entidad persistida (id asignado).
        error_occurred (str): Emitida con mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
        category: Entidad a persistir.
        parent: QObject padre (opcional).
    """

    category_saved = Signal(object)
    error_occurred = Signal(str)

    def __init__(
        self, session_factory: Callable, category: Category, parent=None
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._category = category

    def run(self) -> None:
        """Ejecuta la persistencia de la categoría en el hilo separado."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_category_repository import (
                MariaDbCategoryRepository,
            )

            repo = MariaDbCategoryRepository(session)
            saved = repo.save(self._category)
            session.commit()
            self.category_saved.emit(saved)
        except Exception as exc:
            session.rollback()
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


class DeleteCategoryWorker(QThread):
    """Worker que elimina una categoría por ID.

    Los productos asociados quedan con ``category_id = NULL``
    (restricción ON DELETE SET NULL).

    Signals:
        category_deleted (int): Emitida con el ID de la categoría eliminada.
        error_occurred (str): Emitida con mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
        category_id: PK de la categoría a eliminar.
        parent: QObject padre (opcional).
    """

    category_deleted = Signal(int)
    error_occurred = Signal(str)

    def __init__(
        self, session_factory: Callable, category_id: int, parent=None
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._category_id = category_id

    def run(self) -> None:
        """Ejecuta la eliminación de la categoría en el hilo separado."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_category_repository import (
                MariaDbCategoryRepository,
            )

            repo = MariaDbCategoryRepository(session)
            repo.delete(self._category_id)
            session.commit()
            self.category_deleted.emit(self._category_id)
        except Exception as exc:
            session.rollback()
            self.error_occurred.emit(str(exc))
        finally:
            session.close()
