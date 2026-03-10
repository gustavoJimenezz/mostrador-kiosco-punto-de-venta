"""Re-exporta ProductRepository desde product_repository para compatibilidad."""

from src.domain.ports.product_repository import ProductRepository

__all__ = ["ProductRepository"]
