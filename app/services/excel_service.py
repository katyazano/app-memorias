"""Servicio para la generación de archivos Excel (.xlsx) de memorias de gastos.

Estructura:
- Hoja 1: MEMORIA {numero:02d} (Página 1: Cliente)
- Hoja 2: ARQUITECTO (Página 2: Liquidación Interna, Recuperación y Nómina)
- Fórmulas vivas para sumas, honorarios, IVA, totales, cobrado y saldo.
- Configurado en tamaño carta y ajustado a 1 página de ancho.
"""
import io
import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.models import EstadoMemoria, Memoria, Obra
from app.services.memoria_service import numero_a_letras_mxn


# Paleta de colores profesionales
COLOR_HEADER_BG = "27272A"       # Zinc 800 oscuro
COLOR_HEADER_FG = "FFFFFF"       # Blanco
COLOR_SUBHEADER_BG = "F4F4F5"    # Zinc 100 claro
COLOR_SUBHEADER_FG = "18181B"    # Zinc 900
COLOR_ZEBRA = "FAFAFA"           # Zinc 50 sutil
COLOR_BORDER = "E4E4E7"          # Zinc 200
COLOR_DARK_BORDER = "27272A"     # Zinc 800
COLOR_BORRADOR_BG = "FEF2F2"     # Rojo claro
COLOR_BORRADOR_FG = "991B1B"     # Rojo oscuro

FONT_FAMILY = "Calibri"
FORMAT_CURRENCY = '"$"#,##0.00'
FORMAT_DATE = "DD/MM/YYYY"

MESES_ESP_ABR = {
    1: "ENE", 2: "FEB", 3: "MAR", 4: "ABR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AGO", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DIC"
}


def format_rango_fechas_raya(f_i: Optional[date], f_f: Optional[date], s_num: int, anio: int = 2026) -> str:
    """Retorna el rango en formato '13 OCT A 19 OCT'. Si faltan fechas, calcula con ISO week."""
    if not f_i or not f_f:
        if s_num > 0:
            try:
                d_lunes = date.fromisocalendar(anio, s_num, 1)
                d_domingo = date.fromisocalendar(anio, s_num, 7)
                f_i = f_i or d_lunes
                f_f = f_f or d_domingo
            except Exception:
                pass
    if f_i and f_f:
        m_i = MESES_ESP_ABR.get(f_i.month, f_i.strftime("%b").upper()[:3])
        m_f = MESES_ESP_ABR.get(f_f.month, f_f.strftime("%b").upper()[:3])
        return f"{f_i.day:02d} {m_i} A {f_f.day:02d} {m_f}"
    return f"SEMANA #{s_num}"


def format_texto_en_letra_py(t: Optional[str]) -> str:
    """Asegura exactamente un juego de paréntesis externos."""
    if not t:
        return ""
    clean = str(t).strip()
    while clean.startswith("(") and clean.endswith(")"):
        clean = clean[1:-1].strip()
    return f"({clean.upper()})"


def format_folio_factura(folio: Optional[str]) -> str:
    """
    Formatea el folio de factura del arquitecto:
    - Agrega 'F-' solo si es puramente numérico (ej: '23' -> 'F-23').
    - Si ya contiene o empieza con letras (ej: 'F-501', 'f-501', 'A-23'), se conserva tal cual.
    """
    if not folio:
        return ""
    f = str(folio).strip()
    if not f:
        return ""
    if f.isdigit():
        return f"F-{f}"
    return f



def _aplicar_estilo_rango(
    ws,
    rango: str,
    font: Optional[Font] = None,
    fill: Optional[PatternFill] = None,
    border: Optional[Border] = None,
    alignment: Optional[Alignment] = None,
):
    """Aplica estilos a todas las celdas de un rango (ej. 'A1:D1')."""
    for row in ws[rango]:
        for cell in row:
            if font:
                cell.font = font
            if fill:
                cell.fill = fill
            if border:
                cell.border = border
            if alignment:
                cell.alignment = alignment


def _border_fino() -> Border:
    s = Side(style="thin", color=COLOR_BORDER)
    return Border(left=s, right=s, top=s, bottom=s)


def _border_inferior_doble() -> Border:
    s_top = Side(style="thin", color=COLOR_DARK_BORDER)
    s_bot = Side(style="double", color=COLOR_DARK_BORDER)
    return Border(top=s_top, bottom=s_bot)


def _border_superior_grueso() -> Border:
    s_top = Side(style="thin", color=COLOR_DARK_BORDER)
    return Border(top=s_top)


def parse_fecha(f: Any) -> Optional[date]:
    if not f or f == "None":
        return None
    if isinstance(f, (date, datetime)):
        return f if isinstance(f, date) else f.date()
    if isinstance(f, str):
        try:
            return date.fromisoformat(f[:10])
        except Exception:
            try:
                parts = f.split("/")
                if len(parts) == 3:
                    return date(int(parts[2]), int(parts[1]), int(parts[0]))
            except Exception:
                return None
    return None


def generar_excel_memoria(memoria: Memoria, obra: Obra) -> bytes:
    """Genera el libro Excel con fórmulas vivas idéntico a la hoja MEMORIA 01."""
    snapshot: Dict[str, Any] = {}
    if memoria.snapshot_json:
        try:
            snapshot = json.loads(memoria.snapshot_json)
        except Exception:
            snapshot = {}

    renglones: List[Dict[str, Any]] = snapshot.get("renglones", [])
    totales_snap: Dict[str, Any] = dict(snapshot.get("totales", {}))
    # Asegurar consistencia de acumulados anteriores en totales_snap
    transf_esta = Decimal(str(totales_snap.get("transferencias", "0.00")))
    tot_mem_esta = Decimal(str(totales_snap.get("total_memoria", "0.00")))
    if "transferencias_memorias_anteriores" not in totales_snap or totales_snap["transferencias_memorias_anteriores"] is None:
        acum_transf = Decimal(str(totales_snap.get("acumulado_transferencias", transf_esta)))
        totales_snap["transferencias_memorias_anteriores"] = str(acum_transf - transf_esta)
    if "gastado_memorias_anteriores" not in totales_snap or totales_snap["gastado_memorias_anteriores"] is None:
        gastado_tot = Decimal(str(totales_snap.get("gastado_a_la_fecha", tot_mem_esta)))
        totales_snap["gastado_memorias_anteriores"] = str(gastado_tot - tot_mem_esta)
    anticipos_snap: List[Dict[str, Any]] = snapshot.get("anticipos", [])

    es_borrador = memoria.estado == EstadoMemoria.BORRADOR
    num_mem = memoria.numero or 1
    obra_nombre = obra.nombre or f"OBRA #{obra.id}"
    ubicacion = obra.ubicacion or "NO ESPECIFICADA"
    propietario = obra.propietario or "NO ESPECIFICADO"
    fecha_emision = memoria.fecha_emision or memoria.fecha_fin or date.today()
    fecha_inicio = memoria.fecha_inicio
    fecha_fin = memoria.fecha_fin
    ciudad = memoria.ciudad or "Zapopan, Jalisco"
    folio_arq = memoria.folio_factura_arquitecto or ""
    pct_hon = Decimal(str(memoria.porcentaje_honorarios_usado or obra.porcentaje_honorarios or "10.00"))

    # Agrupar renglones incluidos
    inc = [r for r in renglones if r.get("incluido", True)]
    transferencias = [r for r in inc if r.get("categoria") == "transferencia"]
    efectivo = [r for r in inc if r.get("categoria") == "efectivo"]
    rayas = [r for r in inc if r.get("categoria") == "raya"]
    anticipos = [r for r in (anticipos_snap or inc) if r.get("categoria") == "anticipo" and r.get("incluido", True)]

    # Agrupar rayas por semana
    anio_mem = fecha_inicio.year if isinstance(fecha_inicio, date) else 2026
    mapa_semanas: Dict[int, Dict[str, Any]] = {}
    for r in rayas:
        s = int(r.get("semana_numero") or 0)
        if s not in mapa_semanas:
            mapa_semanas[s] = {
                "semana": s,
                "tipo": "POR DÍA" if r.get("tipo_raya") == "dia" else "DESTAJO",
                "fecha_inicio": r.get("fecha_inicio"),
                "fecha_fin": r.get("fecha_fin"),
                "total": Decimal("0.00"),
                "trabajadores": [],
            }
        else:
            if not mapa_semanas[s]["fecha_inicio"] and r.get("fecha_inicio"):
                mapa_semanas[s]["fecha_inicio"] = r.get("fecha_inicio")
            if not mapa_semanas[s]["fecha_fin"] and r.get("fecha_fin"):
                mapa_semanas[s]["fecha_fin"] = r.get("fecha_fin")
        imp = Decimal(str(r.get("importe", "0.00")))
        mapa_semanas[s]["total"] += imp
        t_raya = "DÍAS" if r.get("tipo_raya") == "dia" else "METROS"
        mapa_semanas[s]["trabajadores"].append({
            "trabajador": r.get("proveedor") or "",
            "oficio": r.get("oficio") or "ALBAÑILERÍA",
            "cantidad": float(r.get("cantidad") or 0.0),
            "tarifa": float(r.get("tarifa") or 0.0),
            "importe": float(imp),
        })

    semanas_lista = [mapa_semanas[k] for k in sorted(mapa_semanas.keys())]

    wb = openpyxl.Workbook()
    # Hoja 1: CLIENTE
    ws_cliente = wb.active
    nombre_hoja_cliente = f"MEMORIA {num_mem:02d}"
    ws_cliente.title = nombre_hoja_cliente

    # Configuración de anchos de columna para Cliente
    ws_cliente.column_dimensions["A"].width = 54
    ws_cliente.column_dimensions["B"].width = 22
    ws_cliente.column_dimensions["C"].width = 16
    ws_cliente.column_dimensions["D"].width = 18

    # Fuentes comunes
    f_titulo = Font(name=FONT_FAMILY, size=15, bold=True, color="18181B")
    f_encabezado = Font(name=FONT_FAMILY, size=9.5, bold=True, color="27272A")
    f_subencabezado = Font(name=FONT_FAMILY, size=8.5, color="52525B")
    f_header_tabla = Font(name=FONT_FAMILY, size=9.5, bold=True, color=COLOR_HEADER_FG)
    f_subheader_col = Font(name=FONT_FAMILY, size=8.5, bold=True, color=COLOR_SUBHEADER_FG)
    f_celda = Font(name=FONT_FAMILY, size=9, color="18181B")
    f_celda_mono = Font(name="Consolas", size=9, color="18181B")
    f_total_tabla = Font(name=FONT_FAMILY, size=9.5, bold=True, color="09090B")
    f_total_mono = Font(name="Consolas", size=9.5, bold=True, color="09090B")
    f_letras = Font(name=FONT_FAMILY, size=8, italic=True, color="52525B")

    fill_header = PatternFill(start_color=COLOR_HEADER_BG, end_color=COLOR_HEADER_BG, fill_type="solid")
    fill_subheader = PatternFill(start_color=COLOR_SUBHEADER_BG, end_color=COLOR_SUBHEADER_BG, fill_type="solid")
    fill_total = PatternFill(start_color="F4F4F5", end_color="F4F4F5", fill_type="solid")

    row_idx = 1

    # Aviso visible si es borrador
    if es_borrador:
        ws_cliente.merge_cells("A1:D1")
        cell_borr = ws_cliente["A1"]
        cell_borr.value = "[ DOCUMENTO EN BORRADOR - PREVISUALIZACIÓN NO OFICIAL ]"
        cell_borr.font = Font(name=FONT_FAMILY, size=10, bold=True, color=COLOR_BORRADOR_FG)
        cell_borr.fill = PatternFill(start_color=COLOR_BORRADOR_BG, end_color=COLOR_BORRADOR_BG, fill_type="solid")
        cell_borr.alignment = Alignment(horizontal="center", vertical="center")
        row_idx += 1

    # 1. Encabezado principal
    r_tit = row_idx
    ws_cliente[f"A{r_tit}"] = f"MEMORIA {num_mem:02d}"
    ws_cliente[f"A{r_tit}"].font = f_titulo

    ws_cliente[f"C{r_tit}"] = "FECHA:"
    ws_cliente[f"C{r_tit}"].font = f_encabezado
    ws_cliente[f"D{r_tit}"] = fecha_emision.strftime("%d/%m/%Y") if isinstance(fecha_emision, date) else str(fecha_emision)
    ws_cliente[f"D{r_tit}"].font = f_celda_mono
    ws_cliente[f"D{r_tit}"].alignment = Alignment(horizontal="right")

    row_idx += 1
    ws_cliente[f"A{row_idx}"] = f"OBRA: {obra_nombre.upper()}"
    ws_cliente[f"A{row_idx}"].font = f_encabezado
    ws_cliente[f"C{row_idx}"] = "CIUDAD:"
    ws_cliente[f"C{row_idx}"].font = f_subencabezado
    ws_cliente[f"D{row_idx}"] = ciudad.upper()
    ws_cliente[f"D{row_idx}"].font = f_celda
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 1
    ws_cliente[f"A{row_idx}"] = f"UBICACIÓN: {ubicacion.upper()}"
    ws_cliente[f"A{row_idx}"].font = f_subencabezado
    ws_cliente[f"C{row_idx}"] = "PERIODO:"
    ws_cliente[f"C{row_idx}"].font = f_subencabezado
    periodo_txt = f"{fecha_inicio.strftime('%d/%m/%Y') if fecha_inicio else ''} AL {fecha_fin.strftime('%d/%m/%Y') if fecha_fin else ''}"
    ws_cliente[f"D{row_idx}"] = periodo_txt
    ws_cliente[f"D{row_idx}"].font = f_celda_mono
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 1
    ws_cliente[f"A{row_idx}"] = f"PROPIETARIO: {propietario.upper()}"
    ws_cliente[f"A{row_idx}"].font = f_subencabezado
    if folio_arq:
        ws_cliente[f"C{row_idx}"] = "FACTURA ARQ:"
        ws_cliente[f"C{row_idx}"].font = f_encabezado
        ws_cliente[f"D{row_idx}"] = format_folio_factura(folio_arq)
        ws_cliente[f"D{row_idx}"].font = f_celda_mono
        ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 2  # Separador

    # TABLA 1: TRANSFERENCIAS
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    ws_cliente[f"A{row_idx}"] = "TRANSFERENCIAS:"
    ws_cliente[f"A{row_idx}"].font = f_header_tabla
    ws_cliente[f"A{row_idx}"].fill = fill_header
    ws_cliente[f"D{row_idx}"] = "IMPORTE"
    ws_cliente[f"D{row_idx}"].font = f_header_tabla
    ws_cliente[f"D{row_idx}"].fill = fill_header
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_cliente, f"A{row_idx}:D{row_idx}", fill=fill_header)

    row_idx += 1
    for col_l, tit in [("A", "CONCEPTO:"), ("B", "COMPROBANTE:"), ("C", "FECHA:"), ("D", "IMPORTE:")]:
        c = ws_cliente[f"{col_l}{row_idx}"]
        c.value = tit
        c.font = f_subheader_col
        c.fill = fill_subheader
        if col_l == "D":
            c.alignment = Alignment(horizontal="right")

    row_idx += 1
    r_ini_transf = row_idx
    if not transferencias:
        ws_cliente[f"A{row_idx}"] = "SIN PAGOS POR TRANSFERENCIA EN EL PERIODO"
        ws_cliente[f"A{row_idx}"].font = Font(name=FONT_FAMILY, size=9, italic=True, color="71717A")
        ws_cliente[f"D{row_idx}"] = 0.0
        ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
        row_idx += 1
    else:
        for t in transferencias:
            prov = (t.get("proveedor") or "").strip().upper()
            conc = (t.get("concepto") or "").strip().upper()
            conc_full = f"{prov}: {conc}" if prov else conc
            comp = (t.get("comprobante") or "—").strip().upper()
            f_d = parse_fecha(t.get("fecha"))
            imp = float(Decimal(str(t.get("importe", "0.00"))))

            ws_cliente[f"A{row_idx}"] = conc_full
            ws_cliente[f"A{row_idx}"].font = f_celda
            if len(conc_full) > 40:
                ws_cliente[f"A{row_idx}"].alignment = Alignment(wrap_text=True, vertical="center")
                ws_cliente.row_dimensions[row_idx].height = 28
            else:
                ws_cliente[f"A{row_idx}"].alignment = Alignment(vertical="center")

            ws_cliente[f"B{row_idx}"] = comp
            ws_cliente[f"B{row_idx}"].font = f_celda_mono

            if f_d:
                ws_cliente[f"C{row_idx}"] = f_d
                ws_cliente[f"C{row_idx}"].number_format = FORMAT_DATE
            else:
                ws_cliente[f"C{row_idx}"] = "—"
            ws_cliente[f"C{row_idx}"].font = f_celda_mono
            ws_cliente[f"C{row_idx}"].alignment = Alignment(horizontal="center")

            ws_cliente[f"D{row_idx}"] = imp
            ws_cliente[f"D{row_idx}"].font = f_celda_mono
            ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
            ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
            _aplicar_estilo_rango(ws_cliente, f"A{row_idx}:D{row_idx}", border=_border_fino())
            row_idx += 1

    r_fin_transf = row_idx - 1
    # Total Transferencias
    r_tot_transf = row_idx
    ws_cliente.merge_cells(f"A{r_tot_transf}:C{r_tot_transf}")
    ws_cliente[f"A{r_tot_transf}"] = "PAGOS TRANSFER. DE ESTA MEMORIA:"
    ws_cliente[f"A{r_tot_transf}"].font = f_total_tabla
    ws_cliente[f"A{r_tot_transf}"].alignment = Alignment(horizontal="right")
    ws_cliente[f"D{r_tot_transf}"] = f"=ROUND(SUM(D{r_ini_transf}:D{r_fin_transf}),2)"
    ws_cliente[f"D{r_tot_transf}"].font = f_total_mono
    ws_cliente[f"D{r_tot_transf}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{r_tot_transf}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_cliente, f"A{r_tot_transf}:D{r_tot_transf}", fill=fill_total, border=_border_inferior_doble())

    row_idx += 2  # Espacio

    # BLOQUE RESUMEN DE TRANSFERENCIAS
    ws_cliente.merge_cells(f"B{row_idx}:C{row_idx}")
    ws_cliente[f"B{row_idx}"] = "RESUMEN DE TRANSFERENCIAS"
    ws_cliente[f"B{row_idx}"].font = Font(name=FONT_FAMILY, size=9, bold=True, color="27272A")
    row_idx += 1

    r_acum_ant = row_idx
    ws_cliente.merge_cells(f"B{row_idx}:C{row_idx}")
    ws_cliente[f"B{row_idx}"] = "ACUMULADO A LA FECHA:"
    ws_cliente[f"B{row_idx}"].font = f_subencabezado
    val_transf_ant = float(Decimal(str(totales_snap.get("transferencias_memorias_anteriores", "0.00"))))
    ws_cliente[f"D{row_idx}"] = val_transf_ant
    ws_cliente[f"D{row_idx}"].font = f_celda_mono
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 1
    r_de_esta = row_idx
    ws_cliente.merge_cells(f"B{row_idx}:C{row_idx}")
    ws_cliente[f"B{row_idx}"] = "DE ESTA MEMORIA:"
    ws_cliente[f"B{row_idx}"].font = f_subencabezado
    ws_cliente[f"D{row_idx}"] = f"=D{r_tot_transf}"
    ws_cliente[f"D{row_idx}"].font = f_celda_mono
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 1
    r_tot_acum_transf = row_idx
    ws_cliente.merge_cells(f"B{row_idx}:C{row_idx}")
    ws_cliente[f"B{row_idx}"] = "TOTAL:"
    ws_cliente[f"B{row_idx}"].font = f_encabezado
    ws_cliente[f"D{row_idx}"] = f"=ROUND(SUM(D{r_acum_ant}:D{r_de_esta}),2)"
    ws_cliente[f"D{row_idx}"].font = f_total_mono
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_cliente, f"B{row_idx}:D{row_idx}", border=_border_superior_grueso())

    row_idx += 2  # Espacio

    # TABLA 2: NOTAS Y FACTURAS EN EFECTIVO
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    ws_cliente[f"A{row_idx}"] = "NOTAS Y FACTURAS EN EFECTIVO:"
    ws_cliente[f"A{row_idx}"].font = f_header_tabla
    ws_cliente[f"A{row_idx}"].fill = fill_header
    ws_cliente[f"D{row_idx}"] = "IMPORTE"
    ws_cliente[f"D{row_idx}"].font = f_header_tabla
    ws_cliente[f"D{row_idx}"].fill = fill_header
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_cliente, f"A{row_idx}:D{row_idx}", fill=fill_header)

    row_idx += 1
    for col_l, tit in [("A", "CONCEPTO:"), ("B", "COMPROBANTE:"), ("C", "FECHA:"), ("D", "IMPORTE:")]:
        c = ws_cliente[f"{col_l}{row_idx}"]
        c.value = tit
        c.font = f_subheader_col
        c.fill = fill_subheader
        if col_l == "D":
            c.alignment = Alignment(horizontal="right")

    row_idx += 1
    r_ini_efec = row_idx
    if not efectivo:
        ws_cliente[f"A{row_idx}"] = "SIN GASTOS EN EFECTIVO EN EL PERIODO"
        ws_cliente[f"A{row_idx}"].font = Font(name=FONT_FAMILY, size=9, italic=True, color="71717A")
        ws_cliente[f"D{row_idx}"] = 0.0
        ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
        row_idx += 1
    else:
        for e in efectivo:
            prov = (e.get("proveedor") or "").strip().upper()
            conc = (e.get("concepto") or "").strip().upper()
            conc_full = f"{prov}: {conc}" if prov else conc
            comp = (e.get("comprobante") or "—").strip().upper()
            f_d = parse_fecha(e.get("fecha"))
            imp = float(Decimal(str(e.get("importe", "0.00"))))

            ws_cliente[f"A{row_idx}"] = conc_full
            ws_cliente[f"A{row_idx}"].font = f_celda
            if len(conc_full) > 40:
                ws_cliente[f"A{row_idx}"].alignment = Alignment(wrap_text=True, vertical="center")
                ws_cliente.row_dimensions[row_idx].height = 28
            else:
                ws_cliente[f"A{row_idx}"].alignment = Alignment(vertical="center")

            ws_cliente[f"B{row_idx}"] = comp
            ws_cliente[f"B{row_idx}"].font = f_celda_mono

            if f_d:
                ws_cliente[f"C{row_idx}"] = f_d
                ws_cliente[f"C{row_idx}"].number_format = FORMAT_DATE
            else:
                ws_cliente[f"C{row_idx}"] = "—"
            ws_cliente[f"C{row_idx}"].font = f_celda_mono
            ws_cliente[f"C{row_idx}"].alignment = Alignment(horizontal="center")

            ws_cliente[f"D{row_idx}"] = imp
            ws_cliente[f"D{row_idx}"].font = f_celda_mono
            ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
            ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
            _aplicar_estilo_rango(ws_cliente, f"A{row_idx}:D{row_idx}", border=_border_fino())
            row_idx += 1

    r_fin_efec = row_idx - 1
    r_tot_efec = row_idx
    ws_cliente.merge_cells(f"A{r_tot_efec}:C{r_tot_efec}")
    ws_cliente[f"A{r_tot_efec}"] = "TOTAL NOTAS Y FACTURAS EN EFECTIVO:"
    ws_cliente[f"A{r_tot_efec}"].font = f_total_tabla
    ws_cliente[f"A{r_tot_efec}"].alignment = Alignment(horizontal="right")
    ws_cliente[f"D{r_tot_efec}"] = f"=ROUND(SUM(D{r_ini_efec}:D{r_fin_efec}),2)"
    ws_cliente[f"D{r_tot_efec}"].font = f_total_mono
    ws_cliente[f"D{r_tot_efec}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{r_tot_efec}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_cliente, f"A{r_tot_efec}:D{r_tot_efec}", fill=fill_total, border=_border_inferior_doble())

    row_idx += 2  # Espacio

    # TABLA 3: RAYAS
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    ws_cliente[f"A{row_idx}"] = "RAYAS:"
    ws_cliente[f"A{row_idx}"].font = f_header_tabla
    ws_cliente[f"A{row_idx}"].fill = fill_header
    ws_cliente[f"D{row_idx}"] = "IMPORTE"
    ws_cliente[f"D{row_idx}"].font = f_header_tabla
    ws_cliente[f"D{row_idx}"].fill = fill_header
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_cliente, f"A{row_idx}:D{row_idx}", fill=fill_header)

    row_idx += 1
    for col_l, tit in [("A", "CONCEPTO:"), ("B", "COMPROBANTE:"), ("C", "FECHA:"), ("D", "IMPORTE:")]:
        c = ws_cliente[f"{col_l}{row_idx}"]
        c.value = tit
        c.font = f_subheader_col
        c.fill = fill_subheader
        if col_l == "D":
            c.alignment = Alignment(horizontal="right")

    row_idx += 1
    r_ini_rayas = row_idx
    if not semanas_lista:
        ws_cliente[f"A{row_idx}"] = "SIN RAYAS DE ALBAÑILERÍA EN EL PERIODO"
        ws_cliente[f"A{row_idx}"].font = Font(name=FONT_FAMILY, size=9, italic=True, color="71717A")
        ws_cliente[f"D{row_idx}"] = 0.0
        ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
        row_idx += 1
    else:
        for sem in semanas_lista:
            s_num = sem["semana"]
            s_tipo = sem["tipo"]
            f_i = parse_fecha(sem.get("fecha_inicio"))
            f_f = parse_fecha(sem.get("fecha_fin"))
            rango_str = format_rango_fechas_raya(f_i, f_f, s_num, anio_mem)

            ws_cliente[f"A{row_idx}"] = f"SEMANA # {s_num}"
            ws_cliente[f"A{row_idx}"].font = f_encabezado
            ws_cliente[f"B{row_idx}"] = s_tipo
            ws_cliente[f"B{row_idx}"].font = f_celda_mono
            ws_cliente[f"C{row_idx}"] = rango_str
            ws_cliente[f"C{row_idx}"].font = f_celda_mono
            ws_cliente[f"C{row_idx}"].alignment = Alignment(horizontal="center")
            ws_cliente[f"D{row_idx}"] = float(sem["total"])
            ws_cliente[f"D{row_idx}"].font = f_celda_mono
            ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
            ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
            _aplicar_estilo_rango(ws_cliente, f"A{row_idx}:D{row_idx}", border=_border_fino())
            row_idx += 1

    r_fin_rayas = row_idx - 1
    r_tot_rayas = row_idx
    ws_cliente.merge_cells(f"A{r_tot_rayas}:C{r_tot_rayas}")
    ws_cliente[f"A{r_tot_rayas}"] = "SUBTOTAL:"
    ws_cliente[f"A{r_tot_rayas}"].font = f_total_tabla
    ws_cliente[f"A{r_tot_rayas}"].alignment = Alignment(horizontal="right")
    ws_cliente[f"D{r_tot_rayas}"] = f"=ROUND(SUM(D{r_ini_rayas}:D{r_fin_rayas}),2)"
    ws_cliente[f"D{r_tot_rayas}"].font = f_total_mono
    ws_cliente[f"D{r_tot_rayas}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{r_tot_rayas}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_cliente, f"A{r_tot_rayas}:D{r_tot_rayas}", fill=fill_total, border=_border_inferior_doble())

    row_idx += 2  # Espacio

    # CIERRE FINANCIERO (HONORARIOS, IVA, TOTALES)
    # Porcentaje de honorarios en celda viva C{row_idx}
    r_pct_row = row_idx
    ws_cliente[f"B{row_idx}"] = "PORCENTAJE DE HONORARIOS:"
    ws_cliente[f"B{row_idx}"].font = f_subencabezado
    ws_cliente[f"C{row_idx}"] = float(pct_hon / Decimal("100.0"))
    ws_cliente[f"C{row_idx}"].font = f_encabezado
    ws_cliente[f"C{row_idx}"].number_format = "0.00%"
    ws_cliente[f"C{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 1
    r_hon_transf = row_idx
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    ws_cliente[f"A{row_idx}"] = f"HONORARIOS {pct_hon}% (PAGOS TRANSF.)"
    ws_cliente[f"A{row_idx}"].font = f_encabezado
    ws_cliente[f"D{row_idx}"] = f"=ROUND(D{r_tot_transf}*C{r_pct_row},2)"
    ws_cliente[f"D{row_idx}"].font = f_celda_mono
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 1
    r_hon_efec = row_idx
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    ws_cliente[f"A{row_idx}"] = f"HONORARIOS {pct_hon}% (PAGOS EFECTIVO)"
    ws_cliente[f"A{row_idx}"].font = f_encabezado
    ws_cliente[f"D{row_idx}"] = f"=ROUND(D{r_tot_efec}*C{r_pct_row},2)"
    ws_cliente[f"D{row_idx}"].font = f_celda_mono
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 1
    r_hon_rayas = row_idx
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    ws_cliente[f"A{row_idx}"] = f"HONORARIOS {pct_hon}% (PAGOS DE RAYAS)"
    ws_cliente[f"A{row_idx}"].font = f_encabezado
    ws_cliente[f"D{row_idx}"] = f"=ROUND(D{r_tot_rayas}*C{r_pct_row},2)"
    ws_cliente[f"D{row_idx}"].font = f_celda_mono
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 1
    r_subtot_hon = row_idx
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    ws_cliente[f"A{row_idx}"] = "SUBTOTAL"
    ws_cliente[f"A{row_idx}"].font = f_total_tabla
    ws_cliente[f"A{row_idx}"].alignment = Alignment(horizontal="right")
    ws_cliente[f"D{row_idx}"] = f"=ROUND(SUM(D{r_tot_rayas},D{r_hon_transf}:D{r_hon_rayas}),2)"
    ws_cliente[f"D{row_idx}"].font = f_total_mono
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_cliente, f"A{row_idx}:D{row_idx}", border=_border_superior_grueso())

    row_idx += 1
    r_iva = row_idx
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    ws_cliente[f"A{row_idx}"] = "IVA 16%"
    ws_cliente[f"A{row_idx}"].font = f_encabezado
    ws_cliente[f"D{row_idx}"] = f"=ROUND(D{r_subtot_hon}*0.16,2)"
    ws_cliente[f"D{row_idx}"].font = f_celda_mono
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 1
    r_factura = row_idx
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    fol_fmt = format_folio_factura(folio_arq)
    fol_label = f"IMPORTE DE ESTA MEMORIA {fol_fmt}" if fol_fmt else "IMPORTE DE ESTA MEMORIA (FACTURA)"
    ws_cliente[f"A{row_idx}"] = fol_label
    ws_cliente[f"A{row_idx}"].font = f_total_tabla
    ws_cliente[f"D{row_idx}"] = f"=ROUND(SUM(D{r_subtot_hon}:D{r_iva}),2)"
    ws_cliente[f"D{row_idx}"].font = f_total_mono
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_cliente, f"A{row_idx}:D{row_idx}", border=_border_superior_grueso())

    # Texto en letra de la factura
    row_idx += 1
    txt_fac = snapshot.get("importe_factura_texto") or totales_snap.get("importe_factura_texto") or getattr(memoria, "importe_factura_texto", None) or ""
    if txt_fac:
        ws_cliente.merge_cells(f"A{row_idx}:D{row_idx}")
        ws_cliente[f"A{row_idx}"] = format_texto_en_letra_py(txt_fac)
        ws_cliente[f"A{row_idx}"].font = f_letras
        ws_cliente[f"A{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 1
    r_total_mem = row_idx
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    ws_cliente[f"A{row_idx}"] = "IMPORTE DE ESTA MEMORIA:"
    ws_cliente[f"A{row_idx}"].font = Font(name=FONT_FAMILY, size=10.5, bold=True, color="09090B")
    ws_cliente[f"D{row_idx}"] = f"=ROUND(SUM(D{r_tot_transf},D{r_tot_efec},D{r_factura}),2)"
    ws_cliente[f"D{row_idx}"].font = Font(name="Consolas", size=10.5, bold=True, color="09090B")
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_cliente, f"A{row_idx}:D{row_idx}", fill=fill_subheader, border=_border_superior_grueso())

    # Texto en letra del total de memoria
    row_idx += 1
    txt_tot = snapshot.get("total_texto") or totales_snap.get("total_texto") or memoria.total_texto or ""
    if txt_tot:
        ws_cliente.merge_cells(f"A{row_idx}:D{row_idx}")
        ws_cliente[f"A{row_idx}"] = format_texto_en_letra_py(txt_tot)
        ws_cliente[f"A{row_idx}"].font = f_letras
        ws_cliente[f"A{row_idx}"].alignment = Alignment(horizontal="right")

    # IMPORTE DE MEMORIAS ANTERIORES: (celda visible y editable con su valor real)
    row_idx += 1
    r_mem_ant = row_idx
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    ws_cliente[f"A{row_idx}"] = "IMPORTE DE MEMORIAS ANTERIORES:"
    ws_cliente[f"A{row_idx}"].font = f_subencabezado
    val_gastado_ant = float(Decimal(str(totales_snap.get("gastado_memorias_anteriores", "0.00"))))
    ws_cliente[f"D{row_idx}"] = val_gastado_ant
    ws_cliente[f"D{row_idx}"].font = f_celda_mono
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")

    # IMPORTE DE MEMORIA 01 A {num_mem:02d}: apunta a celdas visibles
    row_idx += 1
    r_mem_01_N = row_idx
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    ws_cliente[f"A{row_idx}"] = f"IMPORTE DE MEMORIA 01 A {num_mem:02d}:"
    ws_cliente[f"A{row_idx}"].font = f_subencabezado
    ws_cliente[f"D{row_idx}"] = f"=ROUND(D{r_mem_ant}+D{r_total_mem},2)"
    ws_cliente[f"D{row_idx}"].font = f_celda_mono
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 1
    r_gastado_fecha = row_idx
    ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
    ws_cliente[f"A{row_idx}"] = "GASTADO A LA FECHA:"
    ws_cliente[f"A{row_idx}"].font = Font(name=FONT_FAMILY, size=10, bold=True, color="09090B")
    ws_cliente[f"D{row_idx}"] = f"=D{r_mem_01_N}"
    ws_cliente[f"D{row_idx}"].font = Font(name="Consolas", size=10, bold=True, color="09090B")
    ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
    ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_cliente, f"A{row_idx}:D{row_idx}", border=_border_inferior_doble())

    # Texto en letra de gastado a la fecha
    row_idx += 1
    txt_gas = snapshot.get("gastado_a_la_fecha_texto") or totales_snap.get("gastado_a_la_fecha_texto") or getattr(memoria, "gastado_a_la_fecha_texto", None) or ""
    if txt_gas:
        ws_cliente.merge_cells(f"A{row_idx}:D{row_idx}")
        ws_cliente[f"A{row_idx}"] = format_texto_en_letra_py(txt_gas)
        ws_cliente[f"A{row_idx}"].font = f_letras
        ws_cliente[f"A{row_idx}"].alignment = Alignment(horizontal="right")

    row_idx += 2  # Espacio

    # TABLA 4: ANTICIPOS RECIBIDOS (si hay)
    r_tot_anticipos: Optional[int] = None
    if anticipos:
        ws_cliente.merge_cells(f"A{row_idx}:C{row_idx}")
        ws_cliente[f"A{row_idx}"] = "ANTICIPOS RECIBIDOS:"
        ws_cliente[f"A{row_idx}"].font = f_header_tabla
        ws_cliente[f"A{row_idx}"].fill = fill_header
        ws_cliente[f"D{row_idx}"] = "IMPORTE"
        ws_cliente[f"D{row_idx}"].font = f_header_tabla
        ws_cliente[f"D{row_idx}"].fill = fill_header
        ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
        _aplicar_estilo_rango(ws_cliente, f"A{row_idx}:D{row_idx}", fill=fill_header)

        row_idx += 1
        for col_l, tit in [("A", "FECHA:"), ("B", "COMPROBANTE:"), ("C", ""), ("D", "IMPORTE:")]:
            c = ws_cliente[f"{col_l}{row_idx}"]
            c.value = tit
            c.font = f_subheader_col
            c.fill = fill_subheader
            if col_l == "D":
                c.alignment = Alignment(horizontal="right")

        row_idx += 1
        r_ini_ant = row_idx
        for a in anticipos:
            f_d = parse_fecha(a.get("fecha"))
            comp = (a.get("comprobante") or "ANTICIPO").strip().upper()
            imp = float(Decimal(str(a.get("importe", "0.00"))))

            if f_d:
                ws_cliente[f"A{row_idx}"] = f_d
                ws_cliente[f"A{row_idx}"].number_format = FORMAT_DATE
            else:
                ws_cliente[f"A{row_idx}"] = "—"
            ws_cliente[f"A{row_idx}"].font = f_celda_mono
            ws_cliente[f"A{row_idx}"].alignment = Alignment(horizontal="center")
            ws_cliente.merge_cells(f"B{row_idx}:C{row_idx}")
            ws_cliente[f"B{row_idx}"] = comp
            ws_cliente[f"B{row_idx}"].font = f_celda
            ws_cliente[f"D{row_idx}"] = imp
            ws_cliente[f"D{row_idx}"].font = f_celda_mono
            ws_cliente[f"D{row_idx}"].number_format = FORMAT_CURRENCY
            ws_cliente[f"D{row_idx}"].alignment = Alignment(horizontal="right")
            _aplicar_estilo_rango(ws_cliente, f"A{row_idx}:D{row_idx}", border=_border_fino())
            row_idx += 1

        r_fin_ant = row_idx - 1
        r_tot_anticipos = row_idx
        ws_cliente.merge_cells(f"A{r_tot_anticipos}:C{r_tot_anticipos}")
        ws_cliente[f"A{r_tot_anticipos}"] = "TOTAL ANTICIPOS RECIBIDOS:"
        ws_cliente[f"A{r_tot_anticipos}"].font = f_total_tabla
        ws_cliente[f"A{r_tot_anticipos}"].alignment = Alignment(horizontal="right")
        ws_cliente[f"D{r_tot_anticipos}"] = f"=ROUND(SUM(D{r_ini_ant}:D{r_fin_ant}),2)"
        ws_cliente[f"D{r_tot_anticipos}"].font = f_total_mono
        ws_cliente[f"D{r_tot_anticipos}"].number_format = FORMAT_CURRENCY
        ws_cliente[f"D{r_tot_anticipos}"].alignment = Alignment(horizontal="right")
        _aplicar_estilo_rango(ws_cliente, f"A{r_tot_anticipos}:D{r_tot_anticipos}", fill=fill_total, border=_border_inferior_doble())
        row_idx += 2

    # Pie de página: fecha larga en mayúsculas
    meses_es = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
    d_em = fecha_emision if isinstance(fecha_emision, date) else date.today()
    pie_txt = f"{ciudad.upper()}, A {d_em.day} DE {meses_es[d_em.month - 1]} DE {d_em.year}."
    ws_cliente.merge_cells(f"A{row_idx}:D{row_idx}")
    ws_cliente[f"A{row_idx}"] = pie_txt
    ws_cliente[f"A{row_idx}"].font = Font(name=FONT_FAMILY, size=9.5, bold=True, color="52525B")
    ws_cliente[f"A{row_idx}"].alignment = Alignment(horizontal="center")


    # =========================================================================
    # HOJA 2: ARQUITECTO (Liquidación Interna, Recuperación de Caja Chica y Nómina)
    # =========================================================================
    ws_arq = wb.create_sheet(title="ARQUITECTO")

    ws_arq.column_dimensions["A"].width = 38
    ws_arq.column_dimensions["B"].width = 24
    ws_arq.column_dimensions["C"].width = 16
    ws_arq.column_dimensions["D"].width = 14
    ws_arq.column_dimensions["E"].width = 18

    arq_row = 1

    if es_borrador:
        ws_arq.merge_cells("A1:E1")
        c_b = ws_arq["A1"]
        c_b.value = "[ DOCUMENTO EN BORRADOR - PREVISUALIZACIÓN NO OFICIAL ]"
        c_b.font = Font(name=FONT_FAMILY, size=10, bold=True, color=COLOR_BORRADOR_FG)
        c_b.fill = PatternFill(start_color=COLOR_BORRADOR_BG, end_color=COLOR_BORRADOR_BG, fill_type="solid")
        c_b.alignment = Alignment(horizontal="center", vertical="center")
        arq_row += 1

    # Encabezado
    ws_arq[f"A{arq_row}"] = f"RESUMEN MEMORIA {num_mem:02d}:"
    ws_arq[f"A{arq_row}"].font = f_titulo
    arq_row += 1
    ws_arq[f"A{arq_row}"] = f"OBRA: {obra_nombre.upper()} · FECHA: {d_em.strftime('%d/%m/%Y')}"
    ws_arq[f"A{arq_row}"].font = f_subencabezado

    arq_row += 2

    # CUADRO FINANCIERO DEL ARQUITECTO
    ws_arq.merge_cells(f"A{arq_row}:B{arq_row}")
    ws_arq[f"A{arq_row}"] = "HONORARIOS:"
    ws_arq[f"A{arq_row}"].font = Font(name=FONT_FAMILY, size=9.5, bold=True, color="27272A")
    arq_row += 1

    r_arq_hon = arq_row
    ws_arq[f"A{arq_row}"] = "HONORARIOS:"
    ws_arq[f"A{arq_row}"].font = f_encabezado
    ws_arq[f"B{arq_row}"] = f"=ROUND(SUM('{nombre_hoja_cliente}'!D{r_hon_transf}:D{r_hon_rayas}),2)"
    ws_arq[f"B{arq_row}"].font = f_celda_mono
    ws_arq[f"B{arq_row}"].number_format = FORMAT_CURRENCY
    ws_arq[f"B{arq_row}"].alignment = Alignment(horizontal="right")

    arq_row += 1
    r_arq_iva = arq_row
    ws_arq[f"A{arq_row}"] = "IVA TOTAL 16%:"
    ws_arq[f"A{arq_row}"].font = f_encabezado
    ws_arq[f"B{arq_row}"] = f"='{nombre_hoja_cliente}'!D{r_iva}"
    ws_arq[f"B{arq_row}"].font = f_celda_mono
    ws_arq[f"B{arq_row}"].number_format = FORMAT_CURRENCY
    ws_arq[f"B{arq_row}"].alignment = Alignment(horizontal="right")

    arq_row += 1
    r_arq_tot_hon = arq_row
    ws_arq[f"A{arq_row}"] = "TOTAL HONORARIOS:"
    ws_arq[f"A{arq_row}"].font = f_total_tabla
    ws_arq[f"B{arq_row}"] = f"=ROUND(SUM(B{r_arq_hon}:B{r_arq_iva}),2)"
    ws_arq[f"B{arq_row}"].font = f_total_mono
    ws_arq[f"B{arq_row}"].number_format = FORMAT_CURRENCY
    ws_arq[f"B{arq_row}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_arq, f"A{arq_row}:B{arq_row}", border=_border_superior_grueso())

    arq_row += 2

    # REEMBOLSO DE GASTOS
    ws_arq.merge_cells(f"A{arq_row}:B{arq_row}")
    ws_arq[f"A{arq_row}"] = "REEMBOLSO DE GASTOS:"
    ws_arq[f"A{arq_row}"].font = Font(name=FONT_FAMILY, size=9.5, bold=True, color="27272A")
    arq_row += 1

    r_arq_efec = arq_row
    ws_arq[f"A{arq_row}"] = "NOTAS EN EFECTIVO:"
    ws_arq[f"A{arq_row}"].font = f_encabezado
    ws_arq[f"B{arq_row}"] = f"='{nombre_hoja_cliente}'!D{r_tot_efec}"
    ws_arq[f"B{arq_row}"].font = f_celda_mono
    ws_arq[f"B{arq_row}"].number_format = FORMAT_CURRENCY
    ws_arq[f"B{arq_row}"].alignment = Alignment(horizontal="right")

    arq_row += 1
    r_arq_rayas = arq_row
    ws_arq[f"A{arq_row}"] = "NÓMINA:"
    ws_arq[f"A{arq_row}"].font = f_encabezado
    ws_arq[f"B{arq_row}"] = f"='{nombre_hoja_cliente}'!D{r_tot_rayas}"
    ws_arq[f"B{arq_row}"].font = f_celda_mono
    ws_arq[f"B{arq_row}"].number_format = FORMAT_CURRENCY
    ws_arq[f"B{arq_row}"].alignment = Alignment(horizontal="right")

    arq_row += 1
    r_arq_cobrado = arq_row
    ws_arq[f"A{arq_row}"] = "COBRADO:"
    ws_arq[f"A{arq_row}"].font = Font(name=FONT_FAMILY, size=10, bold=True, color="09090B")
    ws_arq[f"B{arq_row}"] = f"=ROUND(SUM(B{r_arq_tot_hon},B{r_arq_efec},B{r_arq_rayas}),2)"
    ws_arq[f"B{arq_row}"].font = Font(name="Consolas", size=10, bold=True, color="09090B")
    ws_arq[f"B{arq_row}"].number_format = FORMAT_CURRENCY
    ws_arq[f"B{arq_row}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_arq, f"A{arq_row}:B{arq_row}", fill=fill_subheader, border=_border_superior_grueso())

    if r_tot_anticipos:
        arq_row += 1
        r_arq_ant = arq_row
        ws_arq[f"A{arq_row}"] = "ANTICIPOS:"
        ws_arq[f"A{arq_row}"].font = f_encabezado
        ws_arq[f"B{arq_row}"] = f"=-('{nombre_hoja_cliente}'!D{r_tot_anticipos})"
        ws_arq[f"B{arq_row}"].font = f_celda_mono
        ws_arq[f"B{arq_row}"].number_format = FORMAT_CURRENCY
        ws_arq[f"B{arq_row}"].alignment = Alignment(horizontal="right")

        arq_row += 1
        ws_arq[f"A{arq_row}"] = f'=IF(B{r_arq_cobrado}+B{r_arq_ant}>=0,"SALDO A MI FAVOR:","ANTICIPO PENDIENTE DE APLICAR:")'
        ws_arq[f"A{arq_row}"].font = Font(name=FONT_FAMILY, size=10, bold=True, color="09090B")
        ws_arq[f"B{arq_row}"] = f"=ROUND(ABS(B{r_arq_cobrado}+B{r_arq_ant}),2)"
        ws_arq[f"B{arq_row}"].font = Font(name="Consolas", size=10, bold=True, color="09090B")
        ws_arq[f"B{arq_row}"].number_format = FORMAT_CURRENCY
        ws_arq[f"B{arq_row}"].alignment = Alignment(horizontal="right")
        _aplicar_estilo_rango(ws_arq, f"A{arq_row}:B{arq_row}", border=_border_inferior_doble())
    else:
        arq_row += 1
        ws_arq[f"A{arq_row}"] = f'=IF(B{r_arq_cobrado}>=0,"SALDO A MI FAVOR:","ANTICIPO PENDIENTE DE APLICAR:")'
        ws_arq[f"A{arq_row}"].font = Font(name=FONT_FAMILY, size=10, bold=True, color="09090B")
        ws_arq[f"B{arq_row}"] = f"=ROUND(ABS(B{r_arq_cobrado}),2)"
        ws_arq[f"B{arq_row}"].font = Font(name="Consolas", size=10, bold=True, color="09090B")
        ws_arq[f"B{arq_row}"].number_format = FORMAT_CURRENCY
        ws_arq[f"B{arq_row}"].alignment = Alignment(horizontal="right")
        _aplicar_estilo_rango(ws_arq, f"A{arq_row}:B{arq_row}", border=_border_inferior_doble())

    arq_row += 3  # Espacio

    # RECUPERACIÓN DE CAJA CHICA (NOTAS DETALLADAS)
    ws_arq.merge_cells(f"A{arq_row}:C{arq_row}")
    ws_arq[f"A{arq_row}"] = "RECUPERACIÓN DE CAJA CHICA."
    ws_arq[f"A{arq_row}"].font = f_header_tabla
    ws_arq[f"A{arq_row}"].fill = fill_header
    ws_arq[f"D{arq_row}"] = "TOTAL:"
    ws_arq[f"D{arq_row}"].font = f_header_tabla
    ws_arq[f"D{arq_row}"].fill = fill_header
    ws_arq[f"D{arq_row}"].alignment = Alignment(horizontal="right")
    ws_arq[f"E{arq_row}"] = f"='{nombre_hoja_cliente}'!D{r_tot_efec}"
    ws_arq[f"E{arq_row}"].font = f_total_mono
    ws_arq[f"E{arq_row}"].fill = fill_header
    ws_arq[f"E{arq_row}"].number_format = FORMAT_CURRENCY
    ws_arq[f"E{arq_row}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_arq, f"A{arq_row}:E{arq_row}", fill=fill_header)

    arq_row += 1
    for col_l, tit in [("A", "CONCEPTO:"), ("B", "COMPROBANTE:"), ("C", "FECHA:"), ("D", ""), ("E", "IMPORTE:")]:
        c = ws_arq[f"{col_l}{arq_row}"]
        c.value = tit
        c.font = f_subheader_col
        c.fill = fill_subheader
        if col_l == "E":
            c.alignment = Alignment(horizontal="right")

    arq_row += 1
    r_ini_det_efec = arq_row
    if not efectivo:
        ws_arq[f"A{arq_row}"] = "SIN MOVIMIENTOS DE CAJA CHICA"
        ws_arq[f"A{arq_row}"].font = Font(name=FONT_FAMILY, size=9, italic=True, color="71717A")
        ws_arq[f"E{arq_row}"] = 0.0
        ws_arq[f"E{arq_row}"].number_format = FORMAT_CURRENCY
        arq_row += 1
    else:
        for e in efectivo:
            prov = (e.get("proveedor") or "").strip().upper()
            conc = (e.get("concepto") or "").strip().upper()
            conc_full = f"{prov}: {conc}" if prov else conc
            comp = (e.get("comprobante") or "—").strip().upper()
            f_d = parse_fecha(e.get("fecha"))
            imp = float(Decimal(str(e.get("importe", "0.00"))))

            ws_arq[f"A{arq_row}"] = conc_full
            ws_arq[f"A{arq_row}"].font = f_celda
            if len(conc_full) > 40:
                ws_arq[f"A{arq_row}"].alignment = Alignment(wrap_text=True, vertical="center")
                ws_arq.row_dimensions[arq_row].height = 28
            else:
                ws_arq[f"A{arq_row}"].alignment = Alignment(vertical="center")

            ws_arq[f"B{arq_row}"] = comp
            ws_arq[f"B{arq_row}"].font = f_celda_mono

            if f_d:
                ws_arq[f"C{arq_row}"] = f_d
                ws_arq[f"C{arq_row}"].number_format = FORMAT_DATE
            else:
                ws_arq[f"C{arq_row}"] = "—"
            ws_arq[f"C{arq_row}"].font = f_celda_mono
            ws_arq[f"C{arq_row}"].alignment = Alignment(horizontal="center")

            ws_arq[f"E{arq_row}"] = imp
            ws_arq[f"E{arq_row}"].font = f_celda_mono
            ws_arq[f"E{arq_row}"].number_format = FORMAT_CURRENCY
            ws_arq[f"E{arq_row}"].alignment = Alignment(horizontal="right")
            _aplicar_estilo_rango(ws_arq, f"A{arq_row}:E{arq_row}", border=_border_fino())
            arq_row += 1

    r_fin_det_efec = arq_row - 1
    r_tot_det_efec = arq_row
    ws_arq.merge_cells(f"A{r_tot_det_efec}:D{r_tot_det_efec}")
    ws_arq[f"A{r_tot_det_efec}"] = "TOTAL:"
    ws_arq[f"A{r_tot_det_efec}"].font = f_total_tabla
    ws_arq[f"A{r_tot_det_efec}"].alignment = Alignment(horizontal="right")
    ws_arq[f"E{r_tot_det_efec}"] = f"=ROUND(SUM(E{r_ini_det_efec}:E{r_fin_det_efec}),2)"
    ws_arq[f"E{r_tot_det_efec}"].font = f_total_mono
    ws_arq[f"E{r_tot_det_efec}"].number_format = FORMAT_CURRENCY
    ws_arq[f"E{r_tot_det_efec}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_arq, f"A{r_tot_det_efec}:E{r_tot_det_efec}", fill=fill_total, border=_border_inferior_doble())

    arq_row += 3  # Espacio

    # DETALLE DE DESTAJOS/RAYAS POR SEMANA
    ws_arq.merge_cells(f"A{arq_row}:C{arq_row}")
    ws_arq[f"A{arq_row}"] = "DETALLE DE DESTAJOS/RAYAS POR SEMANA:"
    ws_arq[f"A{arq_row}"].font = f_header_tabla
    ws_arq[f"A{arq_row}"].fill = fill_header
    ws_arq[f"D{arq_row}"] = "TOTAL NÓMINA:"
    ws_arq[f"D{arq_row}"].font = f_header_tabla
    ws_arq[f"D{arq_row}"].fill = fill_header
    ws_arq[f"D{arq_row}"].alignment = Alignment(horizontal="right")
    ws_arq[f"E{arq_row}"] = f"='{nombre_hoja_cliente}'!D{r_tot_rayas}"
    ws_arq[f"E{arq_row}"].font = f_total_mono
    ws_arq[f"E{arq_row}"].fill = fill_header
    ws_arq[f"E{arq_row}"].number_format = FORMAT_CURRENCY
    ws_arq[f"E{arq_row}"].alignment = Alignment(horizontal="right")
    _aplicar_estilo_rango(ws_arq, f"A{arq_row}:E{arq_row}", fill=fill_header)

    arq_row += 1

    semanas_subtotal_cells: List[str] = []

    if not semanas_lista:
        ws_arq[f"A{arq_row}"] = "SIN REGISTRO DE RAYAS EN EL PERIODO"
        ws_arq[f"A{arq_row}"].font = Font(name=FONT_FAMILY, size=9, italic=True, color="71717A")
        arq_row += 1
    else:
        for sem in semanas_lista:
            s_num = sem["semana"]
            f_i = parse_fecha(sem.get("fecha_inicio"))
            f_f = parse_fecha(sem.get("fecha_fin"))
            rango_str = format_rango_fechas_raya(f_i, f_f, s_num, anio_mem)

            # Cabecera de semana (NUNCA SEMANA #40 (SEMANA #40))
            ws_arq.merge_cells(f"A{arq_row}:C{arq_row}")
            if rango_str != f"SEMANA #{s_num}":
                ws_arq[f"A{arq_row}"] = f"SEMANA #{s_num} ({rango_str})"
            else:
                ws_arq[f"A{arq_row}"] = f"SEMANA #{s_num}"
            ws_arq[f"A{arq_row}"].font = Font(name=FONT_FAMILY, size=9.5, bold=True, color="18181B")
            ws_arq[f"A{arq_row}"].fill = fill_subheader

            ws_arq[f"D{arq_row}"] = "SUBTOTAL:"
            ws_arq[f"D{arq_row}"].font = Font(name=FONT_FAMILY, size=9, bold=True, color="18181B")
            ws_arq[f"D{arq_row}"].fill = fill_subheader
            ws_arq[f"D{arq_row}"].alignment = Alignment(horizontal="right")

            # La celda E{arq_row} tendrá la fórmula SUM de los renglones
            cell_sub_sem = f"E{arq_row}"
            semanas_subtotal_cells.append(cell_sub_sem)
            ws_arq[cell_sub_sem].font = f_total_mono
            ws_arq[cell_sub_sem].fill = fill_subheader
            ws_arq[cell_sub_sem].number_format = FORMAT_CURRENCY
            ws_arq[cell_sub_sem].alignment = Alignment(horizontal="right")
            _aplicar_estilo_rango(ws_arq, f"A{arq_row}:E{arq_row}", fill=fill_subheader, border=_border_fino())

            arq_row += 1
            # Columnas de trabajadores
            for col_l, tit in [("A", "TRABAJADOR"), ("B", "OFICIO"), ("C", "CANTIDAD"), ("D", "TARIFA"), ("E", "IMPORTE")]:
                c = ws_arq[f"{col_l}{arq_row}"]
                c.value = tit
                c.font = Font(name=FONT_FAMILY, size=8, bold=True, color="52525B")
                c.fill = PatternFill(start_color="FAFAFA", end_color="FAFAFA", fill_type="solid")
                if col_l in ("C", "D", "E"):
                    c.alignment = Alignment(horizontal="right")

            arq_row += 1
            r_ini_sem_trab = arq_row

            for t in sem["trabajadores"]:
                ws_arq[f"A{arq_row}"] = t["trabajador"].upper()
                ws_arq[f"A{arq_row}"].font = f_celda
                ws_arq[f"B{arq_row}"] = t["oficio"].upper()
                ws_arq[f"B{arq_row}"].font = f_subencabezado
                ws_arq[f"C{arq_row}"] = t["cantidad"]
                ws_arq[f"C{arq_row}"].font = f_celda_mono
                ws_arq[f"C{arq_row}"].alignment = Alignment(horizontal="right")
                ws_arq[f"D{arq_row}"] = t["tarifa"]
                ws_arq[f"D{arq_row}"].font = f_celda_mono
                ws_arq[f"D{arq_row}"].number_format = FORMAT_CURRENCY
                ws_arq[f"D{arq_row}"].alignment = Alignment(horizontal="right")
                # FÓRMULA VIVA: CANTIDAD * TARIFA
                ws_arq[f"E{arq_row}"] = f"=ROUND(C{arq_row}*D{arq_row},2)"
                ws_arq[f"E{arq_row}"].font = f_celda_mono
                ws_arq[f"E{arq_row}"].number_format = FORMAT_CURRENCY
                ws_arq[f"E{arq_row}"].alignment = Alignment(horizontal="right")
                _aplicar_estilo_rango(ws_arq, f"A{arq_row}:E{arq_row}", border=_border_fino())
                arq_row += 1

            r_fin_sem_trab = arq_row - 1
            # Asignar la fórmula del subtotal de semana
            ws_arq[cell_sub_sem].value = f"=ROUND(SUM(E{r_ini_sem_trab}:E{r_fin_sem_trab}),2)"
            arq_row += 1  # Espacio entre semanas

    # Configuración de página Carta y ajuste al ancho en ambas hojas
    for ws in [ws_cliente, ws_arq]:
        ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
        ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.page_margins.left = 0.472
        ws.page_margins.right = 0.472
        ws.page_margins.top = 0.472
        ws.page_margins.bottom = 0.472
        ws.page_margins.header = 0.2
        ws.page_margins.footer = 0.2

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
