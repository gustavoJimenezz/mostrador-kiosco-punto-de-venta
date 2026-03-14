"""Configuración de QApplication para escalado High DPI.

Debe invocarse **antes** de instanciar QApplication. Centraliza toda
política de escalado para que la UI se vea nítida en el rango de
monitores típicos de un kiosco: notebooks 14" 1920x1080 al 125% y
monitores de escritorio 19" 1280x1024 (ratio 4:3).
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


def configure_high_dpi() -> None:
    """Configura la política de escalado DPI antes de crear QApplication.

    Aplica ``HighDpiScaleFactorRoundingPolicy.PassThrough`` para que Qt
    use el factor de escala exacto del SO (p.ej. 1.25 en Windows al 125%)
    sin redondearlo a enteros, evitando fuentes o botones cortados.

    Si la variable de entorno ``QT_SCALE_FACTOR`` está definida, Qt la
    respeta automáticamente; esta función no la sobreescribe para permitir
    ajuste fino en producción sin recompilar.

    Note:
        En PySide6 6.x ``Qt.AA_EnableHighDpiScaling`` fue eliminado
        (siempre activo). ``Qt.AA_UseHighDpiPixmaps`` también está
        activo por defecto; se fuerza explícitamente aquí para garantizar
        compatibilidad con versiones menores anteriores.
    """
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Garantiza íconos/recursos nítidos en pantallas HiDPI.
    # En PySide6 >= 6.0 está activo por defecto, pero la llamada es inocua.
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    _log_scale_factor()


def _log_scale_factor() -> None:
    """Registra en stdout el factor de escala activo si está sobreescrito.

    Ayuda a diagnosticar problemas de escalado sin necesidad de depurador.
    """
    qt_scale = os.environ.get("QT_SCALE_FACTOR")
    if qt_scale:
        print(f"[app_config] QT_SCALE_FACTOR={qt_scale!r} (sobreescritura manual activa)")
