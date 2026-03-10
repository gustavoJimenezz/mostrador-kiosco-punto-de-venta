# Flujo de Trabajo del Proyecto POS

Diagrama completo del ciclo de desarrollo, desde el dominio puro hasta la distribución final.
Cubre los 5 epics y 10 tickets del plan de ejecución.

---

## 1. Secuencia de Desarrollo (Dependencias entre Tickets)

```mermaid
flowchart TD
    subgraph E1["⬡ Epic 1 · Dominio Puro (Linux)"]
        T11["#1 · Modelos de Dominio\nProduct · Sale · CashClose · Price\n🔴 Prioridad Crítica"]
        T12["#2 · Puertos de Persistencia\nProductRepository · PrinterBase\n🟠 Prioridad Alta"]
        T11 --> T12
    end

    subgraph E2["⬡ Epic 2 · Infraestructura MariaDB (Linux)"]
        T21["#3 · Adaptador MariaDB\nSQLAlchemy 2.0 · Mapeo Imperativo\n🟠 Prioridad Alta"]
        T22["#4 · Motor de Búsqueda Indexada\nFullText · EAN-13 · < 50ms / 5K SKUs\n🟠 Prioridad Alta"]
        T21 --> T22
    end

    subgraph E3["⬡ Epic 3 · Interfaz de Usuario (Linux)"]
        T31["#5 · Presenters y Navegación\nMVP · Keyboard-First · F1-F12\n🔴 Prioridad Crítica"]
        T32["#6 · Importador Masivo (Polars)\nCSV/Excel · 5K filas en < 3s\n🟡 Prioridad Media"]
    end

    subgraph E4["⬡ Epic 4 · Hardware (Windows 11)"]
        T41["#7 · Adaptador Impresión Térmica\nESC/POS · pywin32 · UNC path\n🟡 Prioridad Media"]
        T42["#8 · Escalado DPI\nHighDpiScaleFactorRoundingPolicy\n🔵 Prioridad Baja"]
    end

    subgraph E5["⬡ Epic 5 · Distribución (Windows 11)"]
        T51["#9 · Compilación Nuitka\nPOS.exe · standalone/onefile\n🟠 Prioridad Alta"]
        T52["#10 · Instalador Inno Setup\nInstalar_POS.exe + MariaDB Portable\n🟡 Prioridad Media"]
        T51 --> T52
    end

    T12 --> T21
    T12 --> T31
    T22 --> T31
    T22 --> T32
    T31 --> T41
    T31 --> T42
    T12 --> T41
    E3 --> E4
    E4 --> E5
```

---

## 2. Arquitectura Hexagonal (Flujo de Datos)

```mermaid
flowchart LR
    subgraph EXTERNAL_IN["Adaptadores Primarios (Entrada)"]
        UI["PySide6 UI\nTicket #5"]
        IMPORT["Importador Polars\nTicket #6"]
        BARCODE["Lector de Barras\n(hardware externo)"]
    end

    subgraph CORE["Núcleo de la Aplicación"]
        direction TB
        subgraph APP["Capa de Aplicación"]
            UC["Use Cases\nProcessSale\nUpdateBulkPrices\nGetProductByCode"]
        end
        subgraph DOMAIN["Dominio Puro (Tickets #1 y #2)"]
            direction LR
            ENT["Entidades\nProduct · Sale\nCashClose"]
            VO["Value Objects\nPrice (ARS)"]
            SVC["Servicios\nPriceCalculator\nStockManager"]
            PORTS["Puertos\nProductRepository\nPrinterBase"]
        end
        APP --> DOMAIN
    end

    subgraph EXTERNAL_OUT["Adaptadores Secundarios (Salida)"]
        DB["MariaDB\nTickets #3 y #4"]
        PRINTER["Impresora Térmica\nTicket #7"]
    end

    subgraph DIST["Distribución (Tickets #9 y #10)"]
        EXE["POS.exe\n(Nuitka)"]
        INSTALLER["Instalar_POS.exe\n(Inno Setup)"]
        EXE --> INSTALLER
    end

    BARCODE --> UI
    UI --> UC
    IMPORT --> UC
    UC --> PORTS
    PORTS -->|"implementa"| DB
    PORTS -->|"implementa"| PRINTER

    CORE -->|"empaqueta"| DIST
```

---

## 3. Ciclo de Vida de una Venta

```mermaid
sequenceDiagram
    actor Cajero
    participant UI as PySide6 UI<br/>(Ticket #5)
    participant Worker as QThread Worker<br/>(Ticket #5)
    participant UC as Use Case<br/>ProcessSale
    participant Repo as MariaDB Repo<br/>(Tickets #3 y #4)
    participant Printer as Impresora Térmica<br/>(Ticket #7)

    Cajero->>UI: Escanea código de barras (EAN-13)
    UI->>Worker: search_by_barcode(barcode)
    Worker->>Repo: SELECT con índice (< 50ms)
    Repo-->>Worker: Product encontrado
    Worker-->>UI: Actualiza carrito en hilo principal
    UI-->>Cajero: Muestra producto + precio (ARS con Decimal)

    loop Agrega más productos
        Cajero->>UI: Escanea / busca por nombre (F2)
        UI->>Worker: search_by_name(query)
        Worker->>Repo: FULLTEXT MATCH AGAINST
        Repo-->>Worker: Lista de productos
        Worker-->>UI: Muestra resultados
    end

    Cajero->>UI: Presiona F4 (Confirmar Venta)
    UI->>UC: process_sale(cart_items)

    Note over UC,Repo: Transacción atómica (todo o nada)
    UC->>Repo: INSERT sale + sale_items + UPDATE stock
    Repo-->>UC: Venta confirmada (price_at_sale guardado)

    UC->>Printer: print_ticket(sale)
    Printer-->>Cajero: Ticket impreso (ESC/POS via pywin32)
    UI-->>Cajero: Pantalla limpia para próxima venta
```

---

## 4. Ciclo de Importación Masiva de Precios

```mermaid
sequenceDiagram
    actor Admin
    participant Dialog as Diálogo de Importación<br/>(Ticket #6)
    participant Polars as Importador Polars<br/>(Ticket #6)
    participant UC as Use Case<br/>UpdateBulkPrices
    participant Repo as MariaDB Repo<br/>(Ticket #3)

    Admin->>Dialog: Selecciona archivo CSV/Excel del proveedor
    Dialog->>Polars: load_file(path)
    Polars->>Polars: read_csv() con tipado explícito
    Polars->>Polars: Validar columnas (barcode, name, cost_price)
    Polars->>Polars: Normalizar decimales (formato ARS: 1.500,75)
    Polars-->>Dialog: DataFrame validado (errores reportados)

    Dialog->>UC: update_bulk_prices(products_df)

    loop Por cada fila (5.000 registros en < 3s)
        UC->>Repo: upsert(product)
        alt Producto existe
            Repo->>Repo: UPDATE price + INSERT price_history
        else Producto nuevo
            Repo->>Repo: INSERT product
        end
    end

    Repo-->>UC: Importación completada
    UC-->>Dialog: Reporte (X actualizados, Y insertados, Z errores)
    Dialog-->>Admin: Resultado mostrado en pantalla
```

---

## 5. Pipeline de Distribución

```mermaid
flowchart TD
    subgraph DEV["Desarrollo (Linux)"]
        SRC["Código Fuente\nsrc/ + tests/"]
        TESTS["Tests Unitarios\n100% cobertura dominio"]
        SRC --> TESTS
    end

    subgraph BUILD["Build (Windows 11)"]
        NUITKA["Nuitka Compiler\nTicket #9"]
        EXE["POS.exe\n--standalone o --onefile"]
        DPI["Config DPI\nTicket #8"]
        NUITKA --> EXE
        DPI --> EXE
    end

    subgraph PACKAGE["Empaquetado (Windows 11)"]
        INNO["Inno Setup\nTicket #10"]
        MARIADB["MariaDB Portable\nbinaries + data/"]
        INSTALLER["Instalar_POS.exe"]
        EXE --> INNO
        MARIADB --> INNO
        INNO --> INSTALLER
    end

    subgraph DEPLOY["Instalación en el Kiosco"]
        WIN11["Windows 11\ndel cliente"]
        POS_RUNNING["POS corriendo\nOffline-first"]
        INSTALLER --> WIN11
        WIN11 --> POS_RUNNING
    end

    TESTS -->|"aprobados"| NUITKA
```

---

## 6. Resumen por Epic y Entorno

```mermaid
gantt
    title Plan de Ejecución — Tickets por Epic
    dateFormat  X
    axisFormat  %s

    section Epic 1 · Dominio (Linux)
    #1 Modelos de Dominio          :crit, t11, 0, 1
    #2 Puertos de Persistencia     :t12, after t11, 1

    section Epic 2 · Infraestructura (Linux)
    #3 Adaptador MariaDB           :t21, after t12, 1
    #4 Motor de Búsqueda           :t22, after t21, 1

    section Epic 3 · UI (Linux)
    #5 Presenters Keyboard-First   :crit, t31, after t12, 2
    #6 Importador Polars           :t32, after t22, 1

    section Epic 4 · Hardware (Windows)
    #7 Impresión Térmica           :t41, after t31, 1
    #8 Escalado DPI                :t42, after t31, 1

    section Epic 5 · Distribución (Windows)
    #9 Compilación Nuitka          :t51, after t41, 1
    #10 Instalador Inno Setup      :t52, after t51, 1
```

---

## Referencias

- Plan de Ejecución → [`doc/plan-de-ejecucion.md`](./plan-de-ejecucion.md)
- Aspectos Técnicos → [`doc/aspectos-tecnicos.md`](./aspectos-tecnicos.md)
- Issues del proyecto → [github.com/gustavoJimenezz/mostrador-kiosco-punto-de-venta/issues](https://github.com/gustavoJimenezz/mostrador-kiosco-punto-de-venta/issues)
