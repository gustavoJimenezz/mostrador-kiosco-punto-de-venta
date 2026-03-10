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
