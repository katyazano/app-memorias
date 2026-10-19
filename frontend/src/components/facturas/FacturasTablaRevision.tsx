import React from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Trash2,
  HelpCircle,
  FileText,
  Building2,
  Calendar,
  Layers,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { formatMoney, formatDate } from '@/lib/utils'
import type { MetodoPago } from '@/types'

export interface FilaFacturaState {
  id: string // staging_id o uuid provisional
  staging_id: string
  archivo_xml: string
  archivo_pdf?: string | null
  uuid: string
  rfc_emisor: string
  razon_social: string
  proveedor_alias: string
  es_proveedor_nuevo: boolean
  concepto_resumido: string
  comprobante: string
  fecha: string
  importe: string
  metodo_pago: MetodoPago | ''
  requiere_decision_metodo_pago: boolean
  es_duplicado: boolean
  duplicado_info?: {
    obra_nombre: string
    fecha: string
  }
  error_detalle?: string
}

interface FacturasTablaRevisionProps {
  filas: FilaFacturaState[]
  onFilaChange: (id: string, campo: Partial<FilaFacturaState>) => void
  onEliminarFila: (id: string) => void
  onAplicarMetodoATodasLasVacias: (metodo: MetodoPago) => void
}

export function FacturasTablaRevision({
  filas,
  onFilaChange,
  onEliminarFila,
  onAplicarMetodoATodasLasVacias,
}: FacturasTablaRevisionProps) {
  const filasSinMetodo = filas.filter((f) => !f.es_duplicado && !f.metodo_pago).length

  return (
    <div className="space-y-3">
      {/* Barra de atajo rápido si hay filas sin método */}
      {filasSinMetodo > 0 && (
        <div className="bg-amber-50/80 border border-amber-200/90 rounded-lg p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
          <div className="flex items-center space-x-2 text-amber-900">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              Hay <strong>{filasSinMetodo}</strong> {filasSinMetodo === 1 ? 'factura' : 'facturas'} $\le$ $2,000 que
              requieren selección obligatoria de método de pago.
            </span>
          </div>
          <div className="flex items-center space-x-2 self-end sm:self-auto">
            <span className="text-[11px] text-amber-700 font-medium">Marcar vacías como:</span>
            <button
              type="button"
              onClick={() => onAplicarMetodoATodasLasVacias('transferencia')}
              className="px-2 py-1 bg-white hover:bg-zinc-100 text-zinc-800 rounded border border-amber-300 font-medium text-[11px] shadow-2xs"
            >
              Transferencia
            </button>
            <button
              type="button"
              onClick={() => onAplicarMetodoATodasLasVacias('efectivo')}
              className="px-2 py-1 bg-white hover:bg-zinc-100 text-zinc-800 rounded border border-amber-300 font-medium text-[11px] shadow-2xs"
            >
              Efectivo
            </button>
          </div>
        </div>
      )}

      {/* Contenedor de la tabla densa */}
      <div className="bg-white border border-zinc-200 rounded-lg overflow-hidden shadow-2xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-600 font-semibold uppercase text-[10px] tracking-wider">
              <tr>
                <th className="py-2.5 px-3 w-8 text-center">#</th>
                <th className="py-2.5 px-3 w-56">Proveedor y Alias</th>
                <th className="py-2.5 px-3 min-w-[200px]">Concepto Resumido</th>
                <th className="py-2.5 px-3 w-32">Comprobante</th>
                <th className="py-2.5 px-3 w-28">Fecha</th>
                <th className="py-2.5 px-3 w-32 text-right">Importe Total</th>
                <th className="py-2.5 px-3 w-48">Método de Pago</th>
                <th className="py-2.5 px-2 w-10 text-center"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200">
              {filas.map((fila, index) => {
                const totalNum = parseFloat(fila.importe || '0')
                const esMayor2000 = totalNum > 2000
                const faltaMetodo = !fila.es_duplicado && !fila.metodo_pago
                const faltaAlias = !fila.es_duplicado && fila.es_proveedor_nuevo && !fila.proveedor_alias.trim()

                return (
                  <tr
                    key={fila.id}
                    className={`transition-colors ${
                      fila.es_duplicado
                        ? 'bg-red-50/60 text-zinc-700'
                        : faltaMetodo
                        ? 'bg-amber-50/30'
                        : 'hover:bg-zinc-50/70'
                    }`}
                  >
                    {/* Número e indicador */}
                    <td className="py-3 px-3 text-center font-mono text-zinc-400">
                      {fila.es_duplicado ? (
                        <span title="Factura duplicada" className="inline-block text-red-600">
                          <AlertCircle className="w-4 h-4 mx-auto" />
                        </span>
                      ) : (
                        <span>{index + 1}</span>
                      )}
                    </td>

                    {/* Proveedor y Alias */}
                    <td className="py-3 px-3">
                      {fila.es_duplicado ? (
                        <div>
                          <div className="font-semibold text-red-900">{fila.razon_social}</div>
                          <div className="text-[11px] font-mono text-zinc-500">RFC: {fila.rfc_emisor}</div>
                          <div className="mt-1 text-[11px] text-red-700 bg-red-100/70 rounded px-1.5 py-0.5 inline-block">
                            Ya existe en: {fila.duplicado_info?.obra_nombre || 'otra obra'}{' '}
                            {fila.duplicado_info?.fecha ? `(${formatDate(fila.duplicado_info.fecha)})` : ''}
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-mono text-[10px] text-zinc-500 font-semibold">{fila.rfc_emisor}</span>
                            {fila.es_proveedor_nuevo && (
                              <span className="px-1.5 py-0.2 rounded text-[9px] font-semibold bg-zinc-100 text-zinc-700 border border-zinc-200">
                                NUEVO
                              </span>
                            )}
                          </div>
                          <input
                            type="text"
                            value={fila.proveedor_alias}
                            onChange={(e) => onFilaChange(fila.id, { proveedor_alias: e.target.value })}
                            placeholder="Alias comercial (aparece en memoria)"
                            title={fila.razon_social}
                            className={`w-full px-2 py-1 border rounded text-xs transition-colors font-medium ${
                              faltaAlias
                                ? 'border-red-400 bg-red-50 focus:border-red-500'
                                : 'border-zinc-300 bg-white focus:border-zinc-800'
                            }`}
                          />
                          <p className="text-[10px] text-zinc-400 truncate max-w-[220px]" title={fila.razon_social}>
                            {fila.razon_social}
                          </p>
                        </div>
                      )}
                    </td>

                    {/* Concepto Resumido */}
                    <td className="py-3 px-3">
                      {fila.es_duplicado ? (
                        <div className="text-zinc-500 italic">{fila.concepto_resumido}</div>
                      ) : (
                        <div className="space-y-1">
                          <input
                            type="text"
                            value={fila.concepto_resumido}
                            onChange={(e) => onFilaChange(fila.id, { concepto_resumido: e.target.value })}
                            className="w-full px-2 py-1 border border-zinc-300 rounded text-xs bg-white focus:border-zinc-800"
                            placeholder="Descripción del gasto"
                          />
                          <div className="flex items-center space-x-2 text-[10px] text-zinc-400 font-mono">
                            <span title={fila.archivo_xml} className="truncate max-w-[140px]">
                              {fila.archivo_xml}
                            </span>
                            {fila.archivo_pdf ? (
                              <span className="text-emerald-600 font-medium">+ PDF vinculado</span>
                            ) : (
                              <span className="text-zinc-400">Sin PDF</span>
                            )}
                          </div>
                        </div>
                      )}
                    </td>

                    {/* Comprobante / Folio */}
                    <td className="py-3 px-3">
                      {fila.es_duplicado ? (
                        <div className="font-mono text-zinc-500">{fila.comprobante || '—'}</div>
                      ) : (
                        <div>
                          <input
                            type="text"
                            value={fila.comprobante}
                            onChange={(e) => onFilaChange(fila.id, { comprobante: e.target.value })}
                            className="w-full px-2 py-1 border border-zinc-300 rounded text-xs font-mono bg-white focus:border-zinc-800"
                            placeholder="Folio/Serie"
                          />
                          <p className="text-[10px] text-zinc-400 font-mono mt-0.5 truncate" title={fila.uuid}>
                            UUID: {fila.uuid.slice(0, 8)}...
                          </p>
                        </div>
                      )}
                    </td>

                    {/* Fecha */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      {fila.es_duplicado ? (
                        <span className="font-mono text-zinc-500">{formatDate(fila.fecha)}</span>
                      ) : (
                        <input
                          type="date"
                          value={fila.fecha}
                          onChange={(e) => onFilaChange(fila.id, { fecha: e.target.value })}
                          className="px-2 py-1 border border-zinc-300 rounded text-xs font-mono bg-white focus:border-zinc-800"
                        />
                      )}
                    </td>

                    {/* Importe Total (SOLO LECTURA) */}
                    <td className="py-3 px-3 whitespace-nowrap text-right">
                      <span className="font-semibold text-zinc-900 font-mono text-sm block">
                        {formatMoney(fila.importe)}
                      </span>
                      <span className="text-[10px] text-zinc-400 font-medium">Solo lectura (XML)</span>
                    </td>

                    {/* Método de Pago */}
                    <td className="py-3 px-3">
                      {fila.es_duplicado ? (
                        <span className="text-xs text-red-600 font-medium">Rechazado (duplicado)</span>
                      ) : (
                        <div className="space-y-1">
                          <select
                            value={fila.metodo_pago}
                            onChange={(e) =>
                              onFilaChange(fila.id, { metodo_pago: e.target.value as MetodoPago | '' })
                            }
                            className={`w-full px-2 py-1 rounded text-xs font-medium border transition-colors ${
                              faltaMetodo
                                ? 'border-amber-400 bg-amber-50 text-amber-900 ring-2 ring-amber-300 focus:outline-none font-semibold'
                                : 'border-zinc-300 bg-white text-zinc-800 focus:border-zinc-800'
                            }`}
                          >
                            <option value="">-- Seleccionar (Obligatorio) --</option>
                            <option value="transferencia">Transferencia</option>
                            <option value="efectivo">Efectivo</option>
                          </select>

                          {esMayor2000 ? (
                            <p className="text-[10px] text-zinc-500 leading-tight">
                              Sugerido: Transferencia (Total &gt; $2,000)
                            </p>
                          ) : (
                            <p className="text-[10px] text-amber-700 leading-tight font-medium">
                              {faltaMetodo ? '⚠️ Elige el método' : 'Confirmado'}
                            </p>
                          )}
                        </div>
                      )}
                    </td>

                    {/* Acciones */}
                    <td className="py-3 px-2 text-center">
                      <button
                        type="button"
                        onClick={() => onEliminarFila(fila.id)}
                        title="Quitar esta factura del lote"
                        className="p-1 text-zinc-400 hover:text-red-600 hover:bg-zinc-100 rounded transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
