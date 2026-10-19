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

/**
 * Sugiere un alias abreviado a partir de una razón social (ej. "CEMENTOS TOLTECA SA DE CV" -> "CEMENTOS TOLTECA")
 */
export function sugerirAlias(razonSocial: string): string {
  if (!razonSocial) return ''
  let limpio = razonSocial.trim()

  for (const sufijo of SUFIJOS_SOCIEDAD) {
    limpio = limpio.replace(sufijo, '')
  }

  // Quitar comas o puntos residuales al final y espacios duplicados
  limpio = limpio.replace(/[,.-]+$/, '').replace(/\s+/g, ' ').trim()

  // Si quedó muy largo (más de 35 caracteres), truncar a las primeras palabras
  if (limpio.length > 35) {
    const palabras = limpio.split(' ')
    let resultado = ''
    for (const p of palabras) {
      if ((resultado + ' ' + p).trim().length <= 35) {
        resultado = (resultado + ' ' + p).trim()
      } else {
        break
      }
    }
    limpio = resultado || limpio.slice(0, 35)
  }

  return limpio || razonSocial.trim().slice(0, 30)
}
