# Compatibilidad Linux — Kiosco POS

## Versiones probadas

| Ubuntu | Arquitectura | Estado | Fecha |
|--------|-------------|--------|-------|
| 22.04 LTS (Jammy) | amd64 | Pendiente validación | — |
| 24.04 LTS (Noble) | amd64 | Pendiente validación | — |

## Cómo ejecutar los tests de instalación

```bash
# Generar el .deb (requiere compilar primero con build_linux.sh)
bash scripts/package_deb.sh

# Probar en Ubuntu 22.04
bash scripts/test_deb.sh --ubuntu-version 22.04

# Probar en Ubuntu 24.04
bash scripts/test_deb.sh --ubuntu-version 24.04
```

## Qué valida el smoke test

1. `/usr/bin/POS` existe y es ejecutable.
2. `/etc/pos/config.ini` fue creado por `postinst`.
3. MariaDB responde a `ping`.
4. La base de datos `kiosco_pos` existe.
5. El usuario `pos` puede conectarse y ejecutar `SELECT 1`.
6. `/usr/share/applications/pos.desktop` existe.
7. La UI arranca sin segfault bajo `xvfb-run` (timeout 5s).

## Decisión de arquitectura: standalone vs onefile

El script `build_linux.sh` compila en modo **standalone** por defecto
(genera `dist/main.dist/`). Motivo: los kioscos suelen tener HDDs mecánicos
o CPUs de bajo costo donde la extracción de `--onefile` a `/tmp` en cada
arranque genera demoras perceptibles.

Para instalar en modo `--onefile` (binario único, arranque más lento):

```bash
bash scripts/build_linux.sh --onefile
bash scripts/package_deb.sh --onefile
```

Ver `doc/aspectos-tecnicos.md` para más detalle sobre la estrategia de compilación.
