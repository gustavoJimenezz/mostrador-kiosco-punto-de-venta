# Orquestador de Servicio MariaDB (Local Process)

**Fecha:** 2026-03-26

## Resumen

Implementación del módulo `database_launcher.py` que actúa como puente entre el ejecutable compilado del POS y el MariaDB Portable incluido en el bundle. Verifica si el proceso `mysqld.exe` está activo antes de que la UI arranque, lo inicia silenciosamente si es necesario, y realiza un health check de conexión antes de permitir el inicio de la aplicación.

## Cambios Principales

- Nuevo módulo `src/infrastructure/database_launcher.py` con lógica completa de orquestación
- Nuevo archivo de configuración `config/database.ini` con parámetros de conexión a MariaDB
- Integración en `src/main.py` como primer paso, antes de instanciar `QApplication`
- Dependencia `psutil` agregada para detección de procesos del sistema
- 18 tests unitarios en `tests/unit/infrastructure/test_database_launcher.py` con mocks de `subprocess`, `psutil` y SQLAlchemy

## Flujo de Trabajo

**Punto de entrada:** `main()` en `src/main.py`, inmediatamente después de `load_dotenv()` y antes de cualquier componente Qt.

```
[main.py] → launch_mariadb()
               │
               ├─ Leer config/database.ini (host, port, user, password, database)
               │
               ├─ ¿Existe vendor/mariadb/bin/mysqld.exe?
               │     ├─ SÍ → ¿Está el proceso activo? (psutil)
               │     │         ├─ NO → subprocess.Popen (CREATE_NO_WINDOW)
               │     │         └─ SÍ → continuar
               │     └─ NO → omitir inicio (entorno Linux/dev)
               │
               └─ Health check SQLAlchemy (3 intentos, 2s de pausa)
                     ├─ ÉXITO → retorna True → app arranca normalmente
                     └─ FALLO → retorna False → mensaje de error + sys.exit(1)
```

**Resultado:** Si `launch_mariadb()` retorna `False`, se imprime el mensaje `"No se pudo iniciar el motor de datos. Verifique permisos de carpeta."` en `stderr` y la aplicación termina con código de salida `1`, sin mostrar ninguna ventana Qt.

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/database_launcher.py` | Nuevo — orquestador completo |
| `config/database.ini` | Nuevo — parámetros de conexión |
| `src/main.py` | Modificado — integración del launcher antes de `QApplication` |
| `tests/unit/infrastructure/__init__.py` | Nuevo — módulo de test |
| `tests/unit/infrastructure/test_database_launcher.py` | Nuevo — 18 tests unitarios |
| `pyproject.toml` | Modificado — dependencia `psutil` agregada |

## Notas Técnicas

- **`CREATE_NO_WINDOW`:** La flag de `subprocess` es específica de Windows. En Linux su valor es `0` (sin efecto), lo que permite que el código comparta la misma rama sin condicionales de plataforma.
- **`NullPool` en health check:** El engine temporal usado para el health check usa `NullPool` para no dejar conexiones abiertas ni interferir con el pool principal creado después en `main.py`.
- **Comportamiento en desarrollo (Linux):** Si `vendor/mariadb/bin/mysqld.exe` no existe, el launcher omite el inicio del proceso y va directo al health check, asumiendo una instancia MariaDB externa configurada vía `DATABASE_URL` o `.env`.
- **Timeout máximo:** Con 3 intentos y 2 segundos de pausa, el tiempo máximo de espera es ~6 segundos antes de mostrar el error al usuario.
- **`connection_url` como parámetro opcional:** `launch_mariadb()` acepta la URL directamente para reutilizar la misma variable `database_url` ya construida en `main.py`, evitando duplicar la lógica de lectura de configuración.
