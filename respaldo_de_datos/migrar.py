import sqlite3
from sqlalchemy import create_engine, text

# 1. Conexiones
# Cambiá el nombre del archivo si es necesario
conn_sqlite = sqlite3.connect('respaldo_kiosco_2026-07-18.db')
cursor_sqlite = conn_sqlite.cursor()

# URL de tu MariaDB en Docker (usando los datos de tu .env)
# Reemplazá 'root:root' y 'kiosco_pos' si usás otros valores
engine_mariadb = create_engine("mysql+pymysql://root:root@localhost:3306/kiosco_pos")

print("Iniciando migración de datos...")

# 2. Obtener todas las tablas del respaldo SQLite
cursor_sqlite.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'alembic_%';")
tablas = [row[0] for row in cursor_sqlite.fetchall()]

# 3. Migrar tabla por tabla
with engine_mariadb.begin() as conn_maria:
    # Desactivar temporalmente la verificación de claves foráneas para evitar errores de orden
    conn_maria.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))

    for tabla in tablas:
        print(f"Migrando tabla: {tabla}...")

        # Leer datos de SQLite
        cursor_sqlite.execute(f"SELECT * FROM [{tabla}];")
        filas = cursor_sqlite.fetchall()

        if not filas:
            print(f"-> Tabla {tabla} vacía. Saltando.")
            continue

        # Obtener nombres de columnas
        columnas = [descripcion[0] for descripcion in cursor_sqlite.description]

        # Limpiar datos previos en MariaDB para evitar duplicados (opcional)
        conn_maria.execute(text(f"DELETE FROM {tabla};"))

        # Preparar la consulta de inserción para MariaDB
        placeholders = ", ".join([f":{col}" for col in columnas])
        query_insert = text(f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES ({placeholders});")

        # Convertir filas a diccionarios para SQLAlchemy
        datos_insertar = [dict(zip(columnas, fila)) for fila in filas]

        # Ejecutar inserción masiva
        conn_maria.execute(query_insert, datos_insertar)
        print(f"-> ¡{len(filas)} filas migradas con éxito!")

    # Reactivar verificación de claves foráneas
    conn_maria.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

conn_sqlite.close()
print("\n¡Migración finalizada con éxito! Todos los datos están en tu contenedor MariaDB.")
