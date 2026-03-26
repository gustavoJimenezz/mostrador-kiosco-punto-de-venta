"""Composition Root: punto de entrada de la aplicación POS.

Conecta todas las capas de la arquitectura hexagonal e inicia Qt:
    - Configura el mapeo ORM imperativo.
    - Crea el engine MariaDB y la session_factory.
    - Muestra LoginWindow; si la autenticación es exitosa, abre MainWindow.
    - Instancia todos los Presenters e inyecta dependencias.

La URL de la base de datos se lee de la variable de entorno DATABASE_URL.
Valor por defecto: mysql+pymysql://root:@localhost:3306/kiosco_pos
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication, QDialog

from src.application.use_cases.authenticate_user import AuthenticateUser
from src.application.use_cases.elevate_to_admin import ElevateToAdmin
from src.application.use_cases.restore_draft_cart import RestoreDraftCart
from src.infrastructure.persistence.database import (
    create_mariadb_engine,
    create_session_factory,
)
from src.infrastructure.persistence.json_draft_cart_repository import (
    JsonDraftCartRepository,
)
from src.infrastructure.persistence.mappings import configure_mappings
from src.infrastructure.persistence.mariadb_product_repository import (
    MariadbProductRepository,
)
from src.infrastructure.persistence.mariadb_user_repository import (
    MariadbUserRepository,
)
from src.infrastructure.ui.app_config import configure_high_dpi, get_app_icon
from src.infrastructure.ui.presenters.cash_presenter import CashPresenter
from src.infrastructure.ui.presenters.import_presenter import ImportPresenter
from src.infrastructure.ui.presenters.login_presenter import LoginPresenter
from src.infrastructure.ui.presenters.product_presenter import ProductPresenter
from src.infrastructure.ui.presenters.sale_presenter import SalePresenter
from src.infrastructure.ui.presenters.cash_history_presenter import CashHistoryPresenter
from src.infrastructure.ui.presenters.calendar_presenter import CalendarPresenter
from src.infrastructure.ui.presenters.category_presenter import CategoryPresenter
from src.infrastructure.ui.presenters.sales_history_presenter import SalesHistoryPresenter
from src.infrastructure.ui.presenters.stock_edit_presenter import StockEditPresenter
from src.infrastructure.ui.presenters.stock_inject_presenter import StockInjectPresenter
from src.infrastructure.ui.windows.login_window import LoginWindow
from src.infrastructure.ui.windows.main_window import MainWindow


def main() -> int:
    """Punto de entrada principal de la aplicación.

    Returns:
        Código de salida de la aplicación Qt (0 = normal, != 0 = error).
    """
    load_dotenv()

    # Debe ejecutarse antes de instanciar QApplication.
    configure_high_dpi()

    configure_mappings()

    database_url = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://root:@localhost:3306/kiosco_pos",
    )
    engine = create_mariadb_engine(database_url)
    session_factory = create_session_factory(engine)

    app = QApplication(sys.argv)
    app.setWindowIcon(get_app_icon())

    # --- Fase de autenticación -------------------------------------------
    # Se usa una sesión dedicada para el login. exec() es bloqueante (modal),
    # por lo que la sesión permanece abierta hasta que el usuario se autentica
    # o cierra la ventana.
    with session_factory() as login_session:
        user_repo = MariadbUserRepository(login_session)
        auth_use_case = AuthenticateUser(user_repo)
        login_presenter = LoginPresenter(auth_use_case, user_repo)
        login_window = LoginWindow(login_presenter)
        result = login_window.exec()

    if result != QDialog.DialogCode.Accepted:
        return 0

    # --- Fase principal ---------------------------------------------------
    window = MainWindow(session_factory=session_factory)

    draft_repo = JsonDraftCartRepository()
    presenter = SalePresenter(view=window, draft_repo=draft_repo)
    window.set_presenter(presenter)

    # Restaurar carrito en progreso si existe un borrador (corte de luz, etc.)
    if draft_repo.has_draft():
        with session_factory() as restore_session:
            product_repo = MariadbProductRepository(restore_session)
            restored_items = RestoreDraftCart(draft_repo, product_repo).execute()
            if restored_items:
                presenter.restore_from_draft(restored_items)

    import_presenter = ImportPresenter(window.import_view, session_factory)
    window.import_view.set_presenter(import_presenter)

    product_presenter = ProductPresenter(view=window.product_management_view)
    window.set_product_presenter(product_presenter)

    stock_edit_presenter = StockEditPresenter(view=window.stock_edit_view)
    window.set_stock_edit_presenter(stock_edit_presenter)

    stock_inject_presenter = StockInjectPresenter(view=window.stock_inject_view)
    window.set_stock_inject_presenter(stock_inject_presenter)

    cash_history_presenter = CashHistoryPresenter(view=window.cash_history_view)
    window.set_cash_history_presenter(cash_history_presenter)

    sales_history_presenter = SalesHistoryPresenter(view=window.sales_history_view)
    window.set_sales_history_presenter(sales_history_presenter)

    category_presenter = CategoryPresenter(view=window.category_management_view)
    window.set_category_presenter(category_presenter)

    from pathlib import Path

    _notes_path = Path.home() / ".config" / "kiosco-pos" / "calendar_notes.json"
    calendar_presenter = CalendarPresenter(
        view=window.calendar_view,
        notes_file_path=_notes_path,
    )
    window.set_calendar_presenter(calendar_presenter)

    cash_presenter = CashPresenter(view=window.cash_close_view)
    window.set_cash_presenter(cash_presenter)

    # Caso de uso para desbloquear pestañas admin desde el botón "🔒 Administrador".
    # Usa una sesión dedicada de larga vida (cierra con la app).
    admin_session = session_factory()
    elevate_use_case = ElevateToAdmin(MariadbUserRepository(admin_session))
    window.set_elevate_use_case(elevate_use_case)

    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
