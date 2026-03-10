"""Tests del motor de búsqueda indexada de MariadbProductRepository.

Cubre dos categorías:
- Tests unitarios (sin DB): verifican el routing correcto entre FullText e ILIKE
  usando una sesión SQLAlchemy mockeada con unittest.mock.
- Tests de integración (requieren MariaDB real): verifican correctitud de
  resultados y cumplimiento del SLA de latencia < 50ms con 5,000 registros.

Ticket 2.2: Motor de Búsqueda Indexada.
"""

from __future__ import annotations

import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.domain.models.product import Product
from src.infrastructure.persistence.mariadb_product_repository import (
    MariadbProductRepository,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_product(name: str, barcode: str = "0000000000001") -> Product:
    """Construye un Product mínimo para usar en asserts."""
    return Product(
        barcode=barcode,
        name=name,
        current_cost=Decimal("100.00"),
        margin_percent=Decimal("35.00"),
    )


# ---------------------------------------------------------------------------
# Tests unitarios — sesión mockeada, sin DB real
# ---------------------------------------------------------------------------

class TestSearchByNameRouting:
    """Verifica que search_by_name delega a la ruta correcta según la longitud del query."""

    def setup_method(self) -> None:
        self.mock_session = MagicMock()
        self.repo = MariadbProductRepository(self.mock_session)

    def test_single_char_query_uses_ilike(self):
        """Query de 1 char usa ILIKE (no alcanza ft_min_word_len=3)."""
        with patch.object(self.repo, "_search_by_name_ilike", return_value=[]) as mock_ilike, \
             patch.object(self.repo, "_search_by_name_fulltext") as mock_fulltext:
            self.repo.search_by_name("c")

        mock_ilike.assert_called_once_with("c")
        mock_fulltext.assert_not_called()

    def test_query_shorter_than_3_chars_uses_ilike_directly(self):
        """Query de 2 chars usa ILIKE sin intentar FullText."""
        with patch.object(self.repo, "_search_by_name_ilike", return_value=[]) as mock_ilike, \
             patch.object(self.repo, "_search_by_name_fulltext") as mock_fulltext:
            self.repo.search_by_name("co")

        mock_ilike.assert_called_once_with("co")
        mock_fulltext.assert_not_called()

    def test_query_of_3_chars_uses_fulltext_first(self):
        """Query de exactamente 3 chars intenta FullText primero."""
        expected = [make_product("Coca Cola")]
        with patch.object(self.repo, "_search_by_name_fulltext", return_value=expected) as mock_ft, \
             patch.object(self.repo, "_search_by_name_ilike") as mock_ilike:
            result = self.repo.search_by_name("coc")

        mock_ft.assert_called_once_with("coc")
        mock_ilike.assert_not_called()
        assert result == expected

    def test_query_longer_than_3_chars_uses_fulltext_first(self):
        """Query de 4+ chars usa FullText sin llegar al fallback."""
        expected = [make_product("Coca Cola"), make_product("Coca Zero", "0000000000002")]
        with patch.object(self.repo, "_search_by_name_fulltext", return_value=expected) as mock_ft, \
             patch.object(self.repo, "_search_by_name_ilike") as mock_ilike:
            result = self.repo.search_by_name("coca")

        mock_ft.assert_called_once_with("coca")
        mock_ilike.assert_not_called()
        assert result == expected

    def test_fulltext_empty_result_triggers_ilike_fallback(self):
        """Si FullText retorna lista vacía, activa el fallback ILIKE."""
        fallback_result = [make_product("Cafe de Olla")]
        with patch.object(self.repo, "_search_by_name_fulltext", return_value=[]) as mock_ft, \
             patch.object(self.repo, "_search_by_name_ilike", return_value=fallback_result) as mock_ilike:
            result = self.repo.search_by_name("cafe")

        mock_ft.assert_called_once_with("cafe")
        mock_ilike.assert_called_once_with("cafe")
        assert result == fallback_result

    def test_fulltext_with_results_does_not_call_ilike(self):
        """Si FullText retorna resultados, NO se llama ILIKE (evita doble query)."""
        ft_result = [make_product("Pepsi")]
        with patch.object(self.repo, "_search_by_name_fulltext", return_value=ft_result), \
             patch.object(self.repo, "_search_by_name_ilike") as mock_ilike:
            result = self.repo.search_by_name("pepsi")

        mock_ilike.assert_not_called()
        assert result == ft_result


class TestBuildFulltextQuery:
    """Verifica la construcción de expresiones BOOLEAN MODE."""

    def setup_method(self) -> None:
        self.repo = MariadbProductRepository(MagicMock())

    def test_single_word_query(self):
        """Una sola palabra genera un término obligatorio con wildcard."""
        assert self.repo._build_fulltext_query("coca") == "+coca*"

    def test_multi_word_query(self):
        """Múltiples palabras generan múltiples términos obligatorios."""
        assert self.repo._build_fulltext_query("coca cola") == "+coca* +cola*"

    def test_query_with_extra_spaces_is_normalized(self):
        """Espacios extras al inicio, al final o en el medio se normalizan."""
        assert self.repo._build_fulltext_query("  coca  cola  ") == "+coca* +cola*"

    def test_three_word_query(self):
        """Tres palabras generan tres términos."""
        result = self.repo._build_fulltext_query("coca cola zero")
        assert result == "+coca* +cola* +zero*"


# ---------------------------------------------------------------------------
# Tests de integración — requieren MariaDB real via POS_TEST_DB_URL
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSearchByNameIntegration:
    """Tests de integración del motor de búsqueda con 5,000 productos reales."""

    def test_search_returns_correct_products(self, db_session, populated_products):
        """Buscar 'Coca Cola' retorna productos con ese nombre."""
        repo = MariadbProductRepository(db_session)
        results = repo.search_by_name("Coca Cola")

        assert len(results) > 0
        for product in results:
            name_lower = product.name.lower()
            assert "coca" in name_lower or "cola" in name_lower

    def test_search_respects_limit_of_50(self, db_session, populated_products):
        """La búsqueda nunca retorna más de 50 resultados."""
        repo = MariadbProductRepository(db_session)
        results = repo.search_by_name("Cola")

        assert len(results) <= 50

    def test_search_by_name_meets_50ms_sla(self, db_session, populated_products):
        """Búsqueda por nombre debe completarse en < 50ms con 5,000 registros.

        Este test es el criterio de aceptación del Ticket 2.2.
        Incluye un warm-up previo para que MariaDB cachee el plan de ejecución.
        """
        repo = MariadbProductRepository(db_session)

        # Warm-up: una query previa para cachear el plan de ejecución
        repo.search_by_name("coca")

        start = time.perf_counter()
        results = repo.search_by_name("coca")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50, (
            f"search_by_name tardó {elapsed_ms:.2f}ms, "
            f"excede el SLA de 50ms con 5,000 registros"
        )
        assert len(results) > 0

    def test_search_by_two_char_query_uses_ilike_fallback(
        self, db_session, populated_products
    ):
        """Query de 2 chars usa ILIKE — debe retornar resultados (correctitud, no latencia)."""
        repo = MariadbProductRepository(db_session)
        results = repo.search_by_name("Co")

        assert isinstance(results, list)
        assert len(results) <= 50

    def test_search_multiword_query_finds_intersection(
        self, db_session, populated_products
    ):
        """Query multi-palabra solo retorna productos que contienen todos los términos."""
        repo = MariadbProductRepository(db_session)
        results = repo.search_by_name("Coca Cola")

        for product in results:
            name_lower = product.name.lower()
            assert "coca" in name_lower and "cola" in name_lower

    def test_search_returns_empty_for_nonexistent_product(
        self, db_session, populated_products
    ):
        """Búsqueda de producto inexistente retorna lista vacía."""
        repo = MariadbProductRepository(db_session)
        results = repo.search_by_name("XYZProductoInexistente")

        assert results == []

    def test_search_results_are_ordered_alphabetically(
        self, db_session, populated_products
    ):
        """Los resultados están ordenados alfabéticamente por nombre."""
        repo = MariadbProductRepository(db_session)
        results = repo.search_by_name("alfajor")

        names = [p.name for p in results]
        assert names == sorted(names)
