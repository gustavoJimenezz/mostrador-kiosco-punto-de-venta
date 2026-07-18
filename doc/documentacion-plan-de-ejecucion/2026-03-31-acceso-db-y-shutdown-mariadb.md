# Acceso a la Base de Datos y Shutdown de MariaDB

**Fecha:** 2026-03-31

---

## 1. Cómo ver las tablas de la base de datos

### Requisito previo

`mysqld.exe` debe estar corriendo. Esto ocurre automáticamente al abrir `POS.exe`. Sin el POS abierto, MariaDB no está activo.

### Por terminal (cliente incluido en el bundle)

```bat
REM Desde la carpeta de instalación (C:\Program Files\Kiosco POS\)
vendor\mariadb\bin\mysql.exe -u root -h 127.0.0.1 -P 3306 kiosco_pos
```

Comandos útiles dentro del cliente:

```sql
-- Ver todas las tablas
SHOW TABLES;

-- Ver estructura de una tabla
DESCRIBE products;
DESCRIBE sales;

-- Consultas de ejemplo
SELECT * FROM products LIMIT 20;
SELECT * FROM sales ORDER BY timestamp DESC LIMIT 10;
SELECT * FROM price_history WHERE product_id = 1;
```

### Con interfaz gráfica (recomendado)

| Herramienta | Plataforma | Descarga |
|---|---|---|
| **DBeaver Community** | Windows/Mac/Linux | dbeaver.io |
| **HeidiSQL** | Windows | heidisql.com |
| **TablePlus** | Windows/Mac | tableplus.com (versión free limitada) |

**Datos de conexión** (idénticos en todas las herramientas):

```
Tipo:       MySQL / MariaDB
Host:       127.0.0.1
Puerto:     3306
Usuario:    root
Contraseña: (vacía)
Base de datos: kiosco_pos
```

### Esquema de tablas actuales

| Tabla | Descripción |
|---|---|
| `users` | Operadores del sistema (autenticación por PIN bcrypt) |
| `categories` | Categorías de productos (Golosinas, Bebidas, etc.) |
| `products` | Catálogo: código de barras, nombre, costo, margen, stock |
| `sales` | Cabecera de venta (UUID, timestamp, total, medio de pago) |
| `sale_items` | Ítems de venta — incluye `price_at_sale` (inmutable) |
| `cash_closes` | Arqueos de caja diarios |
| `cash_movements` | Movimientos manuales de caja (ingresos/egresos) |
| `price_history` | Historial de cambios de costo por producto |

Los archivos físicos de datos están en:
```
{carpeta_instalacion}\vendor\mariadb\data\kiosco_pos\
```

---

## 2. Problema: mysqld.exe no se detiene al cerrar el POS

### Estado actual

`MainWindow.closeEvent()` llama a `_shutdown_database()`, que intenta invocar `self._db_launcher.stop()`. Sin embargo, hay **dos gaps en la implementación**:

1. **`_db_launcher` nunca se inyecta** en `MainWindow` desde `main.py`. El `hasattr` siempre evalúa `False`, por lo que el shutdown nunca se ejecuta.
2. **`DatabaseLauncher` no existe como clase** — `database_launcher.py` solo expone funciones sueltas (`launch_mariadb`, `_start_mysqld`, etc.), sin método `stop()`.

**Consecuencia:** `mysqld.exe` queda corriendo como proceso huérfano después de cerrar el POS. Solo se detiene cuando `backup_daily.bat` lo mata a las 02:00 AM, o al reiniciar la PC.

### Plan de implementación

#### Paso 1 — Convertir `database_launcher.py` en clase con estado

Refactorizar las funciones sueltas en una clase `DatabaseLauncher` que guarda la referencia al `subprocess.Popen`:

```python
class DatabaseLauncher:
    def __init__(self, vendor_path: Path, config_path: Path):
        self._vendor_path = vendor_path
        self._config_path = config_path
        self._process: subprocess.Popen | None = None  # referencia al mysqld iniciado

    def launch(self, connection_url: str | None = None) -> bool:
        """Inicia mysqld si es necesario y verifica la conexión. Retorna True si OK."""
        ...
        # Guardar referencia SOLO si fue este launcher quien inició el proceso
        self._process = subprocess.Popen(...)
        ...

    def stop(self) -> None:
        """Detiene mysqld de forma limpia si fue iniciado por esta instancia."""
        if self._process is None:
            return
        # mysqladmin es el shutdown limpio; evita corrupción de tablas
        mysqladmin = self._vendor_path / "bin" / "mysqladmin.exe"
        if mysqladmin.exists():
            subprocess.run(
                [str(mysqladmin), "-u", "root", "--host=127.0.0.1", "shutdown"],
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            # Fallback: terminate + espera
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
```

**Por qué `mysqladmin shutdown` y no `terminate()`:**
MariaDB escribe páginas en cache antes de cerrarse. Un `terminate()` / `SIGTERM` puede dejar el directorio `data/` en estado inconsistente y requerir una recuperación (`innodb_force_recovery`) al próximo arranque. `mysqladmin shutdown` envía la señal de cierre limpio al servidor a través del protocolo MySQL.

**Importante:** `self._process` solo debe guardarse si **este launcher inició** el proceso. Si `mysqld.exe` ya estaba corriendo antes de abrir el POS (iniciado por otra instancia o manualmente), no se lo debe matar al cerrar.

#### Paso 2 — Actualizar `main.py`

```python
# Instanciar la clase en lugar de llamar la función
launcher = DatabaseLauncher(vendor_path=_VENDOR_PATH, config_path=_CONFIG_PATH)
db_ready = launcher.launch(connection_url=database_url)
if not db_ready:
    ...
    return 1

# ... código existente ...

window = MainWindow(session_factory=session_factory)
window.set_db_launcher(launcher)  # inyección de dependencia
```

#### Paso 3 — Agregar `set_db_launcher()` en `MainWindow`

```python
def set_db_launcher(self, launcher: DatabaseLauncher) -> None:
    """Inyecta el launcher para poder detener MariaDB al cerrar la ventana."""
    self._db_launcher = launcher
```

El método `_shutdown_database()` ya existe y ya llama `self._db_launcher.stop()` — no requiere cambios.

### Archivos afectados

| Archivo | Cambio |
|---|---|
| `src/infrastructure/database_launcher.py` | Refactorizar a clase `DatabaseLauncher` con métodos `launch()` y `stop()` |
| `src/main.py` | Instanciar `DatabaseLauncher`, inyectarlo en `MainWindow` |
| `src/infrastructure/ui/windows/main_window.py` | Agregar método `set_db_launcher()` |
| `tests/unit/infrastructure/test_database_launcher.py` | Actualizar tests existentes a la nueva interfaz de clase |

### Consideración para el backup diario

El script `backup_daily.bat` mata `mysqld.exe` con `taskkill /f` para copiar los datos. Esto es correcto para el backup, pero si el POS está abierto en ese momento, la app quedará sin base de datos hasta el próximo arranque.

**Recomendación a futuro:** coordinar el backup con una señal al POS (archivo flag, named pipe, o registro de Windows) para que el POS cierre la conexión limpiamente antes de que el backup mate el proceso.
