from decimal import Decimal
from typing import Union


UNIDADES = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
DECENAS_10 = ["DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISEIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"]
DECENAS_20 = ["VEINTE", "VEINTIUN", "VEINTIDOS", "VEINTITRES", "VEINTICUATRO", "VEINTICINCO", "VEINTISEIS", "VEINTISIETE", "VEINTIOCHO", "VEINTINUEVE"]
DECENAS = ["", "", "", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
CENTENAS = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]


def _centenas_a_letras(n: int) -> str:
    """Convierte un entero entre 0 y 999 a texto en español."""
    if n == 0:
        return ""
    if n == 100:
        return "CIEN"
    
    c = n // 100
    resto = n % 100
    
    texto_c = CENTENAS[c]
    
    if resto == 0:
        return texto_c
    
    if resto < 10:
        texto_u = UNIDADES[resto]
        return f"{texto_c} {texto_u}".strip()
    elif resto < 20:
        texto_d = DECENAS_10[resto - 10]
        return f"{texto_c} {texto_d}".strip()
    elif resto < 30:
        texto_d = DECENAS_20[resto - 20]
        return f"{texto_c} {texto_d}".strip()
    else:
        d = resto // 10
        u = resto % 10
        if u == 0:
            texto_d = DECENAS[d]
            return f"{texto_c} {texto_d}".strip()
        else:
            texto_d = f"{DECENAS[d]} Y {UNIDADES[u]}"
            return f"{texto_c} {texto_d}".strip()


def numero_a_letras_mxn(monto: Union[float, int, Decimal]) -> str:
    """
    Convierte un importe numérico a formato oficial de pesos mexicanos:
    Ejemplo: 36618.32 -> '(TREINTA Y SEIS MIL SEISCIENTOS DIECIOCHO PESOS 32/100 M.N.)'
    """
    monto_dec = round(Decimal(str(monto)), 2)
    entero = int(monto_dec)
    centavos = int((monto_dec - entero) * 100)

    if entero == 0:
        texto_entero = "CERO"
    elif entero == 1:
        texto_entero = "UN"
    else:
        partes = []
        
        # Millones
        millones = entero // 1_000_000
        resto_millones = entero % 1_000_000
        if millones == 1:
            partes.append("UN MILLON")
        elif millones > 1:
            partes.append(f"{_centenas_a_letras(millones)} MILLONES")
            
        # Miles
        miles = resto_millones // 1_000
        resto_miles = resto_millones % 1_000
        if miles == 1:
            partes.append("MIL")
        elif miles > 1:
            partes.append(f"{_centenas_a_letras(miles)} MIL")
            
        # Centenas
        if resto_miles > 0:
            partes.append(_centenas_a_letras(resto_miles))
            
        texto_entero = " ".join(p for p in partes if p).strip()

    moneda = "PESO" if entero == 1 else "PESOS"
    return f"({texto_entero} {moneda} {centavos:02d}/100 M.N.)"
