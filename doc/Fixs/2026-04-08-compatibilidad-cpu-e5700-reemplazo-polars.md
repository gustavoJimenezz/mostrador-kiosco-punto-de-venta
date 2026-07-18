# Fix: Compatibilidad con Intel Core 2 Duo E5700 — Reemplazo de Polars

**Fecha:** 2026-04-08
**Branch:** `feat/36-v2-fastapi-react-sqlite`

---

## Resumen

El servicio `kiosco-pos.service` crasheaba con `signal=ILL` (SIGILL — instrucción
ilegal) al iniciar en el hardware del kiosco (Intel Core 2 Duo E5700, ~2009).
La causa raíz fue que la dependencia `polars` distribuye wheels precompilados con
instrucciones AVX2, que el E5700 no soporta. Se reemplazó Polars por equivalentes
puro Python (`csv` + `openpyxl`) sin pérdida de funcionalidad.

---

## Diagnóstico

### Hardware afectado

| Dato | Valor |
|------|-------|
| CPU | Intel Core 2 Duo E5700 (Wolfdale, 2009) |
| Instrucciones SIMD soportadas | SSE, SSE2, SSE3, SSSE3, SSE4.1 |
| **No soporta** | **SSE4.2, AVX, AVX2, AVX-512** |

### Síntoma observado

```
Process: 10989 ExecStart=...python3 web_main.py
Main PID: 10989 (code=dumped, signal=ILL)
```

El proceso moría 1.8 s después de iniciar — durante la fase de importación de
módulos de Python — antes de servir ninguna request.

### Causa confirmada

`polars 1.39.3` (incluyendo `polars[rtcompat]`) distribuye el wheel
`polars-runtime-compat` compilado con instrucciones **AVX2** (`ymm` registers).
Al importar `import polars as pl`, el kernel lanzaba SIGILL en el primer
intento de ejecutar una instrucción no disponible.

### Otras dependencias analizadas

Se inspeccionaron los binarios nativos del venv con `objdump -d`:

| Librería | Instrucciones detectadas | Estado en E5700 |
|----------|--------------------------|-----------------|
| `polars 1.39.3` | AVX2 (`ymm0–ymm15`) — forzadas en init | **SIGILL confirmado** |
| `pydantic-core` | AVX (`ymm0–ymm15`) — 468 ocurrencias | Funciona: runtime detection |
| `bcrypt` | AVX (`ymm`) | Funciona: runtime detection |
| `openpyxl` | Puro Python | Sin riesgo |
| `fastapi`, `sqlalchemy`, `alembic` | Puro Python | Sin riesgo |

`pydantic-core` y `bcrypt` usan instrucciones AVX pero con detección en tiempo
de ejecución (`is_x86_feature_detected!` en Rust / auto-vectorización opcional en C),
por lo que recaen en paths SSE2 cuando AVX no está disponible.
Polars ejecutaba código AVX incondicionalmente al momento del import.

---

## Solución aplicada

### Principio

Reemplazar Polars por librerías puro Python que cumplen exactamente el mismo
rol — leer CSV y Excel — sin instrucciones SIMD modernas:

| Uso anterior (Polars) | Reemplazo |
|-----------------------|-----------|
| `pl.read_csv(path, infer_schema_length=0)` | `csv.DictReader` (stdlib) |
| `pl.read_excel(path, infer_schema_length=0)` | `openpyxl.load_workbook` |
| `pl.DataFrame` (tipo de retorno) | Clase interna `ImportSheet` |
| `df.columns`, `df.iter_rows(named=True)`, `df.rename()` | Métodos equivalentes en `ImportSheet` |

### Clase `ImportSheet`

Se creó una clase dataclass mínima que replica el subconjunto de la API de
`pl.DataFrame` usado en el proyecto:

```python
@dataclass
class ImportSheet:
    columns: list[str]
    _rows: list[dict[str, str]]

    def iter_rows(self, named=True) -> Iterator[dict[str, str]]: ...
    def rename(self, mapping: dict[str, str]) -> 'ImportSheet': ...

    @classmethod
    def from_dict(cls, data: dict[str, list]) -> 'ImportSheet': ...  # para tests
```

`from_dict` reemplaza `pl.DataFrame({col: [values]})` en los tests unitarios.

### Método `load()` en `BulkPriceImporter`

Se agregó `load(path) -> ImportSheet` para separar la lectura del archivo de
la validación de filas, habilitando el endpoint `/api/import/preview`:

```python
def load(self, file_path) -> ImportSheet:
    """Lee sin validar — útil para preview de columnas."""
    ...

def parse(self, file_path) -> ParseResult:
    """load() + parse_dataframe() — flujo completo."""
    return self.parse_dataframe(self.load(file_path))
```

---

## Cambios en la importación de Excel `.xls`

Para archivos Excel 97-2003 (`.xls`), `openpyxl` no tiene soporte nativo.
Se implementó soporte opcional vía `xlrd` con importación diferida:

```python
def _read_xls(path: Path) -> ImportSheet:
    try:
        import xlrd
    except ImportError:
        raise ImportError("Instalar: poetry add 'xlrd>=1.2,<2.0'")
    ...
```

Si `xlrd` no está instalado el error es claro e instructivo. Para la mayoría
de los casos (`.csv` y `.xlsx`) no se requiere ninguna dependencia extra.

---

## Flujo de importación post-fix

```
Archivo CSV/XLSX/XLS seleccionado por el usuario
        │
        ▼
POST /api/import/preview
        ├─ BulkPriceImporter().load(tmp_path)
        │       ├─ .csv  → csv.DictReader (stdlib)
        │       ├─ .xlsx → openpyxl.load_workbook
        │       └─ .xls  → xlrd (opcional)
        └─ Retorna {columns, preview[100 filas], total_rows}
                │
                ▼
        Frontend: usuario mapea columnas + configura margen
                │
                ▼
POST /api/import  {file, column_mapping (JSON), global_margin}
        ├─ BulkPriceImporter().load(tmp_path)
        ├─ BulkPriceImporter().parse_dataframe(sheet, mapping, margin)
        └─ UpdateBulkPrices(session, category_repo).execute(valid_rows)
                ├─ INSERT masivo (nuevos)
                ├─ UPDATE + historial (cambio de costo)
                └─ SKIP (mismo costo)
```

---

## Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/importers/bulk_price_importer.py` | Reemplazado `import polars` por `csv` + `openpyxl`. Clase `ImportSheet`. Método `load()`. |
| `src/infrastructure/web/routers/import_.py` | Nuevo endpoint `POST /api/import/preview`. Endpoint `POST /api/import` acepta `column_mapping` (JSON) y `global_margin` como form fields. |
| `frontend/src/api/client.ts` | Nuevo método `api.uploadWithData(path, file, data)`. |
| `frontend/src/pages/admin/ImportView.tsx` | Reescrito. Flujo 3 pasos: idle → mapeo con preview → resultado. |
| `tests/unit/importers/test_bulk_importer.py` | 9 ocurrencias `pl.DataFrame({})` → `ImportSheet.from_dict({})`. |
| `pyproject.toml` | `polars >= 0.20.0` → `openpyxl >= 3.1.0`. `uvicorn[standard]` → `uvicorn`. |
| `packaging/build_deb.sh` | Mismo reemplazo en el `pip install` del script de build. |

---

## Notas técnicas

### Por qué `uvicorn[standard]` → `uvicorn`

El extra `[standard]` instala `uvloop` (event loop en C). Aunque `uvloop` no
causó SIGILL en las pruebas, se eliminó preventivamente ya que es innecesario
para un worker único con SQLite y añade una dependencia nativa.

### Compilar pydantic-core para E5700 (alternativa no aplicada)

Si en el futuro `pydantic-core` causara SIGILL (actualmente funciona con
runtime detection), la solución sería compilarlo desde source apuntando a
Core 2 como target de CPU en el `build_deb.sh`:

```bash
RUSTFLAGS="-C target-cpu=core2" \
CFLAGS="-march=core2 -mno-avx -mno-avx2" \
  pip install --no-binary pydantic-core pydantic
```

Esto requiere Rust toolchain y `build-essential` en la PC de build.

### Formato numérico argentino en lectura de Excel

`openpyxl` retorna valores de celda como tipos Python nativos (int, float, str).
El helper `_cell_to_str()` convierte floats enteros a string sin decimal
(`1250.0 → "1250"`) para que el parser de formato argentino funcione
correctamente con ambos formatos.

### Cobertura de tests

Todos los tests existentes pasaron sin modificaciones en la lógica de negocio:
```
34 passed in 0.22s  (tests/unit/importers/)
134 passed in 0.39s (tests/unit/ completo)
```
