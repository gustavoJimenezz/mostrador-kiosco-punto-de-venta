"""Script opcional: genera tests/fixtures/sample_5000_products.csv.

Solo necesario si se quiere correr el test de performance (> 5.000 filas).
Los tests unitarios usan datos inline (10 productos) y no requieren este script.

Uso::

    python scripts/generate_fixture.py
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_5000_products.csv"
TOTAL_ROWS = 5_000

CATEGORIES = [
    "Gaseosas", "Aguas", "Jugos", "Lácteos", "Panificados",
    "Snacks", "Golosinas", "Cigarrillos", "Higiene", "Librería",
]

PRODUCTS = [
    "Coca Cola", "Pepsi", "Sprite", "Fanta", "7UP",
    "Agua Villavicencio", "Agua Ser", "Jugo Cepita", "Jugo Ades",
    "Leche La Serenísima", "Leche Sancor", "Yogur Danone",
    "Pan Lactal Bimbo", "Galletitas Oreo", "Galletitas Toddy",
    "Papas Lays", "Papas Pringles", "Doritos", "Maní La Manicera",
    "Chocolate Milka", "Alfajor Havanna", "Alfajor Jorgito",
    "Chiclets Adams", "Caramelos Halls",
    "Cigarrillos Marlboro", "Cigarrillos Lucky",
    "Shampoo Sedal", "Jabón Dove", "Desodorante Rexona",
    "Cuaderno Gloria", "Lapicera Bic",
]

random.seed(42)


def _format_ars(value: float) -> str:
    """Formatea un número en formato argentino: punto de miles, coma decimal."""
    int_part = int(value)
    dec_part = round((value - int_part) * 100)
    int_str = f"{int_part:,}".replace(",", ".")
    return f"{int_str},{dec_part:02d}"


def generate() -> None:
    """Genera el archivo CSV con 5.000 filas de productos de kiosco."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["barcode", "name", "cost_price", "margin_percent", "stock", "min_stock"]
        )

        for i in range(1, TOTAL_ROWS + 1):
            barcode = f"{7790001000000 + i}"
            category = random.choice(CATEGORIES)
            base_name = random.choice(PRODUCTS)
            name = f"{base_name} {category} #{i}"
            cost = round(random.uniform(50.0, 15_000.0), 2)
            margin = round(random.uniform(10.0, 60.0), 2)
            stock = random.randint(0, 200)
            min_stock = random.randint(0, 10)

            writer.writerow([
                barcode,
                name,
                _format_ars(cost),
                _format_ars(margin),
                stock,
                min_stock,
            ])

    print(f"Fixture generado: {OUTPUT_PATH}  ({TOTAL_ROWS} filas)")


if __name__ == "__main__":
    generate()
