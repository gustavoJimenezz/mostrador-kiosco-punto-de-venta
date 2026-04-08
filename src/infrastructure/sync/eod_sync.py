"""Sincronización End-of-Day (EOD): SQLite local → MariaDB remoto.

Se ejecuta al cerrar la caja (``POST /api/cash/close``). Toma las ventas del
día del arqueo cerrado y las sincroniza al servidor remoto mediante upsert
idempotente por UUID de venta.

Si el servidor remoto no está disponible, el error se loguea y la operación
de cierre de caja local igual se completa. La tabla ``sync_log`` registra el
estado para reintentos manuales.

Configuración requerida:
    ``REMOTE_DATABASE_URL`` — URL MariaDB del servidor remoto.
    Formato: ``mysql+pymysql://user:pass@host:3306/kiosco_pos``

Uso:
    EodSync(remote_url="mysql+pymysql://...").sync(cash_close_id=5)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

_DEFAULT_SQLITE_PATH = Path.home() / ".local" / "share" / "kiosco-pos" / "pos.db"


class EodSync:
    """Sincroniza las ventas de un arqueo de caja al servidor MariaDB remoto.

    Args:
        remote_url: URL de conexión al MariaDB remoto.
        local_url: URL de la DB SQLite local. Por defecto usa la ruta estándar.
    """

    def __init__(
        self,
        remote_url: str,
        local_url: str | None = None,
    ) -> None:
        local = local_url or os.environ.get(
            "DATABASE_URL",
            f"sqlite:///{_DEFAULT_SQLITE_PATH}",
        )
        self._local_engine = create_engine(local, connect_args={"check_same_thread": False})
        self._remote_engine = create_engine(remote_url, pool_pre_ping=True, pool_recycle=3600)
        self._LocalSession = sessionmaker(bind=self._local_engine)
        self._RemoteSession = sessionmaker(bind=self._remote_engine)

    def sync(self, cash_close_id: int) -> None:
        """Sincroniza todas las ventas del arqueo ``cash_close_id`` al remoto.

        Operación idempotente: si una venta con el mismo UUID ya existe en el
        remoto, se omite (no se duplica). Esto protege contra dobles envíos en
        caso de reintentos.

        Args:
            cash_close_id: ID del arqueo de caja ya cerrado a sincronizar.
        """
        logger.info("Iniciando sync EOD para cash_close_id=%s", cash_close_id)
        started_at = datetime.now()

        try:
            sales = self._fetch_local_sales(cash_close_id)
            if not sales:
                logger.info("No hay ventas que sincronizar para cash_close_id=%s", cash_close_id)
                self._log_sync(cash_close_id, "done", len(sales), started_at)
                return

            synced = self._upsert_remote_sales(sales)
            logger.info(
                "Sync EOD completado: %d ventas enviadas al remoto (cash_close_id=%s)",
                synced, cash_close_id,
            )
            self._log_sync(cash_close_id, "done", synced, started_at)

        except Exception as exc:
            logger.exception("Sync EOD falló para cash_close_id=%s", cash_close_id)
            self._log_sync(cash_close_id, "error", 0, started_at, str(exc))
            raise

    def _fetch_local_sales(self, cash_close_id: int) -> list[dict]:
        """Lee todas las ventas del arqueo desde SQLite local.

        Returns:
            Lista de dicts con los datos de ventas e ítems.
        """
        with self._LocalSession() as session:
            rows = session.execute(
                text("""
                    SELECT
                        s.id,
                        s.timestamp,
                        s.total_amount,
                        s.payment_method,
                        s.cash_close_id,
                        si.product_id,
                        si.quantity,
                        si.price_at_sale
                    FROM sales s
                    JOIN sale_items si ON si.sale_id = s.id
                    WHERE s.cash_close_id = :ccid
                    ORDER BY s.id, si.id
                """),
                {"ccid": cash_close_id},
            ).fetchall()

        # Agrupar ítems por venta
        sales_map: dict[str, dict] = {}
        for row in rows:
            sale_id = row[0]
            if sale_id not in sales_map:
                sales_map[sale_id] = {
                    "id": row[0],
                    "timestamp": row[1],
                    "total_amount": row[2],
                    "payment_method": row[3],
                    "cash_close_id": row[4],
                    "items": [],
                }
            sales_map[sale_id]["items"].append({
                "product_id": row[5],
                "quantity": row[6],
                "price_at_sale": row[7],
            })

        return list(sales_map.values())

    def _upsert_remote_sales(self, sales: list[dict]) -> int:
        """Inserta las ventas en el MariaDB remoto, omitiendo las ya existentes.

        Usa INSERT IGNORE para idempotencia: si el UUID ya existe, no falla ni
        duplica.

        Returns:
            Cantidad de ventas efectivamente insertadas.
        """
        synced = 0

        with self._RemoteSession() as session:
            for sale in sales:
                # Verificar si la venta ya existe (idempotencia por UUID)
                exists = session.execute(
                    text("SELECT 1 FROM sales WHERE id = :id"),
                    {"id": sale["id"]},
                ).fetchone()

                if exists:
                    logger.debug("Venta %s ya existe en remoto, omitiendo.", sale["id"])
                    continue

                # INSERT cabecera
                session.execute(
                    text("""
                        INSERT INTO sales (id, timestamp, total_amount, payment_method, cash_close_id)
                        VALUES (:id, :ts, :total, :method, :ccid)
                    """),
                    {
                        "id": sale["id"],
                        "ts": sale["timestamp"],
                        "total": sale["total_amount"],
                        "method": sale["payment_method"],
                        "ccid": sale["cash_close_id"],
                    },
                )

                # INSERT ítems
                for item in sale["items"]:
                    session.execute(
                        text("""
                            INSERT INTO sale_items (sale_id, product_id, quantity, price_at_sale)
                            VALUES (:sale_id, :product_id, :qty, :price)
                        """),
                        {
                            "sale_id": sale["id"],
                            "product_id": item["product_id"],
                            "qty": item["quantity"],
                            "price": item["price_at_sale"],
                        },
                    )

                synced += 1

            session.commit()

        return synced

    def _log_sync(
        self,
        cash_close_id: int,
        status: str,
        records_synced: int,
        started_at: datetime,
        error_msg: str | None = None,
    ) -> None:
        """Registra el resultado del sync en la tabla local ``sync_log``.

        La tabla se crea si no existe (no depende de Alembic para ser liviana).
        """
        try:
            with self._LocalSession() as session:
                session.execute(
                    text("""
                        CREATE TABLE IF NOT EXISTS sync_log (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            cash_close_id INTEGER NOT NULL,
                            sync_type TEXT NOT NULL DEFAULT 'eod',
                            status TEXT NOT NULL,
                            records_synced INTEGER NOT NULL DEFAULT 0,
                            attempted_at TEXT NOT NULL,
                            completed_at TEXT,
                            error_msg TEXT
                        )
                    """)
                )
                session.execute(
                    text("""
                        INSERT INTO sync_log
                            (cash_close_id, status, records_synced, attempted_at, completed_at, error_msg)
                        VALUES
                            (:ccid, :status, :records, :started, :completed, :error)
                    """),
                    {
                        "ccid": cash_close_id,
                        "status": status,
                        "records": records_synced,
                        "started": started_at.isoformat(),
                        "completed": datetime.now().isoformat(),
                        "error": error_msg,
                    },
                )
                session.commit()
        except Exception:
            logger.exception("No se pudo registrar el resultado del sync en sync_log")
