"""Composition Root: punto de entrada de la aplicación POS.

Conecta todas las capas de la arquitectura hexagonal e inicia Qt:
    - Configura el mapeo ORM imperativo.
    - Crea el engine MariaDB y la session_factory.
    - Instancia MainWindow y SalePresenter.
    - Inyecta dependencias (constructor injection).

La URL de la base de datos se lee de la variable de entorno DATABASE_URL.
Valor por defecto: mysql+pymysql://root:@localhost:3306/kiosco_pos
"""

from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication

from src.infrastructure.persistence.database import (
    create_mariadb_engine,
    create_session_factory,
)
from src.infrastructure.persistence.mappings import configure_mappings
from src.infrastructure.ui.presenters.sale_presenter import SalePresenter
from src.infrastructure.ui.windows.main_window import MainWindow


def main() -> int:
    """Punto de entrada principal de la aplicación.

    Returns:
        Código de salida de la aplicación Qt (0 = normal, != 0 = error).
    """
    configure_mappings()

    database_url = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://root:@localhost:3306/kiosco_pos",
    )
    engine = create_mariadb_engine(database_url)
    session_factory = create_session_factory(engine)

    app = QApplication(sys.argv)

    window = MainWindow(session_factory=session_factory)
    presenter = SalePresenter(view=window)
    window.set_presenter(presenter)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
