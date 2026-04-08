"""Router de importación masiva de precios.

Endpoints:
    POST /api/import/preview   — sube archivo, devuelve columnas + preview de filas
    POST /api/import           — ejecuta la importación con mapeo y margen opcionales
    GET  /api/import/status    — estado de la importación en curso
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
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

_PREVIEW_ROWS = 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_temp(content: bytes, suffix: str) -> Path:
    """Guarda bytes en un archivo temporal y retorna su Path."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="pos_import_") as tmp:
        tmp.write(content)
        return Path(tmp.name)


def _validate_extension(filename: str) -> str:
    """Valida que la extensión sea soportada y retorna el suffix en minúsculas."""
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no soportado. Solo CSV, XLSX o XLS.",
        )
    return suffix


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/preview")
async def preview_file(
    file: UploadFile = File(...),
    _auth: dict = Depends(require_admin),
):
    """Carga un archivo y devuelve columnas + filas de preview (sin importar).

    Permite al frontend mostrar el mapeo de columnas antes de confirmar
    la importación.

    Returns:
        ``{columns, preview, total_rows}``
        - ``columns``: lista de nombres de columnas del archivo.
        - ``preview``: primeras N filas como lista de dicts.
        - ``total_rows``: total de filas de datos (sin encabezado).

    Raises:
        HTTPException 400: Si el archivo tiene extensión no soportada.
    """
    filename = file.filename or "archivo"
    suffix = _validate_extension(filename)
    content = await file.read()
    tmp_path = _save_temp(content, suffix)

    try:
        sheet = BulkPriceImporter().load(tmp_path)
        all_rows = list(sheet.iter_rows())
        return {
            "columns": sheet.columns,
            "preview": all_rows[:_PREVIEW_ROWS],
            "total_rows": len(all_rows),
        }
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def start_import(
    file: UploadFile = File(...),
    column_mapping: str = Form("{}"),
    global_margin: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    category_repo: MariaDbCategoryRepository = Depends(get_category_repo),
    _auth: dict = Depends(require_admin),
):
    """Inicia la importación masiva de precios desde un CSV o Excel.

    El archivo se procesa en background. Consultá ``GET /api/import/status``
    para el progreso.

    Args (form-data):
        file: Archivo CSV, XLSX o XLS.
        column_mapping: JSON con el mapeo ``{campo_destino: columna_archivo}``.
            Campos destino: ``barcode``, ``name``, ``net_cost``, ``category``.
            Si no se envía, se usa el nombre de columna del archivo tal cual.
        global_margin: Margen de ganancia porcentual a aplicar a todas las filas.
            Si no se envía, se usa el margen de cada fila o el default (30%).

    Returns:
        HTTP 202 Accepted si la importación se inició correctamente.

    Raises:
        HTTPException 409: Si ya hay una importación en curso.
        HTTPException 400: Si el archivo o el mapping tienen formato inválido.
    """
    global _current_import

    with _import_lock:
        if _current_import.state == "running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya hay una importación en curso. Esperá que termine.",
            )
        _current_import = ImportStatus(state="running")

    filename = file.filename or "archivo"
    suffix = _validate_extension(filename)

    # Parsear column_mapping
    try:
        mapping: dict[str, str] = json.loads(column_mapping) if column_mapping else {}
    except json.JSONDecodeError as exc:
        with _import_lock:
            _current_import = ImportStatus(state="idle")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"column_mapping no es JSON válido: {exc}",
        ) from exc

    # Parsear global_margin
    parsed_margin: Optional[Decimal] = None
    if global_margin is not None and global_margin.strip():
        try:
            parsed_margin = Decimal(global_margin.strip())
        except InvalidOperation as exc:
            with _import_lock:
                _current_import = ImportStatus(state="idle")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"global_margin inválido: '{global_margin}'",
            ) from exc

    content = await file.read()

    def _run_import() -> None:
        global _current_import
        tmp_path: Optional[Path] = None
        try:
            tmp_path = _save_temp(content, suffix)
            importer = BulkPriceImporter()
            sheet = importer.load(tmp_path)
            parse_result = importer.parse_dataframe(
                sheet,
                column_mapping=mapping or None,
                global_margin=parsed_margin,
            )

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
                _current_import = ImportStatus(state="error", error_message=str(exc))
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    threading.Thread(target=_run_import, daemon=True).start()
    return {"detail": "Importación iniciada.", "filename": filename}


@router.get("/status")
def get_import_status():
    """Retorna el estado de la importación en curso o la última completada.

    Returns:
        ``{state, inserted, updated, skipped, error_count, error_message}``
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
