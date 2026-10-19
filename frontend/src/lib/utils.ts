import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Formatea montos en pesos mexicanos: $164,087.92 MXN */
export function formatMoney(amount: string | number | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") return "$0.00 MXN"
  const num = typeof amount === "string" ? parseFloat(amount) : amount
  if (isNaN(num)) return "$0.00 MXN"
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num) + " MXN"
}

/** Formatea montos en pesos sin sufijo MXN: $164,087.92 */
export function formatMoneySimple(amount: string | number | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") return "$0.00"
  const num = typeof amount === "string" ? parseFloat(amount) : amount
  if (isNaN(num)) return "$0.00"
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num)
}

/** Asegura exactamente un solo juego de paréntesis: (CUARENTA Y CUATRO MIL ... M.N.) */
export function formatTextoEnLetra(txt?: string | null): string {
  if (!txt) return ''
  const trimmed = txt.trim()
  if (trimmed.startsWith('(') && trimmed.endsWith(')')) {
    return trimmed
  }
  return `(${trimmed})`
}

/**
 * Formatea el folio de la factura del arquitecto:
 * - Agrega 'F-' solo si el valor es puramente numérico (ej. "23" -> "F-23").
 * - Si ya contiene o empieza con letras (ej. "F-501", "f-501", "A-23"), lo conserva tal cual.
 */
export function formatFolioFactura(folio?: string | null): string {
  if (!folio) return ''
  const f = String(folio).trim()
  if (!f) return ''
  if (/^\d+$/.test(f)) {
    return `F-${f}`
  }
  return f
}


const MESES_ABR = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']

/** Calcula el rango lunes a domingo a partir del número de semana ISO y año */
export function getRangoFromSemanaNumero(semanaNum: number, anio: number = 2026): { inicio: string; fin: string } {
  // 4 de enero siempre cae en la semana 1 según ISO 8601
  const d = new Date(anio, 0, 4);
  const day = (d.getDay() + 6) % 7; // 0 = lunes, ..., 6 = domingo
  const lunesSemana1 = new Date(d);
  lunesSemana1.setDate(d.getDate() - day);

  const lunes = new Date(lunesSemana1);
  lunes.setDate(lunesSemana1.getDate() + (semanaNum - 1) * 7);
  const domingo = new Date(lunes);
  domingo.setDate(lunes.getDate() + 6);

  const pad = (n: number) => String(n).padStart(2, '0');
  const fmt = (dt: Date) => `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`;

  return {
    inicio: fmt(lunes),
    fin: fmt(domingo),
  };
}

/** Formatea rangos de semana: "13 OCT A 19 OCT" */
export function formatRangoSemana(
  inicioStr: string | null | undefined,
  finStr: string | null | undefined,
  semanaNumero?: number | null,
  anioFallback: number = 2026
): string {
  let sIni = inicioStr;
  let sFin = finStr;

  if ((!sIni || !sFin || sIni === 'None' || sFin === 'None') && semanaNumero && semanaNumero > 0) {
    const r = getRangoFromSemanaNumero(semanaNumero, anioFallback);
    sIni = r.inicio;
    sFin = r.fin;
  }

  if (!sIni || !sFin || sIni === 'None' || sFin === 'None') return "—";

  const parseD = (s: string) => {
    if (typeof s === 'string' && /^\d{4}-\d{2}-\d{2}/.test(s)) {
      const [y, m, d] = s.slice(0, 10).split('-').map(Number);
      return new Date(y, m - 1, d);
    }
    return new Date(s);
  };

  const dIni = parseD(sIni);
  const dFin = parseD(sFin);
  if (isNaN(dIni.getTime()) || isNaN(dFin.getTime())) return "—";

  const diaIni = String(dIni.getDate()).padStart(2, '0');
  const mesIni = MESES_ABR[dIni.getMonth()];
  const diaFin = String(dFin.getDate()).padStart(2, '0');
  const mesFin = MESES_ABR[dFin.getMonth()];

  return `${diaIni} ${mesIni} A ${diaFin} ${mesFin}`;
}

const MESES_COMPLETOS = [
  'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO',
  'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE'
]

/** Formatea pie de página en mayúsculas: "ZAPOPAN, JALISCO, A 19 DE OCTUBRE DE 2026." */
export function formatFechaLarga(ciudad: string | null | undefined, fechaStr: string | Date | null | undefined): string {
  const c = (ciudad || 'ZAPOPAN, JALISCO').trim().toUpperCase()
  if (!fechaStr) return `${c}.`
  
  let d: Date
  if (typeof fechaStr === 'string' && /^\d{4}-\d{2}-\d{2}/.test(fechaStr)) {
    const [y, m, day] = fechaStr.slice(0, 10).split('-').map(Number)
    d = new Date(y, m - 1, day)
  } else {
    d = new Date(fechaStr)
  }
  if (isNaN(d.getTime())) return `${c}.`
  
  const dia = d.getDate()
  const mes = MESES_COMPLETOS[d.getMonth()]
  const anio = d.getFullYear()
  return `${c}, A ${dia} DE ${mes} DE ${anio}.`
}

/** Formatea fechas en dd/mm/aaaa */
export function formatDate(dateStr: string | Date | null | undefined): string {
  if (!dateStr) return "—"
  try {
    // Si viene como YYYY-MM-DD
    if (typeof dateStr === "string" && /^\d{4}-\d{2}-\d{2}/.test(dateStr)) {
      const [year, month, day] = dateStr.slice(0, 10).split("-")
      return `${day}/${month}/${year}`
    }
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return "—"
    return new Intl.DateTimeFormat("es-MX", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).format(d)
  } catch {
    return "—"
  }
}

/** Devuelve el estado legible en español de una obra */
export function formatEstadoObra(estado: string | undefined | null): string {
  switch (estado) {
    case 'en_curso':
      return 'En curso'
    case 'pausada':
      return 'Pausada'
    case 'concluida':
      return 'Terminada'
    default:
      return estado || 'En curso'
  }
}
