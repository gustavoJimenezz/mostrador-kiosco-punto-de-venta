"""Workers QThread para operaciones CRUD de productos.

Cada worker recibe una ``session_factory`` (callable) en lugar de una
``Session`` porque cada QThread necesita su propia sesión de SQLAlchemy.

Workers disponibles:
    ListAllProductsWorker — lista todos los productos del catálogo.
    LoadProductWorker     — carga un producto + lista de categorías disponibles.
    SaveProductWorker     — persiste (INSERT/UPDATE) un producto.
    DeleteProductWorker   — elimina un producto por ID.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal


class ListAllProductsWorker(QThread):
    """Worker que lista todos los productos del catálogo.

    Signals:
        products_loaded (list): Emitida con la lista de ``Product``.
        error_occurred (str): Emitida con mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
        parent: QObject padre (opcional).
    """

    products_loaded = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, session_factory: Callable, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory

    def run(self) -> None:
        """Ejecuta la consulta de todos los productos en el hilo separado."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_product_repository import (
                MariadbProductRepository,
            )

            repo = MariadbProductRepository(session)
            products = repo.list_all()
            self.products_loaded.emit(products)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


class LoadProductWorker(QThread):
    """Worker que carga un producto por ID junto con las categorías disponibles.

    Emite ``product_loaded`` con un dict ``{"product": Product, "categories": [Category]}``.

    Signals:
        product_loaded (object): Emitida con el dict ``{product, categories}``.
        error_occurred (str): Emitida con mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
        product_id: ID del producto a cargar.
        parent: QObject padre (opcional).
    """

    product_loaded = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, session_factory: Callable, product_id: int, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._product_id = product_id

    def run(self) -> None:
        """Carga el producto y las categorías en el hilo separado."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_category_repository import (
                MariaDbCategoryRepository,
            )
            from src.infrastructure.persistence.mariadb_product_repository import (
                MariadbProductRepository,
            )

            product_repo = MariadbProductRepository(session)
            category_repo = MariaDbCategoryRepository(session)
            product = product_repo.get_by_id(self._product_id)
            categories = category_repo.list_all()
            self.product_loaded.emit({"product": product, "categories": categories})
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


class SaveProductWorker(QThread):
    """Worker que persiste (INSERT o UPDATE) un producto.

    Signals:
        save_completed (object): Emitida con el ``Product`` guardado.
        error_occurred (str): Emitida con mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
        product: Entidad ``Product`` a persistir.
        parent: QObject padre (opcional).
    """

    save_completed = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, session_factory: Callable, product, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._product = product

    def run(self) -> None:
        """Persiste el producto y hace commit en el hilo separado."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_product_repository import (
                MariadbProductRepository,
            )

            repo = MariadbProductRepository(session)
            saved = repo.save(self._product)
            session.commit()
            self.save_completed.emit(saved)
        except Exception as exc:
            session.rollback()
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


class DeleteProductWorker(QThread):
    """Worker que elimina un producto por ID.

    Signals:
        delete_completed (): Emitida cuando la eliminación fue exitosa.
        error_occurred (str): Emitida con mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
        product_id: ID del producto a eliminar.
        parent: QObject padre (opcional).
    """

    delete_completed = Signal()
    error_occurred = Signal(str)

    def __init__(self, session_factory: Callable, product_id: int, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._product_id = product_id

    def run(self) -> None:
        """Elimina el producto y hace commit en el hilo separado."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_product_repository import (
                MariadbProductRepository,
            )

            repo = MariadbProductRepository(session)
            repo.delete(self._product_id)
            session.commit()
            self.delete_completed.emit()
        except Exception as exc:
            session.rollback()
            self.error_occurred.emit(str(exc))
        finally:
            session.close()
