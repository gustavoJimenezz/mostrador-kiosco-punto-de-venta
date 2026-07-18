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

Diagrama de Datos (UML / ERD)
Para un kiosco en Argentina, la tabla price_history es vital para entender la rentabilidad histórica frente a la inflación.

Relaciones Clave:
Product (1) ↔ PriceHistory (N): Cada vez que cambia el costo o el margen, se guarda un registro. No solo sobreescribimos el precio actual.

Sale (1) ↔ SaleItem (N): La venta guarda el total, pero cada SaleItem guarda el price_at_sale. Si el producto aumenta mañana, la venta de ayer no debe cambiar su valor.

StockLog: Registro de movimientos (entrada por compra, salida por venta, ajuste manual).

🔄 Flujo de Trabajo: El "Cerebro" en Acción
Entrada (Primary Adapter): El usuario presiona F1 en PySide6 y escanea un código.

Puerto de Entrada: La UI llama al caso de uso GetProductByCode.

Lógica (Domain): El Core busca el producto. Si hay una promoción activa (ej: 2x1), el Dominio calcula el descuento.

Puerto de Salida (Secondary Adapter): El Core pide al ProductRepository los datos de MariaDB.

Respuesta: La UI recibe la entidad calculada y refresca la pantalla.

Atomicidad en Ventas: El proceso de "Cerrar Venta" debe ser una transacción única. O se descuenta el stock, se guarda la venta y se registra el dinero en caja, o no se hace nada. Nunca a medias.

Búsqueda "Fuzzy": Los usuarios no siempre escriben bien "Alfajor Jorgito". Implementá búsqueda por similitud en la infraestructura de base de datos para mejorar la UX.

Offline First: La app debe iniciar incluso si no hay internet. El chequeo de licencias o actualizaciones debe ser asincrónico para no trabar la apertura del local a las 8 AM.


¿Qué es la Arquitectura Hexagonal (Ports & Adapters)?
El concepto central es la Independencia. Imaginá que tu lógica de negocio (cómo calculás el precio de un alfajor con 15% de inflación) es un motor. La Arquitectura Hexagonal dice que ese motor debe funcionar igual si lo conectás a una carcasa de Windows (PySide6), a una página web (FastAPI) o si lo probás solo en un banco de pruebas (Unit Tests).

Los 3 Componentes Clave:
El Core (Dominio): Está en el centro. Aquí viven las reglas del kiosco. No sabe qué es una base de datos ni qué es una ventana. Es Python puro.

Los Puertos (Ports): Son "enchufes" o interfaces. El Core dice: "Yo necesito guardar una venta, no me importa cómo". Define una interfaz SaveSale().

Los Adaptadores (Adapters): Son los cables que conectan el mundo real a los puertos.

Adaptador de Entrada: PySide6 captura el teclado y "empuja" datos al Core.

Adaptador de Salida: SQLAlchemy recibe la orden de guardar y la escribe en MariaDB.

¿Por qué te sirve para el Kiosco? Porque si mañana MariaDB se vuelve lenta con 50,000 productos, solo cambiás el Adaptador de Persistencia (por ejemplo a PostgreSQL) y no tocás ni una sola línea de código de tu lógica de ventas.

🗄️ Diseño de Base de Datos (Esquema Senior)
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

Gemini ha dicho
¡Excelente! Como Arquitecto, me encanta que quieras profundizar en el "Por qué" antes del "Cómo". Entender la Arquitectura Hexagonal es lo que diferencia a un programador de un Ingeniero de Software que construye sistemas que duran 10 años.

⬢ ¿Qué es la Arquitectura Hexagonal (Ports & Adapters)?
El concepto central es la Independencia. Imaginá que tu lógica de negocio (cómo calculás el precio de un alfajor con 15% de inflación) es un motor. La Arquitectura Hexagonal dice que ese motor debe funcionar igual si lo conectás a una carcasa de Windows (PySide6), a una página web (FastAPI) o si lo probás solo en un banco de pruebas (Unit Tests).

Los 3 Componentes Clave:
El Core (Dominio): Está en el centro. Aquí viven las reglas del kiosco. No sabe qué es una base de datos ni qué es una ventana. Es Python puro.

Los Puertos (Ports): Son "enchufes" o interfaces. El Core dice: "Yo necesito guardar una venta, no me importa cómo". Define una interfaz SaveSale().

Los Adaptadores (Adapters): Son los cables que conectan el mundo real a los puertos.

Adaptador de Entrada: PySide6 captura el teclado y "empuja" datos al Core.

Adaptador de Salida: SQLAlchemy recibe la orden de guardar y la escribe en MariaDB.

¿Por qué te sirve para el Kiosco? Porque si mañana MariaDB se vuelve lenta con 50,000 productos, solo cambiás el Adaptador de Persistencia (por ejemplo a PostgreSQL) y no tocás ni una sola línea de código de tu lógica de ventas.

🗄️ Diseño de Base de Datos (Esquema Senior)
Para un sistema POS que debe manejar historial de precios y stock crítico, estas son las columnas esenciales para cada tabla en MariaDB:

1. Tabla: products (El catálogo)
Columna	Tipo	Descripción
id	UUID / INT	Clave primaria.
barcode	VARCHAR(50)	Indexado. El código EAN-13 del producto.
name	VARCHAR(250)	FullText Index. Nombre para búsqueda rápida.
category_id	INT	FK a categorías.
current_cost	DECIMAL(12,2)	Último costo de compra del proveedor.
margin_percent	DECIMAL(5,2)	Porcentaje de ganancia (ej: 35.00).
current_price	DECIMAL(12,2)	Precio de venta actual (calculado).
min_stock	INT	Alerta de stock crítico.

2. Tabla: price_history (El radar de inflación)
Columna	Tipo	Descripción
id	INT	PK.
product_id	INT	FK a products.
old_cost	DECIMAL(12,2)	Costo anterior.
new_cost	DECIMAL(12,2)	Costo nuevo tras el aumento.
updated_at	DATETIME	Fecha y hora exacta del cambio.

3. Tabla: sales (Cabecera de Venta)
Columna	Tipo	Descripción
id	UUID	PK.
timestamp	DATETIME	Momento de la venta.
total_amount	DECIMAL(12,2)	Suma total cobrada.
payment_method	ENUM	Efectivo, Débito, Transferencia.
cash_close_id	INT	FK al Arqueo de Caja diario.

4. Tabla: sale_items (Detalle de Venta)
Columna	Tipo	Descripción
id	INT	PK.
sale_id	UUID	FK a sales.
product_id	INT	FK a products.
quantity	INT	Cantidad vendida.
price_at_sale	DECIMAL(12,2)	Crítico: El precio al que se vendió en ESE momento.

5. Tabla: stock_movements (Auditoría de Stock)
Columna,Tipo,Descripción
id,INT,PK.
product_id,INT,FK a products.
quantity,INT,"Cantidad (positiva para compra, negativa para venta)."
reason,VARCHAR(50),"""VENTA"", ""COMPRA"", ""ROTURA"", ""AJUSTE""."

