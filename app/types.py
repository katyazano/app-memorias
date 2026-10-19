"""Tipos y utilidades para manejar dinero con Decimal.

SQLite no tiene NUMERIC real: SQLAlchemy lo guardaría como float y perdería
exactitud. `DecimalText` guarda el valor como texto ("116634.40") y siempre
devuelve Decimal.
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

from sqlalchemy.types import String, TypeDecorator

CENT = Decimal("0.01")


def to_decimal(value: Any) -> Decimal:
    """Convierte a Decimal sin pasar por float (floats se leen por su repr)."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def money(value: Any) -> Decimal:
    """Redondea a 2 decimales (mitad hacia arriba)."""
    return to_decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


class DecimalText(TypeDecorator):
    """Decimal almacenado como texto. `places` fija los decimales guardados."""

    impl = String
    cache_ok = True

    def __init__(self, places: int = 2, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.places = places

    def _quant(self) -> Decimal:
        return Decimal(1).scaleb(-self.places)

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return str(to_decimal(value).quantize(self._quant(), rounding=ROUND_HALF_UP))

    def process_result_value(self, value: Any, dialect: Any) -> Optional[Decimal]:
        if value is None:
            return None
        return Decimal(value)
