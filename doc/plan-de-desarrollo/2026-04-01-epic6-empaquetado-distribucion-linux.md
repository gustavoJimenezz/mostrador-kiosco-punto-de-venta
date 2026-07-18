# Epic 6: Empaquetado y Distribución para Ubuntu/Linux (.deb)

**Fecha:** 2026-04-01

## Resumen

Implementación completa del pipeline de distribución nativa para Ubuntu 22.04/24.04 LTS.
Se agregaron los adaptadores de hardware Linux (impresión térmica vía CUPS), la abstracción
cross-platform en el Composition Root, el script de compilación Nuitka para Linux, y la
infraestructura completa de empaquetado `.deb` con validación automatizada en Docker.

---

## Cambios Principales

- **Adaptador CUPS** (`cups_printer_adapter.py`): impresión térmica ESC/POS sin dependencias externas, usando el comando `lp` del sistema.
- **Factory cross-platform** (`infrastructure/hardware/__init__.py`): selección automática del adaptador correcto según `sys.platform` en runtime.
- **Script de compilación** (`scripts/build_linux.sh`): compila el proyecto con Nuitka en modo standalone u onefile para Linux/Ubuntu.
- **Paquete `.deb`** (`packaging/deb/`): estructura completa con metadatos, scripts de instalación/desinstalación e integración de escritorio.
- **Script `postinst`**: inicialización idempotente de MariaDB (crea DB, usuario, corre migraciones Alembic), permisos de impresora (grupo `lp`, reglas `udev`).
- **Pipeline de testing** (`scripts/test_deb.sh` + `packaging/Dockerfile.test`): validación end-to-end en Ubuntu limpio usando Docker.
- **Tests unitarios** (`tests/unit/infrastructure/test_hardware_adapters.py`): cobertura completa de `CupsPrinterAdapter`, `NullPrinterAdapter` y la factory sin hardware real.
- **Documentación** (`doc/compatibilidad-linux.md`): versiones probadas y decisión standalone vs onefile.

---

## Dependencias Necesarias

### En la máquina de desarrollo (Ubuntu 22.04+)

```bash
# Python y Poetry
sudo apt install python3.12 python3-pip pipx
pipx install poetry

# Compilación con Nuitka
sudo apt install gcc patchelf ccache
poetry add nuitka --group dev

# Empaquetado .deb
sudo apt install dpkg-dev lintian

# Testing en Docker
sudo apt install docker.io
sudo usermod -aG docker $USER  # reiniciar sesión después
```

### En producción (máquina del cliente — Ubuntu 22.04/24.04)

Declaradas en `packaging/deb/DEBIAN/control` como `Depends:`, se instalan automáticamente con `apt-get install -f`:

| Paquete | Versión mínima | Propósito |
|---------|---------------|-----------|
| `mariadb-server` | >= 10.6 | Motor de base de datos |
| `libqt6widgets6` | >= 6.2 | Interfaz gráfica Qt |
| `cups` | cualquiera | Impresión térmica vía `lp` |
| `python3-alembic` | cualquiera | Migraciones de schema DB |
| `adduser` | cualquiera | Creación del usuario del sistema `pos` |

### Dependencias Python del proyecto

Gestionadas por Poetry (`pyproject.toml`):

| Paquete | Versión | Uso |
|---------|---------|-----|
| `pyside6` | 6.10.2 | UI Qt (ventanas, widgets) |
| `sqlalchemy` | 2.0.48 | ORM con mapeo imperativo |
| `pymysql` | 1.1.2 | Driver MariaDB para SQLAlchemy |
| `alembic` | 1.18.4 | Migraciones de base de datos |
| `pydantic` | 2.12.5 | Validación en capa de aplicación |
| `polars` | 1.38.1 | Importación masiva de productos (Excel) |
| `python-dotenv` | 1.2.2 | Variables de entorno desde `.env` |

---

## Flujo de Trabajo Completo

```
[Código fuente]
      │
      ▼
[1. Compilar]  bash scripts/build_linux.sh
      │          └─ Nuitka → C++ → binario ELF
      │          └─ Salida: dist/main.dist/POS  (standalone)
      │                     dist/POS            (onefile)
      ▼
[2. Empaquetar]  bash scripts/package_deb.sh
      │            └─ Copia binario a packaging/deb/usr/bin/POS
      │            └─ dpkg-deb → kiosco-pos_1.0.0_amd64.deb
      │            └─ lintian valida el paquete
      ▼
[3. Testear]  bash scripts/test_deb.sh --ubuntu-version 22.04
      │          └─ Docker: imagen ubuntu:22.04 limpia
      │          └─ Instala el .deb (dpkg -i + apt-get install -f)
      │          └─ Smoke tests: binario, config, MariaDB, SELECT 1, UI
      ▼
[4. Distribuir]  sudo dpkg -i dist/kiosco-pos_1.0.0_amd64.deb
                   └─ postinst: MariaDB DB + usuario + Alembic + udev
                   └─ App disponible en /usr/bin/POS y menú GNOME/KDE
```

### Detalle de cada paso

**Paso 1 — Compilar**

```bash
bash scripts/build_linux.sh              # standalone (default, recomendado para HDD)
bash scripts/build_linux.sh --onefile    # binario único (recomendado para SSD)
```

Lee la configuración desde `build_config.py`. Requiere `gcc`, `patchelf` y `ccache` instalados.

**Paso 2 — Empaquetar**

```bash
bash scripts/package_deb.sh             # standalone
bash scripts/package_deb.sh --onefile   # onefile
```

Genera `dist/kiosco-pos_1.0.0_amd64.deb`. Actualiza automáticamente la versión y el tamaño
instalado en el `control` file desde `build_config.py`.

**Paso 3 — Validar**

```bash
bash scripts/test_deb.sh --ubuntu-version 22.04
bash scripts/test_deb.sh --ubuntu-version 24.04
```

Requiere Docker activo. El contenedor ejecuta `scripts/smoke_test.sh` con 7 verificaciones.

**Paso 4 — Instalar en producción**

```bash
sudo dpkg -i dist/kiosco-pos_1.0.0_amd64.deb
sudo apt-get install -f    # resuelve dependencias faltantes si dpkg las reporta
```

El `postinst` configura todo automáticamente: no requiere intervención manual.

---

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/hardware/cups_printer_adapter.py` | Nuevo — adaptador CUPS para Linux |
| `src/infrastructure/hardware/null_printer_adapter.py` | Nuevo — adaptador nulo (dev/fallback) |
| `src/infrastructure/hardware/__init__.py` | Nuevo — factory cross-platform |
| `src/main.py` | Modificado — usa `get_printer_adapter()` del factory |
| `tests/unit/infrastructure/test_hardware_adapters.py` | Nuevo — tests unitarios sin hardware |
| `scripts/build_linux.sh` | Nuevo — compilación Nuitka para Linux |
| `scripts/package_deb.sh` | Nuevo — genera el paquete `.deb` |
| `scripts/test_deb.sh` | Nuevo — orquesta el pipeline de testing Docker |
| `scripts/smoke_test.sh` | Nuevo — verificaciones post-instalación |
| `packaging/deb/DEBIAN/control` | Nuevo — metadatos y dependencias del paquete |
| `packaging/deb/DEBIAN/postinst` | Nuevo — inicialización de MariaDB, udev, permisos |
| `packaging/deb/DEBIAN/prerm` | Nuevo — detiene el proceso antes de desinstalar |
| `packaging/deb/DEBIAN/conffiles` | Nuevo — declara `/etc/pos/config.ini` como config |
| `packaging/deb/usr/share/applications/pos.desktop` | Nuevo — entrada en el menú GNOME/KDE |
| `packaging/deb/etc/pos/config.ini.example` | Nuevo — ejemplo de configuración de DB |
| `packaging/Dockerfile.test` | Nuevo — imagen Ubuntu para validación aislada |
| `doc/compatibilidad-linux.md` | Nuevo — versiones probadas y decisiones de compilación |

---

## Notas Técnicas

- **Modo standalone vs onefile:** Se usa standalone por defecto. Los kioscos suelen tener HDDs mecánicos donde la extracción de `--onefile` a `/tmp` en cada arranque agrega latencia perceptible.
- **MariaDB en Docker:** El contenedor de test no tiene `systemd`; el `postinst` y el smoke test inician `mysqld_safe` directamente en background.
- **Idempotencia del postinst:** Todos los comandos SQL usan `CREATE DATABASE IF NOT EXISTS` y `CREATE USER IF NOT EXISTS`, por lo que reinstalar el paquete no rompe datos existentes.
- **Reglas udev:** Se instalan en `/etc/udev/rules.d/99-thermal-printer.rules` para que el usuario `pos` acceda a la impresora USB sin `sudo`. Cubre Epson TM, Star Micronics, Bixolon y genéricas.
- **Variable de entorno `POS_ENV`:** La factory `get_printer_adapter()` detecta `sys.platform` automáticamente. Se puede forzar el adaptador con la variable de entorno `POS_ENV=linux|windows` para testing cruzado.
