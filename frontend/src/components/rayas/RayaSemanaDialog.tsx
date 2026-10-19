import React, { useState } from 'react'
import { Plus, Trash2, Calendar, UserCheck } from 'lucide-react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { formatMoney } from '@/lib/utils'
import type { Trabajador, TipoRaya, PagosSemanaCreate, FilaSemanaRayaCreate } from '@/types'

interface FilaCaptura {
  id: string
  trabajador_id: number | ''
  tipo: TipoRaya
  cantidad: string
  tarifa: string
}

interface RayaSemanaDialogProps {
  open: boolean
  onClose: () => void
  trabajadores: Trabajador[]
  onSubmit: (data: PagosSemanaCreate) => Promise<void>
  isLoading?: boolean
}

// Calcula el rango por defecto Lunes a Domingo de la semana actual
function getLunesADomingoActual(): { lunes: string; domingo: string } {
  const d = new Date()
  const day = d.getDay() // 0 = dom, 1 = lun, ..., 6 = sab
  const diffToMonday = day === 0 ? -6 : 1 - day
  const lunes = new Date(d)
  lunes.setDate(d.getDate() + diffToMonday)
  const domingo = new Date(lunes)
  domingo.setDate(lunes.getDate() + 6)
  return {
    lunes: lunes.toISOString().slice(0, 10),
    domingo: domingo.toISOString().slice(0, 10),
  }
}

// Calcula el número de semana ISO a partir de la fecha de inicio ("Desde")
function getWeekNumberFromFecha(fechaStr: string): number {
  if (!fechaStr) return 1
  const d = new Date(fechaStr + 'T12:00:00')
  if (isNaN(d.getTime())) return 1
  const target = new Date(d.valueOf())
  const dayNr = (d.getDay() + 6) % 7
  target.setDate(target.getDate() - dayNr + 3)
  const firstThursday = target.valueOf()
  target.setMonth(0, 1)
  if (target.getDay() !== 4) {
    target.setMonth(0, 1 + ((4 - target.getDay() + 7) % 7))
  }
  return 1 + Math.ceil((firstThursday - target.valueOf()) / 604800000)
}

const MESES = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']

export const RayaSemanaDialog: React.FC<RayaSemanaDialogProps> = ({
  open,
  onClose,
  trabajadores,
  onSubmit,
  isLoading,
}) => {
  const { lunes: lunesDef, domingo: domingoDef } = getLunesADomingoActual()

  const [fechaInicio, setFechaInicio] = useState(lunesDef)
  const [fechaFin, setFechaFin] = useState(domingoDef)
  const [filas, setFilas] = useState<FilaCaptura[]>([
    { id: '1', trabajador_id: '', tipo: 'dia', cantidad: '6', tarifa: '50.00' },
  ])
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null)

  // Recalcular semana y etiqueta basados en fechaInicio ("Desde")
  const numSemana = getWeekNumberFromFecha(fechaInicio)
  const dInicio = new Date(fechaInicio + 'T12:00:00')
  const dFin = new Date(fechaFin + 'T12:00:00')
  const diaI = isNaN(dInicio.getTime()) ? '' : dInicio.getDate().toString().padStart(2, '0')
  const mesI = isNaN(dInicio.getTime()) ? '' : MESES[dInicio.getMonth()] || ''
  const diaF = isNaN(dFin.getTime()) ? '' : dFin.getDate().toString().padStart(2, '0')
  const mesF = isNaN(dFin.getTime()) ? '' : MESES[dFin.getMonth()] || ''
  const etiquetaSemana = `Semana ${numSemana}, ${diaI} ${mesI} A ${diaF} ${mesF}`

  // Detectar duplicados de trabajadores en la misma semana
  const trabajadoresContados: Record<number, number> = {}
  filas.forEach((f) => {
    if (f.trabajador_id) {
      trabajadoresContados[Number(f.trabajador_id)] = (trabajadoresContados[Number(f.trabajador_id)] || 0) + 1
    }
  })

  const handleAgregarFila = () => {
    setFilas((prev) => [
      ...prev,
      {
        id: Math.random().toString(),
        trabajador_id: '',
        tipo: 'dia',
        cantidad: '6',
        tarifa: '50.00',
      },
    ])
  }

  const handleEliminarFila = (idFila: string) => {
    if (filas.length > 1) {
      setFilas((prev) => prev.filter((f) => f.id !== idFila))
    }
  }

  const handleFilaChange = (idFila: string, campo: Partial<FilaCaptura>) => {
    setErrorGeneral(null)
    setFilas((prev) => prev.map((f) => (f.id === idFila ? { ...f, ...campo } : f)))
  }

  // Previsualización de total en vivo (usando redondeo exacto a 2 decimales para cada fila)
  let totalSuma = 0
  filas.forEach((f) => {
    const cant = parseFloat(f.cantidad || '0')
    const tar = parseFloat(f.tarifa || '0')
    if (!isNaN(cant) && !isNaN(tar) && cant > 0 && tar > 0) {
      totalSuma += Math.round(cant * tar * 100) / 100
    }
  })

  const handleGuardar = async () => {
    setErrorGeneral(null)

    // Validar filas
    let tieneErrores = false
    const filasValidas: FilaSemanaRayaCreate[] = []

    for (const f of filas) {
      const cant = parseFloat(f.cantidad)
      const tar = parseFloat(f.tarifa)
      if (!f.trabajador_id || isNaN(cant) || cant <= 0 || isNaN(tar) || tar <= 0) {
        tieneErrores = true
        continue
      }

      filasValidas.push({
        trabajador_id: Number(f.trabajador_id),
        tipo: f.tipo,
        cantidad: cant.toString(),
        tarifa: tar.toFixed(2),
      })
    }

    if (tieneErrores || filasValidas.length === 0) {
      setErrorGeneral('Revisa las filas en rojo. Todos los campos son obligatorios y deben ser mayores a 0.')
      return
    }

    try {
      const payload: PagosSemanaCreate = {
        semana_numero: numSemana,
        fecha_inicio: fechaInicio,
        fecha_fin: fechaFin,
        filas: filasValidas,
      }
      await onSubmit(payload)
      onClose()
    } catch (err: any) {
      setErrorGeneral(err.message || 'Error al guardar la semana.')
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Captura Semanal de Raya (Nómina)"
      description="Registra la nómina completa de los trabajadores para una semana de trabajo."
      maxWidth="4xl"
    >
      <div className="space-y-4 text-xs">
        {/* Encabezado de la semana */}
        <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <span className="text-[10px] text-zinc-400 uppercase font-semibold">Periodo de Nómina</span>
            <p className="text-sm font-bold text-zinc-900 font-mono tracking-wide">{etiquetaSemana}</p>
          </div>

          <div className="flex items-center space-x-3">
            <div>
              <label className="block text-[10px] text-zinc-500 font-medium mb-0.5">Desde (Lunes)</label>
              <input
                type="date"
                value={fechaInicio}
                onChange={(e) => setFechaInicio(e.target.value)}
                className="px-2 py-1.5 border border-zinc-200 rounded font-mono bg-white text-xs"
              />
            </div>
            <div>
              <label className="block text-[10px] text-zinc-500 font-medium mb-0.5">Hasta (Domingo)</label>
              <input
                type="date"
                value={fechaFin}
                onChange={(e) => setFechaFin(e.target.value)}
                className="px-2 py-1.5 border border-zinc-200 rounded font-mono bg-white text-xs"
              />
            </div>
          </div>
        </div>

        {dInicio.getDay() !== 1 || dFin.getDay() !== 0 ? (
          <div className="p-2 bg-amber-50 border border-amber-200 rounded text-amber-800 text-[11px] flex items-center gap-1.5">
            <span>ℹ️</span>
            <span>Aviso: El rango seleccionado no es de lunes a domingo (habitual en el despacho). Puedes continuar si se trata de una semana especial.</span>
          </div>
        ) : null}

        {errorGeneral && (
          <div className="p-2.5 bg-red-50 border border-red-200 rounded-md text-red-700 text-xs font-medium">
            {errorGeneral}
          </div>
        )}

        {/* Tabla interactiva de trabajadores de la semana */}
        <div className="border border-zinc-200 rounded-lg overflow-x-auto bg-white shadow-2xs">
          <table className="w-full text-left text-xs min-w-[760px]">
            <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-500 font-semibold uppercase text-[10px]">
              <tr>
                <th className="py-2.5 px-3 min-w-[240px]">Trabajador *</th>
                <th className="py-2.5 px-3 min-w-[130px]">Tipo *</th>
                <th className="py-2.5 px-3 min-w-[120px] text-right">Cantidad</th>
                <th className="py-2.5 px-3 min-w-[120px] text-right">Tarifa ($)</th>
                <th className="py-2.5 px-3 min-w-[130px] text-right">Importe En Vivo</th>
                <th className="py-2.5 px-2 w-10 text-center"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {filas.map((fila) => {
                const cant = parseFloat(fila.cantidad || '0')
                const tar = parseFloat(fila.tarifa || '0')
                const totalFila = isNaN(cant) || isNaN(tar) ? 0 : Math.round(cant * tar * 100) / 100
                const esTrabajadorInvalido = !fila.trabajador_id
                const esCantidadInvalida = isNaN(cant) || cant <= 0
                const esTarifaInvalida = isNaN(tar) || tar <= 0
                const esDuplicado = fila.trabajador_id && trabajadoresContados[Number(fila.trabajador_id)] > 1

                return (
                  <tr key={fila.id} className="hover:bg-zinc-50/50">
                    <td className="py-2.5 px-3 min-w-[240px]">
                      <select
                        value={fila.trabajador_id}
                        onChange={(e) =>
                          handleFilaChange(fila.id, {
                            trabajador_id: e.target.value ? Number(e.target.value) : '',
                          })
                        }
                        className={`w-full px-2 py-1.5 border rounded bg-white text-xs font-medium ${
                          esTrabajadorInvalido ? 'border-red-300 bg-red-50/20' : 'border-zinc-200'
                        }`}
                      >
                        <option value="">-- Seleccionar trabajador --</option>
                        {trabajadores.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.nombre} ({t.oficio || 'Sin oficio'})
                          </option>
                        ))}
                      </select>
                      {esTrabajadorInvalido && (
                        <p className="text-[10px] text-red-600 mt-0.5 font-medium">Trabajador obligatorio</p>
                      )}
                      {esDuplicado && (
                        <p className="text-[10px] text-amber-600 mt-0.5 font-medium">
                          Advertencia: Trabajador repetido en esta semana
                        </p>
                      )}
                    </td>

                    <td className="py-2.5 px-3 min-w-[130px]">
                      <select
                        value={fila.tipo}
                        onChange={(e) => handleFilaChange(fila.id, { tipo: e.target.value as TipoRaya })}
                        className="w-full px-2 py-1.5 border border-zinc-200 rounded bg-white text-xs font-medium"
                      >
                        <option value="dia">Día</option>
                        <option value="destajo">Destajo</option>
                      </select>
                    </td>

                    <td className="py-2.5 px-3 min-w-[120px]">
                      <div className="relative">
                        <input
                          type="number"
                          step="any"
                          value={fila.cantidad}
                          onChange={(e) => handleFilaChange(fila.id, { cantidad: e.target.value })}
                          className={`w-full px-2 py-1.5 border rounded text-right font-mono text-xs ${
                            esCantidadInvalida ? 'border-red-300 bg-red-50/20' : 'border-zinc-200'
                          }`}
                          placeholder="6.0"
                        />
                        <span className="block text-[10px] text-zinc-400 text-right mt-0.5">
                          {fila.tipo === 'destajo' ? 'Metros' : 'Días'}
                        </span>
                      </div>
                      {esCantidadInvalida && (
                        <p className="text-[10px] text-red-600 text-right mt-0.5 font-medium">Mayor a 0</p>
                      )}
                    </td>

                    <td className="py-2.5 px-3 min-w-[120px]">
                      <input
                        type="number"
                        step="0.01"
                        value={fila.tarifa}
                        onChange={(e) => handleFilaChange(fila.id, { tarifa: e.target.value })}
                        className={`w-full px-2 py-1.5 border rounded text-right font-mono text-xs ${
                          esTarifaInvalida ? 'border-red-300 bg-red-50/20' : 'border-zinc-200'
                        }`}
                        placeholder="50.00"
                      />
                      {esTarifaInvalida && (
                        <p className="text-[10px] text-red-600 text-right mt-0.5 font-medium">Mayor a 0</p>
                      )}
                    </td>

                    <td className="py-2.5 px-3 min-w-[130px] text-right font-mono font-bold text-zinc-900 text-sm">
                      {formatMoney(totalFila.toFixed(2))}
                    </td>

                    <td className="py-2.5 px-2 text-center">
                      <button
                        type="button"
                        onClick={() => handleEliminarFila(fila.id)}
                        disabled={filas.length <= 1}
                        className="p-1 text-zinc-400 hover:text-red-600 disabled:opacity-30"
                        title="Eliminar fila"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Barra inferior de adición y totales */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
          <Button type="button" variant="outline" size="sm" onClick={handleAgregarFila}>
            <Plus className="w-3.5 h-3.5 mr-1" />
            Agregar trabajador a la semana
          </Button>

          <div className="flex items-center space-x-4 self-end sm:self-auto">
            <div className="text-right">
              <span className="text-[11px] text-zinc-500 font-medium mr-2">Total de la Semana:</span>
              <span className="text-base font-bold font-mono text-zinc-950">
                {formatMoney(totalSuma.toFixed(2))}
              </span>
            </div>

            <Button size="sm" onClick={handleGuardar} disabled={isLoading || totalSuma <= 0}>
              {isLoading ? 'Guardando nómina...' : 'Guardar Toda la Semana'}
            </Button>
          </div>
        </div>
      </div>
    </Dialog>
  )
}
