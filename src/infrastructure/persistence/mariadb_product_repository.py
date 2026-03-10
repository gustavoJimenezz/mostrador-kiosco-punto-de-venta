"""Adaptador de infraestructura: implementación MariaDB del puerto ProductRepository.

Implementa el protocolo ``ProductRepository`` del dominio usando SQLAlchemy 2.0
con sesiones explícitas. La gestión del ciclo de vida de la sesión (commit,
rollback, close) es responsabilidad del caso de uso o del composition root.

Prerequisito: ``configure_mappings()`` debe haber sido llamado antes de
instanciar este repositorio (ver ``src/infrastructure/persistence/mappings.py``).
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain.models.product import Product
from src.domain.ports.product_repository import ProductRepository


class MariadbProductRepository:
    """Implementación de ``ProductRepository`` sobre MariaDB + SQLAlchemy 2.0.

    Args:
        session: Sesión SQLAlchemy activa. El repositorio NO hace commit ni
            rollback por sí solo; solo llama ``flush()`` para obtener IDs
            generados por la DB sin cerrar la transacción.

    Examples:
        >>> engine = create_mariadb_engine("mysql+pymysql://pos:pos@localhost/kiosco")
        >>> configure_mappings()
        >>> SessionFactory = create_session_factory(engine)
        >>> with SessionFactory() as session:
        ...     repo = MariadbProductRepository(session)
        ...     product = repo.get_by_barcode("7790895000115")
        ...     session.commit()
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_barcode(self, barcode: str) -> Optional[Product]:
        """Busca un producto por código de barras.

        Usa el índice ``ix_products_barcode`` para búsqueda O(log n).

        Args:
            barcode: Código EAN-13 u otro código de barras del producto.

        Returns:
            ``Product`` si existe, ``None`` si no se encuentra.
        """
        stmt = select(Product).where(Product.barcode == barcode)
        return self._session.execute(stmt).scalars().first()

    def get_by_id(self, product_id: int) -> Optional[Product]:
        """Busca un producto por su PK usando el identity map de SQLAlchemy.

        Si el objeto ya está en la sesión activa, lo retorna desde caché
        sin hacer un query adicional a la DB.

        Args:
            product_id: Identificador primario del producto.

        Returns:
            ``Product`` si existe, ``None`` si no se encuentra.
        """
        return self._session.get(Product, product_id)

    def save(self, product: Product) -> Product:
        """Persiste un producto nuevo (INSERT) o actualiza uno existente (UPDATE).

        Si ``product.id`` es ``None``, realiza un INSERT y asigna el id
        generado por la DB al atributo ``product.id`` tras el flush.
        Si ``product.id`` ya tiene valor, SQLAlchemy detecta el objeto
        como "dirty" y emite un UPDATE sobre las columnas modificadas.

        Args:
            product: Entidad ``Product`` a guardar.

        Returns:
            El mismo objeto ``product`` con el ``id`` asignado por la DB.

        Raises:
            ValueError: Si ya existe otro producto con el mismo ``barcode``
                (violación de constraint UNIQUE).
        """
        try:
            self._session.add(product)
            self._session.flush()
            return product
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError(
                f"Ya existe un producto con el código de barras '{product.barcode}'."
            ) from exc

    def _build_fulltext_query(self, query: str) -> str:
        """Convierte texto de búsqueda en expresión BOOLEAN MODE de MariaDB FullText.

        Cada token se convierte en un término obligatorio (+) con wildcard de
        prefijo (*), habilitando búsqueda por prefijo dentro del índice FullText.

        Args:
            query: Texto ingresado por el usuario.

        Returns:
            Expresión BOOLEAN MODE. Ejemplo: "coca cola" -> "+coca* +cola*"
        """
        tokens = query.strip().split()
        return " ".join(f"+{token}*" for token in tokens if token)

    def _search_by_name_fulltext(self, query: str) -> list[Product]:
        """Búsqueda usando el índice ix_products_name_fulltext (BOOLEAN MODE).

        Usa ``MATCH(name) AGAINST(:ft_query IN BOOLEAN MODE)`` con wildcard de
        prefijo para aprovechar el índice FullText creado en la migración
        ``1bafd69c0714``. Requiere query >= 3 chars (``ft_min_word_len=3``).

        Args:
            query: Texto con al menos 3 caracteres.

        Returns:
            Lista de hasta 50 productos que coinciden, ordenados alfabéticamente.
        """
        fulltext_expr = text(
            "MATCH(name) AGAINST(:ft_query IN BOOLEAN MODE)"
        ).bindparams(ft_query=self._build_fulltext_query(query))
        stmt = (
            select(Product)
            .where(fulltext_expr)
            .order_by(Product.name)
            .limit(50)
        )
        return list(self._session.execute(stmt).scalars().all())

    def _search_by_name_ilike(self, query: str) -> list[Product]:
        """Búsqueda ILIKE (full table scan). Fallback para queries cortos.

        Usada cuando el query tiene < 3 caracteres o cuando FullText retorna
        vacío (ej: stopwords configurados en el servidor MariaDB).

        Args:
            query: Texto parcial del nombre a buscar.

        Returns:
            Lista de hasta 50 productos cuyo nombre contiene ``query``,
            ordenados alfabéticamente.
        """
        stmt = (
            select(Product)
            .where(Product.name.ilike(f"%{query}%"))
            .order_by(Product.name)
            .limit(50)
        )
        return list(self._session.execute(stmt).scalars().all())

    def search_by_name(self, query: str) -> list[Product]:
        """Busca productos por nombre usando FullText index o ILIKE como fallback.

        Estrategia:
        - Query >= 3 chars: ``MATCH...AGAINST`` BOOLEAN MODE sobre el índice
          ``ix_products_name_fulltext`` (O(1) index lookup, meta < 50ms con 5k SKUs).
        - Query < 3 chars: ILIKE fallback (``ft_min_word_len=3`` en MariaDB).
        - Fallback ILIKE si FullText retorna vacío (stopwords del servidor).

        Args:
            query: Texto parcial del nombre a buscar. Mínimo 1 carácter.

        Returns:
            Lista de hasta 50 productos cuyo nombre contiene ``query``,
            ordenados alfabéticamente. Puede ser vacía.
        """
        if len(query.strip()) < 3:
            return self._search_by_name_ilike(query)

        results = self._search_by_name_fulltext(query)
        if not results:
            return self._search_by_name_ilike(query)

        return results

    def list_all(self) -> list[Product]:
        """Retorna todos los productos del catálogo ordenados por nombre.

        Returns:
            Lista completa de productos. Puede ser vacía.
        """
        stmt = select(Product).order_by(Product.name)
        return list(self._session.execute(stmt).scalars().all())

    def delete(self, product_id: int) -> None:
        """Elimina un producto por su ID.

        Si el producto no existe, la operación es silenciosa (no lanza excepción),
        conforme al contrato del puerto ``ProductRepository``.

        Args:
            product_id: Identificador primario del producto a eliminar.
        """
        product = self._session.get(Product, product_id)
        if product is not None:
            self._session.delete(product)
            self._session.flush()


# Verificación estática: MariadbProductRepository satisface el protocolo.
# Esta línea falla en tiempo de importación si falta algún método del puerto.
_: ProductRepository = MariadbProductRepository.__new__(MariadbProductRepository)
