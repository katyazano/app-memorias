"""Cálculo de la memoria. Módulo PURO: sin BD, sin FastAPI, solo Decimal.

    transferencias  = suma de gastos con metodo_pago=transferencia
    efectivo        = suma de gastos con metodo_pago=efectivo
    rayas           = suma de PagoRaya
    hon_transf      = transferencias * %      hon_efectivo = efectivo * %
    hon_rayas       = rayas * %
    honorarios      = hon_transf + hon_efectivo + hon_rayas
    subtotal        = rayas + honorarios
    iva             = subtotal * 0.16
    importe_factura = subtotal + iva
    total_memoria   = transferencias + efectivo + importe_factura
    cobrado         = importe_factura + efectivo
    gastado_a_la_fecha = saldo_inicial_gastado + memorias cerradas anteriores + total_memoria
    anticipos_total = suma de anticipos incluidos
    saldo_a_favor   = cobrado - anticipos_total

Cada resultado intermedio se redondea a 2 decimales (mitad hacia arriba).
`porcentaje` se expresa como 10 = 10 %.
"""
from dataclasses import dataclass, fields
from decimal import Decimal
from typing import Any, Dict, Iterable

from app.types import money, to_decimal

IVA = Decimal("0.16")
CIEN = Decimal("100")


@dataclass(frozen=True)
class TotalesMemoria:
    transferencias: Decimal
    efectivo: Decimal
    rayas: Decimal
    porcentaje_honorarios: Decimal
    hon_transferencias: Decimal
    hon_efectivo: Decimal
    hon_rayas: Decimal
    honorarios: Decimal
    subtotal: Decimal
    iva: Decimal
    importe_factura: Decimal
    total_memoria: Decimal
    cobrado: Decimal
    gastado_a_la_fecha: Decimal
    acumulado_transferencias: Decimal
    anticipos_total: Decimal = Decimal("0.00")
    saldo_a_favor: Decimal = Decimal("0.00")
    gastado_memorias_anteriores: Decimal = Decimal("0.00")
    transferencias_memorias_anteriores: Decimal = Decimal("0.00")
    total_honorarios: Decimal = Decimal("0.00")

    def to_json(self) -> Dict[str, str]:
        """Todo como texto Decimal (nunca float) para snapshot/respuestas."""
        return {f.name: str(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "TotalesMemoria":
        return cls(**{f.name: Decimal(str(data.get(f.name, "0.00"))) for f in fields(cls)})


def sumar(importes: Iterable[Any]) -> Decimal:
    total = Decimal("0.00")
    for i in importes:
        total += to_decimal(i)
    return money(total)


def calcular_memoria(
    transferencias: Any,
    efectivo: Any,
    rayas: Any,
    porcentaje_honorarios: Any,
    *,
    anticipos: Any = 0,
    saldo_inicial_gastado: Any = None,
    saldo_inicial_memorias_anteriores: Any = None,
    gastado_memorias_anteriores: Any = 0,
    saldo_inicial_acumulado: Any = None,
    saldo_inicial_transferencias: Any = None,
    saldo_inicial_efectivo: Any = 0,
    saldo_inicial_rayas: Any = 0,
    transferencias_memorias_anteriores: Any = 0,
) -> TotalesMemoria:
    transferencias = money(transferencias)
    efectivo = money(efectivo)
    rayas = money(rayas)
    anticipos_total = money(anticipos)
    pct = to_decimal(porcentaje_honorarios)
    if pct < 0 or pct > 100:
        raise ValueError("El porcentaje de honorarios debe estar entre 0 y 100.")
    factor = pct / CIEN

    hon_transf = money(transferencias * factor)
    hon_efectivo = money(efectivo * factor)
    hon_rayas = money(rayas * factor)
    honorarios = money(hon_transf + hon_efectivo + hon_rayas)

    subtotal = money(rayas + honorarios)
    iva = money(subtotal * IVA)
    importe_factura = money(subtotal + iva)
    total_honorarios = money(honorarios + iva)
    total_memoria = money(transferencias + efectivo + importe_factura)
    cobrado = money(total_honorarios + efectivo + rayas)
    saldo_a_favor = money(cobrado - anticipos_total)

    # Resolución de saldos iniciales (nuevo modelo de 4 saldos o compatibilidad con nombres anteriores)
    mem_ant_init = saldo_inicial_memorias_anteriores if saldo_inicial_memorias_anteriores is not None else (saldo_inicial_gastado or 0)
    transf_init = saldo_inicial_transferencias if saldo_inicial_transferencias is not None else (saldo_inicial_acumulado or 0)

    gastado = money(to_decimal(mem_ant_init) + to_decimal(gastado_memorias_anteriores) + total_memoria)
    acumulado_transf = money(
        to_decimal(transf_init) + to_decimal(transferencias_memorias_anteriores) + transferencias
    )

    return TotalesMemoria(
        transferencias=transferencias,
        efectivo=efectivo,
        rayas=rayas,
        porcentaje_honorarios=pct,
        hon_transferencias=hon_transf,
        hon_efectivo=hon_efectivo,
        hon_rayas=hon_rayas,
        honorarios=honorarios,
        subtotal=subtotal,
        iva=iva,
        importe_factura=importe_factura,
        total_memoria=total_memoria,
        cobrado=cobrado,
        gastado_a_la_fecha=gastado,
        acumulado_transferencias=acumulado_transf,
        anticipos_total=anticipos_total,
        saldo_a_favor=saldo_a_favor,
        gastado_memorias_anteriores=money(to_decimal(mem_ant_init) + to_decimal(gastado_memorias_anteriores)),
        transferencias_memorias_anteriores=money(to_decimal(transf_init) + to_decimal(transferencias_memorias_anteriores)),
        total_honorarios=total_honorarios,
    )
