"""Tests unitarios para la entidad de dominio Category.

Cobertura:
    - Construcción válida con name correcto.
    - ValueError con name vacío (string vacío o solo espacios).
    - ValueError con name que supera 100 caracteres.
    - El campo id es None por defecto y no entra en comparación (compare=False).
"""

from __future__ import annotations

import pytest

from src.domain.models.category import Category


class TestCategoryConstruction:
    def test_construccion_valida(self) -> None:
        """Category con name válido se construye sin errores."""
        cat = Category(name="Golosinas")
        assert cat.name == "Golosinas"
        assert cat.id is None

    def test_construccion_con_id(self) -> None:
        """Category puede recibir id explícito."""
        cat = Category(name="Bebidas", id=5)
        assert cat.id == 5

    def test_name_vacio_lanza_error(self) -> None:
        """Name vacío ('') lanza ValueError."""
        with pytest.raises(ValueError, match="no puede estar vacío"):
            Category(name="")

    def test_name_solo_espacios_lanza_error(self) -> None:
        """Name con solo espacios lanza ValueError."""
        with pytest.raises(ValueError, match="no puede estar vacío"):
            Category(name="   ")

    def test_name_exactamente_100_chars_es_valido(self) -> None:
        """Name de exactamente 100 caracteres es válido."""
        cat = Category(name="A" * 100)
        assert len(cat.name) == 100

    def test_name_101_chars_lanza_error(self) -> None:
        """Name de 101 caracteres lanza ValueError."""
        with pytest.raises(ValueError, match="no puede superar 100 caracteres"):
            Category(name="A" * 101)

    def test_id_excluido_de_comparacion(self) -> None:
        """Dos Category con mismo name pero distinto id son iguales (compare=False en id)."""
        cat1 = Category(name="Lácteos", id=1)
        cat2 = Category(name="Lácteos", id=99)
        assert cat1 == cat2
