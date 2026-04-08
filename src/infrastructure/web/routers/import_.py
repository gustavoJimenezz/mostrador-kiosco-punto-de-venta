"""Router de importación masiva de precios.

Endpoints:
    POST /api/import          — sube un archivo CSV/Excel e inicia la importación
    GET  /api/import/status   — consulta el estado de la importación en curso

La importación corre en un thread background para no bloquear la respuesta HTTP.
El estado se almacena en memoria (único proceso uvicorn --workers 1).
"""

from __future__ import annotations

import logging
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.application.use_cases.update_bulk_prices import ImportResult, UpdateBulkPrices
from src.infrastructure.importers.bulk_price_importer import BulkPriceImporter
from src.infrastructure.persistence.mariadb_category_repository import MariaDbCategoryRepository
from src.infrastructure.web.dependencies import (
    get_category_repo,
    get_session,
    require_admin,
)

router = APIRouter(prefix="/api/import", tags=["import"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Estado en memoria de la importación activa
# ---------------------------------------------------------------------------

@dataclass
class ImportStatus:
    state: Literal["idle", "running", "done", "error"] = "idle"
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    error_count: int = 0
    error_message: Optional[str] = None


_import_lock = threading.Lock()
_current_import = ImportStatus()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def start_import(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    category_repo: MariaDbCategoryRepository = Depends(get_category_repo),
    _auth: dict = Depends(require_admin),
):
    """Inicia la importación masiva de precios desde un CSV o Excel.

    El archivo se guarda en un directorio temporal y se procesa en background.
    Consultá ``GET /api/import/status`` para el progreso.

    Returns:
        HTTP 202 Accepted si la importación se inició correctamente.

    Raises:
        HTTPException 409: Si ya hay una importación en curso.
        HTTPException 400: Si el archivo tiene un formato no soportado.
    """
    global _current_import

    with _import_lock:
        if _current_import.state == "running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya hay una importación en curso. Esperá que termine.",
            )
        _current_import = ImportStatus(state="running")

    # Validar extensión
    filename = file.filename or ""
    if not filename.lower().endswith((".csv", ".xlsx", ".xls")):
        with _import_lock:
            _current_import = ImportStatus(state="idle")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no soportado. Solo CSV, XLSX o XLS.",
        )

    # Guardar en temp y procesar en background
    content = await file.read()
    suffix = Path(filename).suffix

    def _run_import() -> None:
        global _current_import
        tmp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix, prefix="pos_import_"
            ) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)

            parse_result = BulkPriceImporter().parse(tmp_path)

            if not parse_result.valid_rows:
                with _import_lock:
                    _current_import = ImportStatus(
                        state="done",
                        error_count=len(parse_result.errors),
                        error_message="No se encontraron filas válidas en el archivo.",
                    )
                return

            use_case = UpdateBulkPrices(session, category_repo)
            result: ImportResult = use_case.execute(parse_result.valid_rows)

            with _import_lock:
                _current_import = ImportStatus(
                    state="done",
                    inserted=result.inserted,
                    updated=result.updated,
                    skipped=result.skipped,
                    error_count=len(parse_result.errors),
                )

        except Exception as exc:
            logger.exception("Error durante la importación masiva")
            with _import_lock:
                _current_import = ImportStatus(
                    state="error",
                    error_message=str(exc),
                )
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    threading.Thread(target=_run_import, daemon=True).start()

    return {"detail": "Importación iniciada.", "filename": filename}


@router.get("/status")
def get_import_status():
    """Retorna el estado actual de la importación en curso o la última completada.

    Returns:
        ``{state, inserted, updated, skipped, error_count, error_message}``
        donde ``state`` es: ``idle`` | ``running`` | ``done`` | ``error``
    """
    with _import_lock:
        return {
            "state": _current_import.state,
            "inserted": _current_import.inserted,
            "updated": _current_import.updated,
            "skipped": _current_import.skipped,
            "error_count": _current_import.error_count,
            "error_message": _current_import.error_message,
        }
