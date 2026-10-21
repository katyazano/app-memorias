/**
 * Utilidades para procesar nombres y razones sociales en el módulo de facturas.
 */

// Palabras y regímenes societarios comunes a limpiar en la sugerencia del alias
const SUFIJOS_SOCIEDAD = [
  /\bS\.?A\.?\s+DE\s+C\.?V\.?\b/gi,
  /\bS\.?A\.?P\.?I\.?\s+DE\s+C\.?V\.?\b/gi,
  /\bS\.?\s*DE\s+R\.?L\.?\s+DE\s+C\.?V\.?\b/gi,
  /\bS\.?A\.?\b/gi,
  /\bS\.?C\.?\b/gi,
  /\bS\.?A\.?S\.?\b/gi,
  /\bS\.?C\.?P\.?\b/gi,
  /\bS\.?N\.?C\.?\b/gi,
  /\bS\.?E\.?N\.?C\.?\b/gi,
  /\bS\.?P\.?R\.?\s+DE\s+R\.?L\.?\b/gi,
  /\bSOCIEDAD\s+ANONIMA\s+DE\s+CAPITAL\s+VARIABLE\b/gi,
  /\bSOCIEDAD\s+DE\s+RESPONSABILIDAD\s+LIMITADA\b/gi,
  /\bSOCIEDAD\s+CIVIL\b/gi,
]

const PREPOSICIONES = new Set([
  'A', 'AL', 'DE', 'DEL', 'LA', 'LAS', 'EL', 'LOS', 'EN',
  'PARA', 'POR', 'CON', 'SIN', 'SOBRE', 'HACIA', 'DESDE', 'HASTA', 'ENTRE', 'Y', 'E', 'O', 'U'
])

/**
 * Sugiere un alias abreviado memorable a partir de una razón social.
 * - Elimina sufijos societarios.
 * - Corta en límite de palabra si excede ~32 caracteres.
 * - Nunca termina en preposición ni conjunción.
 * Ej. "DE LA TORRE MATERIALES PARA CONSTRUCCION" -> "DE LA TORRE MATERIALES"
 */
export function sugerirAlias(razonSocial: string, maxLen: number = 32): string {
  if (!razonSocial) return ''
  let limpio = razonSocial.trim()

  for (const sufijo of SUFIJOS_SOCIEDAD) {
    limpio = limpio.replace(sufijo, '')
  }

  // Quitar comas o puntos residuales al final y espacios duplicados
  limpio = limpio.replace(/[,.;:\-_]+$/, '').replace(/\s+/g, ' ').trim()

  const palabras = limpio.split(' ')

  if (limpio.length <= maxLen) {
    while (palabras.length > 0 && PREPOSICIONES.has(palabras[palabras.length - 1].toUpperCase())) {
      palabras.pop()
    }
    return palabras.join(' ').replace(/[,.; ]+$/, '') || limpio
  }

  const seleccionadas: string[] = []
  let currLen = 0
  for (const p of palabras) {
    const adicional = seleccionadas.length === 0 ? p.length : p.length + 1
    if (currLen + adicional <= maxLen) {
      seleccionadas.push(p)
      currLen += adicional
    } else {
      break
    }
  }

  while (seleccionadas.length > 0 && PREPOSICIONES.has(seleccionadas[seleccionadas.length - 1].toUpperCase())) {
    seleccionadas.pop()
  }

  const res = seleccionadas.join(' ').replace(/[,.; ]+$/, '')
  return res || limpio.slice(0, maxLen).trim()
}
