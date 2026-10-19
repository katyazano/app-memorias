from decimal import Decimal

import pytest

from app.services.memoria_calculo import TotalesMemoria, calcular_memoria, sumar


def D(x: str) -> Decimal:
    return Decimal(x)


def test_memoria_01_caso_obligatorio():
    t = calcular_memoria(D("116634.40"), D("10835.20"), D("17109.60"), D("10"))
    assert t.hon_transferencias == D("11663.44")
    assert t.hon_efectivo == D("1083.52")
    assert t.hon_rayas == D("1710.96")
    assert t.honorarios == D("14457.92")
    assert t.subtotal == D("31567.52")
    assert t.iva == D("5050.80")
    assert t.importe_factura == D("36618.32")
    assert t.total_memoria == D("164087.92")
    assert t.cobrado == D("47453.52")
    # Sin saldos previos, lo gastado es el total de la memoria.
    assert t.gastado_a_la_fecha == D("164087.92")


def test_gastado_a_la_fecha_suma_saldo_inicial_y_memorias_cerradas():
    t = calcular_memoria(
        D("116634.40"), D("10835.20"), D("17109.60"), D("10"),
        saldo_inicial_gastado=D("500000.00"),
        gastado_memorias_anteriores=D("200000.50"),
    )
    assert t.gastado_a_la_fecha == D("500000.00") + D("200000.50") + D("164087.92")


def test_acumulado_de_transferencias():
    t = calcular_memoria(
        D("1000.00"), 0, 0, D("10"),
        saldo_inicial_acumulado=D("5000.00"),
        transferencias_memorias_anteriores=D("2500.00"),
    )
    assert t.acumulado_transferencias == D("8500.00")


def test_todo_en_cero():
    t = calcular_memoria(0, 0, 0, D("10"))
    assert t.total_memoria == D("0.00") and t.iva == D("0.00") and t.cobrado == D("0.00")


def test_porcentaje_distinto_por_obra():
    t = calcular_memoria(D("1000"), D("0"), D("0"), D("12.5"))
    assert t.honorarios == D("125.00")
    assert t.subtotal == D("125.00")  # sin rayas: subtotal = honorarios
    assert t.iva == D("20.00")


def test_redondeo_mitad_hacia_arriba_y_sin_float():
    # 0.05 * 10% = 0.005 -> 0.01 (HALF_UP); con float/banker's daría 0.00
    t = calcular_memoria(D("0.05"), 0, 0, D("10"))
    assert t.hon_transferencias == D("0.01")
    assert all(isinstance(getattr(t, k), Decimal) for k in t.to_json())


def test_acepta_float_y_str_sin_perder_centavos():
    assert calcular_memoria(116634.4, "10835.20", 17109.6, 10).total_memoria == D("164087.92")


@pytest.mark.parametrize("pct", [-1, 100.01, 500])
def test_porcentaje_invalido(pct):
    with pytest.raises(ValueError):
        calcular_memoria(1, 1, 1, pct)


def test_json_ida_y_vuelta():
    t = calcular_memoria(D("116634.40"), D("10835.20"), D("17109.60"), D("10"))
    data = t.to_json()
    assert data["total_memoria"] == "164087.92"
    assert TotalesMemoria.from_json(data) == t


def test_sumar():
    assert sumar([D("0.10"), D("0.20"), "0.30"]) == D("0.60")  # 0.1+0.2+0.3 sin error binario


def test_saldo_a_favor_con_anticipos():
    t = calcular_memoria(
        D("116634.40"), D("10835.20"), D("17109.60"), D("10"),
        anticipos=D("20000.00"),
    )
    assert t.cobrado == D("47453.52")
    assert t.anticipos_total == D("20000.00")
    assert t.saldo_a_favor == D("27453.52")


def test_saldo_a_favor_sin_anticipos():
    t = calcular_memoria(
        D("116634.40"), D("10835.20"), D("17109.60"), D("10"),
    )
    assert t.cobrado == D("47453.52")
    assert t.anticipos_total == D("0.00")
    assert t.saldo_a_favor == D("47453.52")


def test_saldo_a_favor_negativo_anticipo_pendiente():
    """Verifica que si anticipo supera a lo cobrado, saldo_a_favor sea negativo (-1263.41 para cobrado 236.59 y anticipo 1500.00)."""
    # transferencias=1154.00, efectivo=200.00, rayas=0, pct=10%
    # hon_transf = 115.40, hon_efec = 20.00 -> hon = 135.40
    # subtotal = 135.40, iva = 21.66 -> factura = 157.06
    # Para cuadrar exactamente cobrado = 236.59:
    # efectivo + factura = 236.59
    # subtotal + iva + efec = 236.59 => subtotal * 1.16 + efec = 236.59
    # Si transferencias=0, rayas=0, efectivo=203.96, pct=10%:
    # honorarios = 20.40, iva = 3.26, factura = 23.66, cobrado = 203.96 + 23.66 = 227.62
    # Más directamente con los componentes que den cobrado exacto:
    # efec=200.00, rayas=0, transf=315.43, pct=10% -> hon=51.54, subtotal=51.54, iva=8.25 -> factura=59.79
    # En cualquier caso, probemos calcular_memoria donde cobrado resulta 236.59 o usemos los importes correspondientes:
    # Si rayas = 175.00, efectivo = 25.00, transf = 96.00, pct = 10%
    # hon = 9.60 + 2.50 + 17.50 = 29.60
    # subtotal = 175 + 29.60 = 204.60
    # iva = 204.60 * 0.16 = 32.74
    # factura = 204.60 + 32.74 = 237.34 -> cobrado = 262.34
    # Para dar cobrado exacto 236.59:
    # subtotal * 1.16 + efectivo = 236.59
    # Si subtotal = 173.78, iva = 27.81, factura = 201.59, efectivo = 35.00 -> cobrado = 236.59
    # subtotal = rayas + honorarios. Si rayas = 150.00, honorarios = 23.78
    # pct = 10%, transferencias = 87.80 -> hon_t = 8.78, efec = 35.00 -> hon_e = 3.50, rayas = 150 -> hon_r = 15.00 -> hon = 27.28
    # Probemos con:
    # transferencias=52.80, efectivo=35.00, rayas=150.00, pct=10%
    # hon_transf = 5.28, hon_efec = 3.50, hon_rayas = 15.00 -> hon = 23.78
    # subtotal = 150 + 23.78 = 173.78
    # iva = 173.78 * 0.16 = 27.8048 -> 27.80
    # importe_factura = 173.78 + 27.80 = 201.58 -> cobrado = 236.58
    # Si transferencias=52.86: hon_t=5.29, hon=23.79, subtotal=173.79, iva=27.81, factura=201.60 -> cobrado=236.60
    # Para 236.59: transferencias=52.80, efectivo=35.01, rayas=150.00, pct=10%:
    # hon_t=5.28, hon_e=3.50, hon_r=15.00 -> hon=23.78, subtotal=173.78, iva=27.80, factura=201.58, cobrado=201.58+35.01=236.59!
    t = calcular_memoria(
        D("52.80"), D("35.01"), D("150.00"), D("10"),
        anticipos=D("1500.00"),
    )
    assert t.cobrado == D("236.59")
    assert t.anticipos_total == D("1500.00")
    assert t.saldo_a_favor == D("-1263.41")
    assert abs(t.saldo_a_favor) == D("1263.41")
