Plan de Ejecución Hexagonal (Fase 1)
Epic 1: El Dominio Puro (The Core)
Se puede ejecutar 100% en Ubuntu.

Ticket 1.1: Modelos de Dominio y Lógica de Precios
Prioridad: Crítica.

Entorno: Ubuntu / Linux.

Descripción: Crear entidades (Product, Sale, CashClose) y Value Objects (Price). Implementar lógica de redondeo para ARS.

DoD: Cobertura de tests unitarios del 100% en cálculos de margen y precios.

Tip Senior: Usar decimal.Decimal con ROUND_HALF_UP para evitar que los decimales de la inflación te descuadren la caja por redondeos truncados.

Ticket 1.2: Puerto de Persistencia (Interface Definition)
Prioridad: Alta.

Entorno: Ubuntu / Linux.

Descripción: Definir la clase abstracta (Protocol o ABC) ProductRepository. El Core solo llama a estos métodos, no sabe que existe MariaDB.

DoD: Interfaz definida y testeada mediante un MockRepository en memoria.

Epic 2: Infraestructura y Adaptadores de Datos
Se puede ejecutar en Ubuntu (usando MariaDB nativo o Docker).

Ticket 2.1: Adaptador MariaDB con SQLAlchemy 2.0
Prioridad: Alta.

Entorno: Ubuntu / Linux.

Descripción: Implementar el mapping imperativo. Configurar el pool de conexiones para una base de datos local.

DoD: Integración exitosa entre las entidades de dominio y las tablas de MariaDB.

Tip Senior: Configurá MariaDB con el motor Aria o InnoDB optimizado para escrituras rápidas, previniendo corrupción de datos ante cortes de luz (comunes en verano en Argentina).

Ticket 2.2: Motor de Búsqueda Indexada (5,000+ SKUs)
Prioridad: Alta.

Entorno: Ubuntu / Linux.

Descripción: Crear queries optimizadas con SQLAlchemy que usen índices en barcode y name.

DoD: Búsqueda por parte del nombre de producto que responda en < 50ms con 5,000 registros.

Epic 3: Interfaz de Usuario y Adaptador Primario
Desarrollo en Ubuntu, validación visual en Windows.

Ticket 3.1: Presenters y Navegación Keyboard-First
Prioridad: Crítica.

Entorno: Ubuntu / Linux.

Descripción: Implementar la lógica del Presenter (MVP). Manejo de atajos F1-F12.

DoD: La lógica de la UI funciona (puedo agregar productos al carrito y ver el total) usando solo el teclado.

Tip Senior: En PySide6, usá QThread o Worker para la comunicación con la DB. Si la búsqueda tarda 100ms y bloqueás el hilo principal, el lector de barras podría "perder" caracteres al escanear rápido.

Ticket 3.2: Adaptador de Importación (Polars)
Prioridad: Media.

Entorno: Ubuntu / Linux.

Descripción: Script de carga masiva de listas Excel de proveedores.

DoD: Importación de un CSV de 5,000 filas procesado y guardado en < 3 segundos.

Epic 4: Adaptadores de Hardware y Ajustes de OS
Ejecutar obligatoriamente en Windows 11.

Ticket 4.1: Adaptador de Impresión Térmica (Win32)
Prioridad: Media.

Entorno: Windows 11.

Descripción: Implementar el "Output Adapter" para tickets. Usar pywin32 para enviar comandos ESC/POS a la impresora térmica.

DoD: Impresión de un ticket de prueba desde la app.

Tip Senior: Usá rutas UNC para las impresoras (ej. \\localhost\Ticketera) para evitar problemas si cambian el puerto USB.

Ticket 4.2: Ajuste de Escalado DPI (High DPI Scaling)
Prioridad: Baja.

Entorno: Windows 11.

Descripción: Configurar Qt.HighDpiScaleFactorRoundingPolicy para que la app se vea nítida en monitores de 14" de notebooks o monitores viejos de 19".

DoD: La app se ve proporcionada en diferentes resoluciones de Windows.

Epic 6: Compatibilidad con Hardware Legacy (CPUs sin SSE4.2)
Ejecutar en Ubuntu 22.04. Produce un .deb independiente para PCs antiguas.

Contexto: PySide6 de PyPI requiere SSE4.2 (Intel Core i-series 2008+ / AMD Bulldozer+).
CPUs anteriores como el Pentium Dual-Core E5700 no la soportan. La solución es usar
PyQt5 como backend de UI mediante la capa de abstracción qtpy.

Ticket 6.1: Capa de abstracción Qt (qtpy)
Prioridad: Crítica.

Entorno: Ubuntu 22.04.

Descripción: Reemplazar todos los imports directos de PySide6 en src/infrastructure/ui/
por imports via qtpy. qtpy detecta en runtime qué toolkit está disponible (PySide6 o PyQt5)
y expone una API unificada. Cambios principales:
  - `from PySide6.QtWidgets import X` → `from qtpy.QtWidgets import X`
  - `Signal` → `qtpy.QtCore.Signal` (qtpy lo normaliza automáticamente)
  - `QUiLoader` → `qtpy.uic.loadUi`
  - Workers: QThread se mantiene igual

DoD: La app arranca y opera sin errores con QT_API=pyqt5 y con QT_API=pyside6.

Tip Senior: qtpy ya está en las dependencias del proyecto (python3-qtpy en Ubuntu 22.04).
No requiere cambios en el dominio ni en los presenters — solo en la capa de infraestructura UI.

Ticket 6.2: Agregar PyQt5 como dependencia opcional
Prioridad: Alta.

Entorno: Ubuntu 22.04.

Descripción: Agregar PyQt5 al pyproject.toml como dependencia de un grupo opcional
`legacy`. El grupo default sigue usando PySide6. El build legacy usa el grupo `legacy`.

```toml
[tool.poetry.group.legacy.dependencies]
PyQt5 = ">=5.15.0"
qtpy = ">=2.0.0"
```

DoD: `poetry install --with legacy` instala PyQt5 sin romper el entorno PySide6.

Ticket 6.3: Script de compilación legacy (build_linux_legacy.sh)
Prioridad: Alta.

Entorno: Ubuntu 22.04 con CPU moderna (no el E5700).

Descripción: Crear scripts/build_linux_legacy.sh que:
  1. Activa el grupo `legacy` de Poetry (PyQt5)
  2. Setea QT_API=pyqt5
  3. Compila con Nuitka usando --enable-plugin=pyqt5 en vez de pyside6
  4. Genera dist/main.dist-legacy/

DoD: Binario compilado que corre en el E5700 sin SIGILL.

Tip Senior: Compilar SIEMPRE en una PC con CPU moderna corriendo Ubuntu 22.04.
No intentar compilar en el E5700 — PySide6 de pip falla en ese CPU incluso para compilar.
El binario resultante de Ubuntu 22.04 tiene GLIBC 2.35 y es compatible con Ubuntu 22.04
en cualquier CPU, incluyendo el E5700.

Ticket 6.4: Paquete .deb legacy (package_deb_legacy.sh)
Prioridad: Alta.

Entorno: Ubuntu 22.04.

Descripción: Crear scripts/package_deb_legacy.sh que genere
kiosco-pos-legacy_<version>_amd64.deb usando el binario de dist/main.dist-legacy/.
El paquete legacy:
  - Tiene PyQt5 como dependencia (no PySide6)
  - El postinst detecta si el CPU soporta SSE4.2 y advierte si corresponde
  - Nombre de paquete diferente para coexistir con el paquete standard

DoD: dpkg -i kiosco-pos-legacy_*.deb instala y la app abre en el E5700.

Ticket 6.5: Detección de CPU en postinst
Prioridad: Media.

Entorno: Ubuntu 22.04.

Descripción: Agregar al postinst del paquete standard una verificación de SSE4.2.
Si el CPU no lo soporta, mostrar un mensaje claro en vez de fallar silenciosamente:

```sh
if ! grep -q sse4_2 /proc/cpuinfo; then
    echo "ADVERTENCIA: Este CPU no soporta SSE4.2."
    echo "Usar el paquete kiosco-pos-legacy en su lugar."
    echo "Descargar desde: https://github.com/gustavoJimenezz/mostrador-kiosco-punto-de-venta/releases"
fi
```

DoD: Instalación en CPU sin SSE4.2 muestra el mensaje y no crashea silenciosamente.

Ticket 6.6: Release en GitHub con ambos paquetes
Prioridad: Media.

Entorno: Ubuntu 22.04.

Descripción: Publicar en GitHub Releases dos assets:
  - kiosco-pos_<version>_amd64.deb — para CPUs modernos (SSE4.2+)
  - kiosco-pos-legacy_<version>_amd64.deb — para CPUs sin SSE4.2 (pre-2011)

Documentar en README qué paquete corresponde según el CPU del cliente.

DoD: Ambos .deb disponibles en Releases con descripción clara de compatibilidad.

Epic 5: Empaquetado y Distribución
Ejecutar obligatoriamente en Windows 11.

Ticket 5.1: Compilación con Nuitka (.exe)
Prioridad: Alta.

Entorno: Windows 11.

Descripción: Crear el script de compilación: python -m nuitka --standalone --show-memory --plugin-enable=pyside6 --windows-uac-admin --onefile main.py.

DoD: Un archivo POS.exe funcional que no requiera Python instalado.

Tip Senior: Usá --onefile solo si el cliente valora la simplicidad. Para performance de arranque, --standalone (una carpeta con archivos) es más rápido en PCs con discos mecánicos o CPUs viejas.

Ticket 5.2: Instalador con Inno Setup
Prioridad: Media.

Entorno: Windows 11.

Descripción: Crear el .iss que incluya el ejecutable, la base de datos MariaDB Portable y configure los permisos de carpeta.

DoD: Un archivo Instalar_POS.exe que instale todo el sistema.
