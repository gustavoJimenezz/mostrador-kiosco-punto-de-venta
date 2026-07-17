Arquitectura y Estructura de Directorios
Utilizaremos Arquitectura Hexagonal (Ports & Adapters). El objetivo es que el "Cerebro" (Domain) esté protegido de los cambios externos (si mañana querés cambiar MariaDB por PostgreSQL o PySide6 por una Web App).

Estructura de Carpetas (Project Layout)

kiosco_pos/
├── src/
│   ├── domain/                # El "Core" (Puro Python, sin dependencias)
│   │   ├── models/            # Product, Sale, Price (Value Object)
│   │   ├── services/          # PriceCalculator, StockManager
│   │   └── ports/             # Interfaces (RepositoryBase, PrinterBase)
│   ├── application/           # Casos de Uso (Orquestación)
│   │   ├── use_cases/         # ProcessSale, UpdateBulkPrices
│   ├── infrastructure/        # Adaptadores (Dependencias externas)
│   │   ├── persistence/       # SQLAlchemy, MariaDB Mappings
│   │   ├── ui/                # PySide6 Windows, Widgets, Presenters
│   │   ├── hardware/          # PrinterAdapter, BarcodeAdapter
│   └── main.py                # Punto de entrada (Composition Root)
├── tests/                     # Unitarios en Linux, Integración en Windows
├── alembic/                   # Migraciones de DB
└── requirements.txt


¿Qué es la Arquitectura Hexagonal (Ports & Adapters)?
El concepto central es la Independencia. Imaginá que tu lógica de negocio (cómo calculás el precio de un alfajor con 15% de inflación) es un motor. La Arquitectura Hexagonal dice que ese motor debe funcionar igual si lo conectás a una carcasa de Windows (PySide6), a una página web (FastAPI) o si lo probás solo en un banco de pruebas (Unit Tests).

Los 3 Componentes Clave:

El Core (Dominio): Está en el centro. Aquí viven las reglas del kiosco. No sabe qué es una base de datos ni qué es una ventana. Es Python puro.

Los Puertos (Ports): Son "enchufes" o interfaces. El Core dice: "Yo necesito guardar una venta, no me importa cómo". Define una interfaz SaveSale().

Los Adaptadores (Adapters): Son los cables que conectan el mundo real a los puertos.

Adaptador de Entrada: PySide6 captura el teclado y "empuja" datos al Core.

Adaptador de Salida: SQLAlchemy recibe la orden de guardar y la escribe en MariaDB.

Diseño de Base de Datos (Esquema Senior)
Para un sistema POS que debe manejar historial de precios y stock crítico, estas son las columnas esenciales para cada tabla en MariaDB:

1. Tabla: products (El catálogo)
Columna,Tipo,Descripción
id,UUID / INT,Clave primaria.
barcode,VARCHAR(50),Indexado. El código EAN-13 del producto.
name,VARCHAR(250),FullText Index. Nombre para búsqueda rápida.
category_id,INT,FK a categorías.
current_cost,"DECIMAL(12,2)",Último costo de compra del proveedor.
margin_percent,"DECIMAL(5,2)",Porcentaje de ganancia (ej: 35.00).
current_price,"DECIMAL(12,2)",Precio de venta actual (calculado).
min_stock,INT,Alerta de stock crítico.

2. Tabla: price_history (El radar de inflación)
Columna,Tipo,Descripción
id,INT,PK.
product_id,INT,FK a products.
old_cost,"DECIMAL(12,2)",Costo anterior.
new_cost,"DECIMAL(12,2)",Costo nuevo tras el aumento.
updated_at,DATETIME,Fecha y hora exacta del cambio.

3. Tabla: sales (Cabecera de Venta)
Columna,Tipo,Descripción
id,UUID,PK.
timestamp,DATETIME,Momento de la venta.
total_amount,"DECIMAL(12,2)",Suma total cobrada.
payment_method,ENUM,"Efectivo, Débito, Transferencia."
cash_close_id,INT,FK al Arqueo de Caja diario.

4. Tabla: sale_items (Detalle de Venta)
Columna,Tipo,Descripción
id,INT,PK.
sale_id,UUID,FK a sales.
product_id,INT,FK a products.
quantity,INT,Cantidad vendida.
price_at_sale,"DECIMAL(12,2)",Crítico: El precio al que se vendió en ESE momento.


Stack Tecnológico Completo:

Lenguaje y Base de Desarrollo
Python 3.12+:
Pydantic v2: Lo usaremos en la capa de Aplicación para validar que los datos que entran (desde la UI o un Excel) sean correctos antes de que lleguen al Core. Es extremadamente rápido (escrito en Rust).

Interfaz de Usuario (The Desktop Adapter)
PySide6 (Qt for Python): Es la versión oficial de Qt. A diferencia de Tkinter (muy simple) o CustomTkinter, PySide6 permite crear interfaces de grado industrial que se sienten nativas en Windows 11. Soporta QSS (estilos tipo CSS) para que el POS sea visualmente moderno.

Qt Designer: Permite prototipar las ventanas de forma visual, separando el diseño del comportamiento lógico.

Persistencia y Datos (The Infrastructure)
MariaDB (Community Server): A diferencia de SQLite, MariaDB es un servidor de base de datos real. Soporta transacciones pesadas y permite que, en el futuro, varias cajas (PCs) se conecten a una misma base de datos central en el local sin que el archivo se corrompa.

SQLAlchemy 2.0 (ORM): Usaremos el Mapeo Imperativo. Esto nos permite desacoplar las tablas de la base de datos de nuestras clases de Python. Si mañana decidís subir la base de datos a la nube (AWS/Azure), solo cambiás la cadena de conexión.

Alembic: Es el sistema de "Control de Versiones" para la base de datos. Si agregás una columna "Descuento" a los productos, Alembic actualiza la base de datos en la PC del kiosquero sin borrar sus datos.

Procesamiento y Performance
Polars: Reemplaza a Pandas. Para un kiosco que recibe una lista de precios de 10,000 productos de un proveedor, Polars procesa ese archivo usando todos los núcleos del procesador. Lo que en Excel tarda un minuto, en Polars tarda milisegundos.

Distribución y DevOps Local
Nuitka: No es un simple "empaquetador" como PyInstaller. Nuitka compila el código Python a C++. Esto da dos beneficios:

Velocidad: El código corre más rápido.

Seguridad: Hace que sea muy difícil para un tercero "robar" tu código fuente o crackear el sistema.

Inno Setup: Es la herramienta estándar para crear instaladores .exe profesionales en Windows. Permite instalar MariaDB como un servicio automáticamente durante la instalación del POS.
