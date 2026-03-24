"""Workers QThread para operaciones de base de datos.

Evita bloquear el hilo principal de Qt. Crítico para el lector de barras:
si el hilo principal se bloquea 100ms durante una búsqueda, el scanner
puede perder caracteres del siguiente código.

Cada worker recibe una ``session_factory`` (callable) en lugar de una
``Session`` porque cada QThread necesita su propia sesión de SQLAlchemy —
compartir sesiones entre hilos no es seguro.

Uso típico::

    worker = SearchByBarcodeWorker(session_factory, barcode)
    worker.product_found.connect(presenter.on_barcode_found)
    worker.not_found.connect(presenter.on_barcode_not_found)
    worker.error_occurred.connect(presenter.on_search_error)
    worker.start()

Workers disponibles:
    SearchByBarcodeWorker — búsqueda por código de barras.
    SearchByNameWorker    — búsqueda FullText por nombre.
    ProcessSaleWorker     — procesamiento atómico de venta.
    ImportWorker          — re-exportado desde import_worker.py (backward compat).
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QThread, Signal

from src.application.use_cases.get_product_by_code import GetProductByCode
from src.application.use_cases.process_sale import ProcessSale
from src.domain.models.product import Product
from src.domain.models.sale import PaymentMethod, Sale


class SearchByBarcodeWorker(QThread):
    """Worker para búsqueda de producto por código de barras.

    Emite ``product_found`` si encuentra el producto, ``not_found`` si no
    existe en el catálogo, o ``error_occurred`` ante cualquier excepción.

    Signals:
        product_found (Product): Emitida con el producto encontrado.
        not_found (str): Emitida con el barcode si no se encontró.
        error_occurred (str): Emitida con mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
        barcode: Código de barras a buscar.
        parent: QObject padre (opcional).
    """

    product_found = Signal(object)
    not_found = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        session_factory: Callable,
        barcode: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._barcode = barcode

    def run(self) -> None:
        """Ejecuta la búsqueda por barcode en el hilo separado."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_product_repository import (
                MariadbProductRepository,
            )

            repo = MariadbProductRepository(session)
            uc = GetProductByCode(repo)
            product = uc.execute(self._barcode)

            if product is not None:
                self.product_found.emit(product)
            else:
                self.not_found.emit(self._barcode)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


class SearchByNameWorker(QThread):
    """Worker para búsqueda de productos por nombre (FullText MariaDB).

    Signals:
        results_ready (list): Emitida con la lista de Products encontrados.
        error_occurred (str): Emitida con mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
        query: Texto parcial del nombre a buscar.
        parent: QObject padre (opcional).
    """

    results_ready = Signal(list)
    error_occurred = Signal(str)

    def __init__(
        self,
        session_factory: Callable,
        query: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._query = query

    def run(self) -> None:
        """Ejecuta la búsqueda por nombre en el hilo separado."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_product_repository import (
                MariadbProductRepository,
            )

            repo = MariadbProductRepository(session)
            results = repo.search_by_name(self._query)
            self.results_ready.emit(results)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


class ProcessSaleWorker(QThread):
    """Worker para procesar y persistir una venta de forma atómica.

    Signals:
        sale_completed (Sale): Emitida con la venta persistida.
        error_occurred (str): Emitida con mensaje de error.

    Args:
        session_factory: Callable que retorna una nueva Session de SQLAlchemy.
        cart: Diccionario ``{product_id: (Product, quantity)}``.
        payment_method: Método de pago seleccionado por el cajero.
        cash_close_id: ID del arqueo de caja activo (para vincular la venta).
        parent: QObject padre (opcional).
    """

    sale_completed = Signal(object)
    error_occurred = Signal(str)

    def __init__(
        self,
        session_factory: Callable,
        cart: dict,
        payment_method: PaymentMethod,
        cash_close_id: Optional[int] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._cart = cart
        self._payment_method = payment_method
        self._cash_close_id = cash_close_id

    def run(self) -> None:
        """Ejecuta el procesamiento de la venta en el hilo separado."""
        session = self._session_factory()
        try:
            from src.infrastructure.persistence.mariadb_product_repository import (
                MariadbProductRepository,
            )
            from src.infrastructure.persistence.mariadb_sale_repository import (
                MariadbSaleRepository,
            )

            product_repo = MariadbProductRepository(session)
            sale_repo = MariadbSaleRepository(session)
            uc = ProcessSale(sale_repo, product_repo)
            sale = uc.execute(self._cart, self._payment_method, self._cash_close_id)
            self.sale_completed.emit(sale)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            session.close()


# Re-exportado para backward compatibility con import_dialog.py (flujo legacy F9 modal).
# La implementación real con column_mapping vive en import_worker.py.
from src.infrastructure.ui.workers.import_worker import ImportWorker as ImportWorker  # noqa: F401, E501
