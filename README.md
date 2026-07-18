# Mostrador Kiosco — Punto de Venta


### Logs y diagnóstico

La aplicación escribe un log con rotación diaria (7 días de historial):

```bash
# Ver el log en tiempo real
tail -f ~/.local/share/kiosco-pos/pos.log

# Activar modo debug para más detalle
POS_LOG_LEVEL=DEBUG /usr/bin/POS
```

### Credenciales por defecto

| Campo | Valor |
|-------|-------|
| Usuario | `Administrador` |
| PIN | `1234` |


> La base de datos y el archivo `/etc/pos/config.ini` **no se eliminan** al desinstalar para preservar los datos del negocio.

---

## Modo desarrollo

# Instalar dependencias

```bash
# Python y Poetry
sudo apt install python3.12 python3-pip pipx
pipx install poetry

# Activar entorno
poetry shell

# Requiere Docker corriendo para la base de datos.
# Configurar variables de entorno

DB_ROOT_PASSWORD=
DB_NAME=
DB_PORT=
DATABASE_URL="mysql+pymysql://root:root@localhost:3306/kiosco_pos"
```

**Base de datos**
```bash
docker compose up --build -d

# Aplicar migraciones (correr tambien si hay cambios de esquema)
poetry run alembic upgrade head
```

** Backend **
```bash
poetry run python3 web_main.py
```

** Frontend **
```bash
cd frontend
npm install
npm run dev

http://localhost:5173/
```

La app queda disponible en:
- Frontend (con hot-reload): `http://localhost:5173`
- Backend API: `http://localhost:8000`

---

> Docker se usa solo para levantar MariaDB en desarrollo. En producción se instala MariaDB nativo junto con la app.



---

## Credenciales por defecto

Al ejecutar `alembic upgrade head` se crea automáticamente un usuario administrador:

| Campo | Valor |
|-------|-------|
| Usuario | `Administrador` |
| PIN | `1234` |
| Rol | Admin (acceso completo) |

> **Importante:** Cambiar el PIN desde Configuración → Usuarios tras el primer inicio.

---

## Tests

```bash
# Unitarios (sin DB)
poetry run pytest tests/ -m "not integration" -v

# Con cobertura del dominio
poetry run pytest tests/domain/ tests/unit/ --cov=src/domain --cov-report=term-missing

# Integración (requiere MariaDB)
POS_TEST_DB_URL="mysql+pymysql://root:root@localhost:3306/kiosco_test" \
  poetry run pytest -m integration -v
```

---

## Atajos de teclado

| Tecla | Acción |
|-------|--------|
| `F1` | Nueva venta |
| `F2` | Buscar por nombre |
| `F4` | Confirmar venta / Cobrar |
| `F10` | Cierre de caja *(próximamente)* |
| `Esc` | Cancelar búsqueda |
| `Enter` | Confirmar / buscar barcode |

---

| Historial de caja | `CashHistoryView` |

> La pestaña principal (venta) no es recargable porque su layout proviene de un archivo `.ui`.

**Limitación:** no recarga dependencias transitivas. Si el cambio está en un widget importado por la vista, reiniciar la aplicación.

### Cómo eliminar esta funcionalidad antes de producción

Todo el código de hot-reload está marcado con la etiqueta `[DEV_ONLY]`. Para ubicar y eliminar todos los puntos:

```bash
grep -rn "\[DEV_ONLY\]" src/
```

Archivos afectados: `src/infrastructure/ui/windows/main_window.py`

Elementos a eliminar:
- `import importlib` (línea marcada con `[DEV_ONLY]`)
- Línea `self._tab_import = tab_import` en `_load_ui()`
- Líneas `self._*_presenter = presenter` en cada setter `set_*_presenter()`
- Línea del shortcut `Ctrl+R` en `_setup_shortcuts()`
- Bloque completo delimitado por los comentarios `[DEV_ONLY]` (clase `_DEV_RELOAD_MAP` + método `_dev_reload_view()`)



## version offline
Sistema POS offline-first para kioscos en Argentina. Soporta operación sin internet, historial de precios y navegación keyboard-first (F1-F12).

> **Descargar instalador (Windows):** [Releases → Instalar_Kiosco_POS.exe](https://github.com/gustavoJimenezz/mostrador-kiosco-punto-de-venta/releases)
>
> **Descargar instalador (Ubuntu/Linux):** [Releases → kiosco-pos_1.0.0_amd64.deb](https://github.com/gustavoJimenezz/mostrador-kiosco-punto-de-venta/releases)

---

## Instalación en Ubuntu 22.04 / 24.04 LTS

### Requisitos del sistema

| Requisito | Detalle |
|-----------|---------|
| Sistema operativo | Ubuntu 22.04 LTS o 24.04 LTS (amd64) |
| Acceso | Usuario con `sudo` |
| Internet | Necesario solo durante la instalación (para descargar dependencias) |
| Espacio en disco | ~500 MB (app + MariaDB) |

No es necesario instalar nada manualmente. El paquete `.deb` instala y configura todo automáticamente.

### Instalación

```bash
# 1. Instalar el paquete
sudo dpkg -i kiosco-pos_1.0.0_amd64.deb

# 2. Si dpkg reporta dependencias faltantes, resolverlas con:
sudo apt-get install -f
```

El instalador configura automáticamente:
- MariaDB con la base de datos `kiosco_pos` y el usuario `pos`
- El esquema completo de tablas
- Permisos para impresora térmica USB (`/dev/usb/lp0`)
- Entrada en el menú de aplicaciones (GNOME/KDE)

### Abrir la aplicación

Desde el menú de aplicaciones buscando **Kiosco POS**, o desde terminal:

```bash
/usr/bin/POS
```

### Desinstalar

```bash
sudo dpkg -r kiosco-pos
```