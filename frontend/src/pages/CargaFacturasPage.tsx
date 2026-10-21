import React, { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  UploadCloud,
  FileCheck2,
  Receipt,
  Layers,
  ExternalLink,
  RefreshCw,
  Copy,
  Check,
  FolderOpen,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { api } from '@/lib/api'
import { formatMoney } from '@/lib/utils'
import { sugerirAlias } from '@/lib/proveedorUtils'
import { FacturaDropzone } from '@/components/facturas/FacturaDropzone'
import {
  FacturasTablaRevision,
  type FilaFacturaState,
} from '@/components/facturas/FacturasTablaRevision'
import type { UploadFacturasOut, MetodoPago, FacturaConfirmarItem, Gasto } from '@/types'

export function CargaFacturasPage() {
  const { id } = useParams<{ id: string }>()
  const obraId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [filas, setFilas] = useState<FilaFacturaState[]>([])
  const [erroresGenerales, setErroresGenerales] = useState<string[]>([])
  const [errorDetallesTecnicos, setErrorDetallesTecnicos] = useState<string | null>(null)
  const [copiado, setCopiado] = useState(false)
  const [abriendoLogs, setAbriendoLogs] = useState(false)
  const [exitoResumen, setExitoResumen] = useState<{
    guardadas: number
    totalImporte: string
    gastos: Gasto[]
  } | null>(null)

  // Obtener datos de la obra
  const { data: obra, isLoading: cargandoObra } = useQuery({
    queryKey: ['obra', obraId],
    queryFn: () => api.getObra(obraId),
    enabled: !isNaN(obraId),
  })

  // Mutación para subir lote de archivos al staging
  const subirMutation = useMutation({
    mutationFn: (files: File[]) => api.subirFacturas(obraId, files),
    onSuccess: (data: UploadFacturasOut) => {
      setErroresGenerales([])

      const nuevasFilas: FilaFacturaState[] = []
      const erroresNoDuplicados: string[] = []

      // 1. Convertir items leídos exitosamente en filas
      data.items.forEach((item) => {
        const esNuevo = !item.proveedor.existente_id
        const aliasCalculado =
          item.proveedor.alias ||
          (esNuevo ? sugerirAlias(item.proveedor.razon_social) : item.proveedor.razon_social)

        nuevasFilas.push({
          id: item.staging_id,
          staging_id: item.staging_id,
          archivo_xml: item.archivo_xml,
          archivo_pdf: item.archivo_pdf,
          uuid: item.datos.uuid,
          rfc_emisor: item.proveedor.rfc,
          razon_social: item.proveedor.razon_social,
          proveedor_alias: aliasCalculado,
          es_proveedor_nuevo: esNuevo,
          concepto_resumido: item.sugerido.concepto_resumido,
          comprobante: item.sugerido.comprobante,
          fecha: item.sugerido.fecha,
          importe: item.datos.total,
          metodo_pago: item.sugerido.metodo_pago || '',
          requiere_decision_metodo_pago: item.requiere_decision_metodo_pago,
          es_duplicado: false,
        })
      })

      // 2. Errores por archivo (duplicados de BD o del mismo lote)
      data.errores.forEach((err) => {
        if (err.codigo === 'uuid_duplicado' || err.codigo === 'uuid_duplicado_lote') {
          nuevasFilas.push({
            id: `err-${err.archivo}-${Math.random()}`,
            staging_id: '',
            archivo_xml: err.archivo,
            uuid: err.detalle,
            rfc_emisor: '—',
            razon_social: err.archivo,
            proveedor_alias: '',
            es_proveedor_nuevo: false,
            concepto_resumido: err.detalle,
            comprobante: '—',
            fecha: err.duplicado_de ? err.duplicado_de.fecha : '',
            importe: '0.00',
            metodo_pago: '',
            requiere_decision_metodo_pago: false,
            es_duplicado: true,
            duplicado_info: err.duplicado_de
              ? {
                  obra_nombre: err.duplicado_de.obra_nombre,
                  fecha: err.duplicado_de.fecha,
                }
              : undefined,
            error_detalle: err.detalle,
          })
        } else if (err.codigo === 'pdf_sin_xml') {
          erroresNoDuplicados.push(`PDF sin XML asociado: "${err.archivo}". (Opcional, no impide registrar el lote).`)
        } else {
          erroresNoDuplicados.push(`${err.archivo}: ${err.detalle}`)
        }
      })

      setFilas(nuevasFilas)
      setErroresGenerales(erroresNoDuplicados)
      setErrorDetallesTecnicos(null)
    },
    onError: (err: any) => {
      setErroresGenerales([err.message || 'Error al procesar los archivos en el servidor.'])
      setErrorDetallesTecnicos(err.detallesTecnicos || err.stack || err.message || null)
    },
  })

  // Mutación para confirmar el lote revisado
  const confirmarMutation = useMutation({
    mutationFn: (items: FacturaConfirmarItem[]) => api.confirmarFacturas(obraId, items),
    onSuccess: (gastosCreados) => {
      // Invalida la caché para que el detalle de obra y la lista se actualicen
      queryClient.invalidateQueries({ queryKey: ['gastos', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obra-resumen', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obras-resumen'] })

      // Calcular suma total usando Decimal strings
      let totalSuma = 0
      gastosCreados.forEach((g) => {
        totalSuma += parseFloat(g.importe || '0')
      })

      setExitoResumen({
        guardadas: gastosCreados.length,
        totalImporte: totalSuma.toFixed(2),
        gastos: gastosCreados,
      })
      setFilas([])
      setErroresGenerales([])
      setErrorDetallesTecnicos(null)
    },
    onError: (err: any) => {
      // Si el staging expiró (404)
      if (err.message && err.message.toLowerCase().includes('expiró')) {
        setErroresGenerales([
          'La sesión de carga temporal ha expirado por tiempo de inactividad (TTL). Por favor vuelve a arrastrar los archivos para reiniciar la revisión.',
        ])
        setErrorDetallesTecnicos(null)
      } else {
        let msg = err.message || 'No se pudo guardar la factura. Los detalles técnicos se guardaron en el registro.'
        if (msg.includes('500') || msg.includes('Internal Server Error')) {
          msg = 'No se pudo guardar la factura. Los detalles técnicos se guardaron en el registro.'
        }
        setErroresGenerales([msg])
        setErrorDetallesTecnicos(err.detallesTecnicos || err.stack || err.message || null)
      }
    },
  })

  // Manejo de cambios en las filas
  const handleFilaChange = (idFila: string, campo: Partial<FilaFacturaState>) => {
    setFilas((prev) => prev.map((f) => (f.id === idFila ? { ...f, ...campo } : f)))
  }

  // Quitar fila del lote
  const handleEliminarFila = (idFila: string) => {
    setFilas((prev) => prev.filter((f) => f.id !== idFila))
  }

  // Atajo rápido: aplicar método a todas las filas pendientes
  const handleAplicarMetodoATodasLasVacias = (metodo: MetodoPago) => {
    setFilas((prev) =>
      prev.map((f) => {
        if (!f.es_duplicado && !f.metodo_pago) {
          return { ...f, metodo_pago: metodo }
        }
        return f
      })
    )
  }

  // Subir archivos al dropzone
  const handleFilesSelected = (files: File[]) => {
    subirMutation.mutate(files)
  }

  // Confirmar lote
  const handleConfirmarLote = () => {
    const filasValidas = filas.filter((f) => !f.es_duplicado)
    const itemsPayload: FacturaConfirmarItem[] = filasValidas.map((f) => ({
      staging_id: f.staging_id,
      metodo_pago: f.metodo_pago as MetodoPago,
      fecha: f.fecha,
      concepto_resumido: f.concepto_resumido,
      comprobante: f.comprobante,
      proveedor_alias: f.proveedor_alias,
      proveedor_razon_social: f.razon_social,
    }))

    confirmarMutation.mutate(itemsPayload)
  }

  // Métricas y validación del estado del botón Confirmar
  const filasValidas = filas.filter((f) => !f.es_duplicado)
  const filasConMetodo = filasValidas.filter((f) => Boolean(f.metodo_pago))
  const filasConAliasValido = filasValidas.filter(
    (f) => !f.es_proveedor_nuevo || Boolean(f.proveedor_alias.trim())
  )

  const todoListoParaConfirmar =
    filasValidas.length > 0 &&
    filasConMetodo.length === filasValidas.length &&
    filasConAliasValido.length === filasValidas.length

  if (cargandoObra) {
    return (
      <div className="p-8 text-center text-sm text-zinc-500 font-mono">
        Cargando datos de la obra...
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Barra superior de navegación */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Link
            to={`/obras/${obraId}`}
            className="p-1.5 rounded-md hover:bg-zinc-200 text-zinc-600 transition-colors"
            title="Volver a la obra"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-mono uppercase tracking-wider text-zinc-400">
                Obra #{obraId}
              </span>
              <span className="text-zinc-300">&bull;</span>
              <span className="text-xs font-semibold text-zinc-700">{obra?.nombre}</span>
            </div>
            <h1 className="text-xl font-bold font-serif text-zinc-900 tracking-tight">
              Carga y Revisión de Facturas CFDI
            </h1>
          </div>
        </div>

        {filas.length > 0 && !exitoResumen && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setFilas([])
              setErroresGenerales([])
            }}
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Reiniciar Lote
          </Button>
        )}
      </div>

      {/* Pantalla de éxito tras confirmar */}
      {exitoResumen && (
        <div className="bg-white border border-emerald-200 rounded-xl p-6 shadow-xs space-y-4">
          <div className="flex items-center space-x-3 text-emerald-800">
            <CheckCircle2 className="w-8 h-8 text-emerald-600 shrink-0" />
            <div>
              <h2 className="text-lg font-bold text-emerald-950">
                ¡Lote de facturas guardado exitosamente!
              </h2>
              <p className="text-xs text-emerald-700 mt-0.5">
                Se registraron {exitoResumen.guardadas} facturas y sus gastos asociados en la obra.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-3 border-t border-emerald-100 text-xs">
            <div className="p-3 bg-emerald-50/60 rounded-md">
              <span className="text-[11px] text-emerald-700 font-semibold uppercase">
                Facturas Registradas
              </span>
              <p className="text-base font-bold text-emerald-950 mt-0.5">
                {exitoResumen.guardadas}
              </p>
            </div>
            <div className="p-3 bg-emerald-50/60 rounded-md">
              <span className="text-[11px] text-emerald-700 font-semibold uppercase">
                Importe Total Guardado
              </span>
              <p className="text-base font-bold text-emerald-950 mt-0.5 font-mono">
                {formatMoney(exitoResumen.totalImporte)}
              </p>
            </div>
          </div>

          <div className="pt-2 flex items-center space-x-3">
            <Link to={`/obras/${obraId}`}>
              <Button size="sm">
                <Receipt className="w-4 h-4 mr-1.5" />
                Ver en pestaña Facturas y Gastos
              </Button>
            </Link>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setExitoResumen(null)
                setFilas([])
              }}
            >
              Subir otro lote de facturas
            </Button>
          </div>
        </div>
      )}

      {/* Mensajes de advertencia y errores generales */}
      {erroresGenerales.length > 0 && (
        <div className="bg-red-50/90 border border-red-200 rounded-lg p-4 space-y-3 text-xs text-red-900 shadow-sm">
          <div className="flex items-center space-x-2 font-semibold text-red-900">
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
            <span>Atención:</span>
          </div>
          <ul className="list-disc pl-5 space-y-1 text-red-800">
            {erroresGenerales.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
          {errorDetallesTecnicos && (
            <div className="pt-2 border-t border-red-200/80 flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs bg-white text-zinc-700 hover:bg-zinc-50 border-red-200"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(
                      `${erroresGenerales.join('\n')}\n\nDetalles técnicos:\n${errorDetallesTecnicos}`
                    )
                    setCopiado(true)
                    setTimeout(() => setCopiado(false), 2500)
                  } catch (e) {
                    console.error('Error al copiar:', e)
                  }
                }}
              >
                {copiado ? (
                  <>
                    <Check className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                    <span>¡Detalles copiados!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 mr-1 text-zinc-500" />
                    <span>Copiar detalles</span>
                  </>
                )}
              </Button>

              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs bg-white text-zinc-700 hover:bg-zinc-50 border-red-200"
                disabled={abriendoLogs}
                onClick={async () => {
                  setAbriendoLogs(true)
                  try {
                    await api.abrirCarpetaLogs()
                  } catch (e) {
                    console.error('Error al abrir carpeta de logs:', e)
                  } finally {
                    setAbriendoLogs(false)
                  }
                }}
              >
                <FolderOpen className="w-3.5 h-3.5 mr-1 text-zinc-500" />
                <span>Abrir carpeta de registros</span>
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Paso 1: Dropzone (visible si no hay filas cargadas o para agregar) */}
      {filas.length === 0 && !exitoResumen && (
        <FacturaDropzone
          onFilesSelected={handleFilesSelected}
          isUploading={subirMutation.isPending}
        />
      )}

      {/* Paso 2: Tabla de Revisión en Lote */}
      {filas.length > 0 && !exitoResumen && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-zinc-200">
            <div>
              <h2 className="text-sm font-semibold text-zinc-900">
                Revisión del Lote ({filas.length} {filas.length === 1 ? 'archivo' : 'archivos'})
              </h2>
              <p className="text-xs text-zinc-500">
                Verifica el alias comercial, el concepto y selecciona el método de pago para cada factura.
              </p>
            </div>

            {/* Contador de estado */}
            <div className="flex items-center space-x-3 text-xs">
              <span
                className={`px-2.5 py-1 rounded-full font-medium ${
                  todoListoParaConfirmar
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                    : 'bg-zinc-100 text-zinc-700 border border-zinc-300'
                }`}
              >
                {filasConMetodo.length} de {filasValidas.length} listas
              </span>
            </div>
          </div>

          <FacturasTablaRevision
            filas={filas}
            onFilaChange={handleFilaChange}
            onEliminarFila={handleEliminarFila}
            onAplicarMetodoATodasLasVacias={handleAplicarMetodoATodasLasVacias}
          />

          {/* Barra de acción inferior */}
          <div className="bg-zinc-50 border border-zinc-200 rounded-lg p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="text-xs text-zinc-600">
              {!todoListoParaConfirmar ? (
                <p className="flex items-center text-amber-700 font-medium">
                  <AlertTriangle className="w-4 h-4 mr-1.5 shrink-0" />
                  Para confirmar, debes asignar el método de pago a todas las facturas y verificar los alias comerciales.
                </p>
              ) : (
                <p className="flex items-center text-emerald-700 font-medium">
                  <CheckCircle2 className="w-4 h-4 mr-1.5 shrink-0" />
                  Todas las facturas válidas están completas y listas para guardarse.
                </p>
              )}
            </div>

            <div className="flex items-center space-x-2 self-end sm:self-auto">
              <Link to={`/obras/${obraId}`}>
                <Button variant="ghost" size="sm">
                  Cancelar
                </Button>
              </Link>
              <Button
                size="sm"
                onClick={handleConfirmarLote}
                disabled={!todoListoParaConfirmar || confirmarMutation.isPending}
              >
                {confirmarMutation.isPending
                  ? 'Guardando facturas...'
                  : `Confirmar y Guardar (${filasValidas.length})`}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
