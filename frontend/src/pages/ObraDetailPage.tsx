import React, { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Building2,
  FileText,
  Plus,
  Upload,
  Receipt,
  UserCheck,
  Coins,
  History,
  FileSpreadsheet,
  Download,
  FileDown,
  Trash2,
  Edit2,
  Calendar,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { api } from '@/lib/api'
import { formatMoney, formatDate, formatEstadoObra, formatFolioFactura } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { GastoEditDialog } from '@/components/gastos/GastoEditDialog'
import { GastoManualDialog } from '@/components/gastos/GastoManualDialog'
import { RayaSemanaDialog } from '@/components/rayas/RayaSemanaDialog'
import { AnticipoDialog } from '@/components/anticipos/AnticipoDialog'
import type { Gasto, PagoRaya, Anticipo, MemoriaResumen, GastoManualCreate, PagosSemanaCreate } from '@/types'

export const ObraDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const obraId = Number(id)
  const [activeTab, setActiveTab] = useState<'gastos' | 'rayas' | 'anticipos' | 'memorias'>('gastos')

  // Modales
  const [gastoAEditar, setGastoAEditar] = useState<Gasto | null>(null)
  const [gastoManualModalOpen, setGastoManualModalOpen] = useState(false)
  const [rayaSemanaModalOpen, setRayaSemanaModalOpen] = useState(false)
  const [anticipoModalOpen, setAnticipoModalOpen] = useState(false)
  const [anticipoAEditar, setAnticipoAEditar] = useState<Anticipo | null>(null)

  // Consultas
  const { data: obra, isLoading: loadingObra } = useQuery({
    queryKey: ['obra-resumen', obraId],
    queryFn: () => api.getObraResumen(obraId),
    enabled: !isNaN(obraId),
  })

  const { data: proveedores = [] } = useQuery({
    queryKey: ['proveedores'],
    queryFn: () => api.getProveedores(),
  })

  const { data: trabajadores = [] } = useQuery({
    queryKey: ['trabajadores'],
    queryFn: () => api.getTrabajadores(),
  })

  const { data: gastos, isLoading: loadingGastos } = useQuery({
    queryKey: ['gastos', obraId],
    queryFn: () => api.getGastosDeObra(obraId),
    enabled: !isNaN(obraId) && activeTab === 'gastos',
  })

  const { data: rayas, isLoading: loadingRayas } = useQuery({
    queryKey: ['rayas', obraId],
    queryFn: () => api.getRayasDeObra(obraId),
    enabled: !isNaN(obraId) && activeTab === 'rayas',
  })

  const { data: anticipos, isLoading: loadingAnticipos } = useQuery({
    queryKey: ['anticipos', obraId],
    queryFn: () => api.getAnticiposDeObra(obraId),
    enabled: !isNaN(obraId) && activeTab === 'anticipos',
  })

  const { data: memorias, isLoading: loadingMemorias } = useQuery({
    queryKey: ['memorias', obraId],
    queryFn: () => api.getMemoriasDeObra(obraId),
    enabled: !isNaN(obraId) && activeTab === 'memorias',
  })

  // Paginación de Gastos
  const [paginaGastos, setPaginaGastos] = useState(1)
  const [tamanoPaginaGastos, setTamanoPaginaGastos] = useState(15)

  const totalGastos = gastos?.length || 0
  const totalPaginasGastos = tamanoPaginaGastos === -1 ? 1 : Math.max(1, Math.ceil(totalGastos / tamanoPaginaGastos))
  const gastosPaginados = React.useMemo(() => {
    if (!gastos) return []
    if (tamanoPaginaGastos === -1) return gastos
    const inicio = (paginaGastos - 1) * tamanoPaginaGastos
    return gastos.slice(inicio, inicio + tamanoPaginaGastos)
  }, [gastos, paginaGastos, tamanoPaginaGastos])

  // Mutaciones de Gastos
  const crearGastoManualMutation = useMutation({
    mutationFn: (data: GastoManualCreate) => api.createGastoManual(obraId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gastos', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obra', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obra-resumen', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obras-resumen'] })
    },
  })

  const actualizarGastoMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => api.updateGasto(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gastos', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obra', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obra-resumen', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obras-resumen'] })
    },
  })

  const eliminarGastoMutation = useMutation({
    mutationFn: (gastoId: number) => api.deleteGasto(gastoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gastos', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obra', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obra-resumen', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obras-resumen'] })
    },
  })

  // Mutaciones de Rayas
  const crearRayasSemanaMutation = useMutation({
    mutationFn: (data: PagosSemanaCreate) => api.createRayasSemana(obraId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rayas', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obra', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obra-resumen', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obras-resumen'] })
    },
  })

  const eliminarRayaMutation = useMutation({
    mutationFn: (rayaId: number) => api.deleteRaya(rayaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rayas', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obra', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obra-resumen', obraId] })
      queryClient.invalidateQueries({ queryKey: ['obras-resumen'] })
    },
  })

  // Mutaciones de Anticipos
  const crearAnticipoMutation = useMutation({
    mutationFn: (data: { fecha: string; comprobante: string; importe: string }) =>
      api.createAnticipo(obraId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anticipos', obraId] })
    },
  })

  const actualizarAnticipoMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => api.updateAnticipo(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anticipos', obraId] })
    },
  })

  const eliminarAnticipoMutation = useMutation({
    mutationFn: (anticipoId: number) => api.deleteAnticipo(anticipoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anticipos', obraId] })
    },
  })

  const handleEliminarGasto = (gasto: Gasto) => {
    const confirmMsg =
      gasto.origen === 'xml'
        ? `¿Estás seguro de eliminar el gasto "${gasto.concepto_resumido}"? Esta acción borrará también el archivo XML y PDF asociados del almacenamiento.`
        : `¿Estás seguro de eliminar este gasto manual por ${formatMoney(gasto.importe)}?`
    if (window.confirm(confirmMsg)) {
      eliminarGastoMutation.mutate(gasto.id)
    }
  }

  const handleEliminarRaya = (raya: PagoRaya) => {
    if (window.confirm(`¿Eliminar pago de raya para ${raya.trabajador_nombre} (Semana ${raya.semana_numero})?`)) {
      eliminarRayaMutation.mutate(raya.id)
    }
  }

  const handleEliminarAnticipo = (ant: Anticipo) => {
    if (window.confirm(`¿Eliminar anticipo "${ant.comprobante}" por ${formatMoney(ant.importe)}?`)) {
      eliminarAnticipoMutation.mutate(ant.id)
    }
  }

  if (loadingObra) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (!obra) {
    return (
      <div className="p-8 text-center text-xs text-zinc-500">
        No se encontró la obra solicitada.{' '}
        <Link to="/" className="text-zinc-900 underline font-medium">
          Volver a obras
        </Link>
      </div>
    )
  }

  // Agrupar rayas por semana para la vista agrupada con subtotales
  const rayasPorSemana = (rayas || []).reduce<Record<number, PagoRaya[]>>((acc, r) => {
    if (!acc[r.semana_numero]) acc[r.semana_numero] = []
    acc[r.semana_numero].push(r)
    return acc
  }, {})

  const semanasOrdenadas = Object.keys(rayasPorSemana)
    .map(Number)
    .sort((a, b) => b - a)

  return (
    <div className="space-y-6">
      {/* Cabecera y Resumen de la Obra */}
      <div className="bg-white border border-zinc-200/80 rounded-lg p-5 shadow-2xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            {/* Breadcrumb con nombre legible */}
            <div className="flex items-center space-x-2 text-xs text-zinc-500 mb-1">
              <Link to="/" className="hover:text-zinc-900 flex items-center">
                <ArrowLeft className="w-3 h-3 mr-1" />
                Obras
              </Link>
              <span>/</span>
              <span className="font-medium text-zinc-800">{obra.nombre}</span>
            </div>

            <div className="flex items-center space-x-3">
              <h1 className="text-xl font-bold font-serif text-zinc-900 tracking-tight">{obra.nombre}</h1>
              <Badge variant={obra.estado === 'en_curso' ? 'success' : 'muted'}>
                {formatEstadoObra(obra.estado)}
              </Badge>
            </div>
            <p className="text-xs text-zinc-500">
              Propietario: <span className="text-zinc-800 font-medium">{obra.propietario || '—'}</span> &nbsp;|&nbsp;
              Ubicación: <span className="text-zinc-800 font-medium">{obra.ubicacion || '—'}</span>
            </p>
          </div>

          <div className="flex items-center space-x-2 shrink-0">
            <Link to={`/obras/${obra.id}/facturas/nueva`}>
              <Button variant="outline" size="sm">
                <Upload className="w-3.5 h-3.5 mr-1.5" />
                Subir Facturas
              </Button>
            </Link>
            <Link to={`/obras/${obra.id}/memorias/asistente`}>
              <Button size="sm">
                <Plus className="w-3.5 h-3.5 mr-1.5" />
                Nueva Memoria
              </Button>
            </Link>
          </div>
        </div>

        {/* Tarjetas métricas de la obra (Requisito 1 de Ajustes) */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-zinc-100 text-xs">
          <div className="p-3 bg-zinc-50/70 rounded-md border border-zinc-100">
            <p className="text-[11px] text-zinc-500 font-semibold uppercase">Gastos registrados</p>
            <p className="text-sm font-bold text-zinc-900 mt-0.5">{formatMoney(obra.total_gastado_registrado)}</p>
            <span className="text-[10px] text-zinc-500 block truncate" title={`Gastos ${formatMoney(obra.total_gastos_puros || '0.00')} · Rayas ${formatMoney(obra.total_rayas || '0.00')}`}>
              Gastos {formatMoney(obra.total_gastos_puros || '0.00')} · Rayas {formatMoney(obra.total_rayas || '0.00')}
            </span>
          </div>

          <div className="p-3 bg-zinc-50/70 rounded-md border border-zinc-100">
            <p className="text-[11px] text-zinc-500 font-semibold uppercase">Gastado en memorias cerradas</p>
            <p className="text-sm font-bold text-zinc-800 mt-0.5">{formatMoney(obra.gastado_a_la_fecha)}</p>
            <span className="text-[10px] text-zinc-400">Memorias liquidadas</span>
          </div>

          <div className="p-3 bg-zinc-50/70 rounded-md border border-zinc-100">
            <p className="text-[11px] text-zinc-500 font-semibold uppercase">Honorarios</p>
            <p className="text-sm font-bold text-zinc-800 mt-0.5">{obra.porcentaje_honorarios}%</p>
            <span className="text-[10px] text-zinc-400">Porcentaje pactado</span>
          </div>

          <div className="p-3 bg-zinc-50/70 rounded-md border border-zinc-100">
            <p className="text-[11px] text-zinc-500 font-semibold uppercase">Última Memoria</p>
            <p className="text-sm font-bold text-zinc-800 mt-0.5">
              {obra.numero_ultima_memoria
                ? `Memoria #${obra.numero_ultima_memoria}`
                : obra.numero_ultima_memoria_previa > 0
                ? `Previa #${obra.numero_ultima_memoria_previa}`
                : 'Ninguna'}
            </p>
            <span className="text-[10px] text-zinc-400">
              Siguiente sugerida: #{Math.max(obra.numero_ultima_memoria || 0, obra.numero_ultima_memoria_previa || 0) + 1}
            </span>
          </div>
        </div>
      </div>

      {/* Selector de Pestañas */}
      <div className="border-b border-zinc-200">
        <nav className="flex space-x-6 text-xs font-medium">
          <button
            onClick={() => setActiveTab('gastos')}
            className={`pb-3 border-b-2 flex items-center space-x-2 transition-colors ${
              activeTab === 'gastos'
                ? 'border-zinc-900 text-zinc-950 font-semibold'
                : 'border-transparent text-zinc-500 hover:text-zinc-800'
            }`}
          >
            <Receipt className="w-4 h-4" />
            <span>Facturas y Gastos ({obra.total_gastos})</span>
          </button>

          <button
            onClick={() => setActiveTab('rayas')}
            className={`pb-3 border-b-2 flex items-center space-x-2 transition-colors ${
              activeTab === 'rayas'
                ? 'border-zinc-900 text-zinc-950 font-semibold'
                : 'border-transparent text-zinc-500 hover:text-zinc-800'
            }`}
          >
            <UserCheck className="w-4 h-4" />
            <span>Rayas (Nóminas)</span>
          </button>

          <button
            onClick={() => setActiveTab('anticipos')}
            className={`pb-3 border-b-2 flex items-center space-x-2 transition-colors ${
              activeTab === 'anticipos'
                ? 'border-zinc-900 text-zinc-950 font-semibold'
                : 'border-transparent text-zinc-500 hover:text-zinc-800'
            }`}
          >
            <Coins className="w-4 h-4" />
            <span>Anticipos</span>
          </button>

          <button
            onClick={() => setActiveTab('memorias')}
            className={`pb-3 border-b-2 flex items-center space-x-2 transition-colors ${
              activeTab === 'memorias'
                ? 'border-zinc-900 text-zinc-950 font-semibold'
                : 'border-transparent text-zinc-500 hover:text-zinc-800'
            }`}
          >
            <History className="w-4 h-4" />
            <span>Memorias ({obra.total_memorias})</span>
          </button>
        </nav>
      </div>

      {/* PESTAÑA 1: GASTOS Y FACTURAS */}
      {activeTab === 'gastos' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs text-zinc-500">
              Gastos de la obra registrados por CFDI (XML/PDF) o notas manuales.
            </p>
            <div className="flex items-center space-x-2">
              <Button size="sm" variant="outline" onClick={() => setGastoManualModalOpen(true)}>
                <Plus className="w-3.5 h-3.5 mr-1" />
                Registrar Gasto Manual / Nota
              </Button>
            </div>
          </div>

          <div className="bg-white border border-zinc-200/80 rounded-lg overflow-hidden shadow-2xs">
            {loadingGastos ? (
              <div className="p-6 space-y-3">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : !gastos || gastos.length === 0 ? (
              <EmptyState
                title="No hay gastos ni facturas en esta obra"
                description="Sube archivos XML/PDF de CFDI o agrega pagos manuales para comenzar."
                actionLabel="Subir Facturas CFDI"
                onAction={() => navigate(`/obras/${obra.id}/facturas/nueva`)}
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-500 font-semibold uppercase text-[10px]">
                    <tr>
                      <th className="py-2.5 px-4">Fecha</th>
                      <th className="py-2.5 px-4">Proveedor</th>
                      <th className="py-2.5 px-4">Concepto</th>
                      <th className="py-2.5 px-4">Comprobante</th>
                      <th className="py-2.5 px-4">Método</th>
                      <th className="py-2.5 px-4">Origen</th>
                      <th className="py-2.5 px-4 text-right">Importe</th>
                      <th className="py-2.5 px-4 text-center">Archivos</th>
                      <th className="py-2.5 px-4 text-center">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 font-normal text-zinc-800">
                    {gastosPaginados.map((gasto) => (
                      <tr key={gasto.id} className="hover:bg-zinc-50/50 transition-colors">
                        <td className="py-2.5 px-4 whitespace-nowrap font-mono">{formatDate(gasto.fecha)}</td>
                        <td
                          className="py-2.5 px-4 font-medium truncate max-w-[180px] cursor-help"
                          title={gasto.proveedor_nombre || 'Sin proveedor asignado'}
                        >
                          {gasto.proveedor_nombre || '—'}
                        </td>
                        <td className="py-2.5 px-4 truncate max-w-[260px] text-zinc-600">{gasto.concepto_resumido}</td>
                        <td className="py-2.5 px-4 whitespace-nowrap font-mono text-zinc-500">
                          {gasto.comprobante || '—'}
                        </td>
                        <td className="py-2.5 px-4 whitespace-nowrap">
                          <span
                            className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium uppercase ${
                              gasto.metodo_pago === 'transferencia'
                                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            }`}
                          >
                            {gasto.metodo_pago}
                          </span>
                        </td>
                        <td className="py-2.5 px-4 whitespace-nowrap text-zinc-500 uppercase text-[10px]">
                          {gasto.origen}
                        </td>
                        <td className="py-2.5 px-4 whitespace-nowrap text-right font-medium text-zinc-900 font-mono">
                          {formatMoney(gasto.importe)}
                        </td>
                        <td className="py-2.5 px-4 whitespace-nowrap text-center space-x-1">
                          {gasto.factura ? (
                            <>
                              <a
                                href={`/api/facturas/${gasto.id}/archivo/xml`}
                                target="_blank"
                                rel="noreferrer"
                                className="px-1.5 py-0.5 rounded border border-zinc-200 hover:bg-zinc-100 text-[10px] font-mono"
                                title="Descargar XML"
                              >
                                XML
                              </a>
                              {gasto.factura.ruta_pdf && (
                                <a
                                  href={`/api/facturas/${gasto.id}/archivo/pdf`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="px-1.5 py-0.5 rounded border border-red-200 text-red-700 hover:bg-red-50 text-[10px] font-mono"
                                  title="Descargar PDF"
                                >
                                  PDF
                                </a>
                              )}
                            </>
                          ) : (
                            <span className="text-zinc-300">—</span>
                          )}
                        </td>
                        <td className="py-2.5 px-4 whitespace-nowrap text-center space-x-1">
                          <button
                            type="button"
                            onClick={() => setGastoAEditar(gasto)}
                            className="p-1 text-zinc-400 hover:text-zinc-800 rounded transition-colors"
                            title="Editar gasto"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleEliminarGasto(gasto)}
                            className="p-1 text-zinc-400 hover:text-red-600 rounded transition-colors"
                            title="Eliminar gasto"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Barra de paginación */}
                {totalGastos > 0 && (
                  <div className="bg-zinc-50/80 border-t border-zinc-200 px-4 py-3 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-zinc-600">
                    <div className="flex items-center gap-3">
                      <span>
                        Mostrando{' '}
                        <strong className="font-mono text-zinc-800">
                          {tamanoPaginaGastos === -1 ? 1 : (paginaGastos - 1) * tamanoPaginaGastos + 1}
                        </strong>{' '}
                        -{' '}
                        <strong className="font-mono text-zinc-800">
                          {tamanoPaginaGastos === -1
                            ? totalGastos
                            : Math.min(paginaGastos * tamanoPaginaGastos, totalGastos)}
                        </strong>{' '}
                        de <strong className="font-mono text-zinc-800">{totalGastos}</strong> gastos
                      </span>

                      <div className="flex items-center gap-1.5 ml-2">
                        <span className="text-zinc-500 text-[11px]">Por página:</span>
                        <select
                          value={tamanoPaginaGastos}
                          onChange={(e) => {
                            setTamanoPaginaGastos(Number(e.target.value))
                            setPaginaGastos(1)
                          }}
                          className="bg-white border border-zinc-200 rounded px-2 py-1 text-xs font-medium text-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-900"
                        >
                          <option value={15}>15</option>
                          <option value={25}>25</option>
                          <option value={50}>50</option>
                          <option value={-1}>Todos ({totalGastos})</option>
                        </select>
                      </div>
                    </div>

                    {tamanoPaginaGastos !== -1 && totalPaginasGastos > 1 && (
                      <div className="flex items-center gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={paginaGastos <= 1}
                          onClick={() => setPaginaGastos((p) => Math.max(1, p - 1))}
                          className="h-8 px-2 text-xs"
                        >
                          <ChevronLeft className="w-3.5 h-3.5 mr-0.5" />
                          <span>Anterior</span>
                        </Button>

                        <div className="px-2 font-mono text-xs font-semibold text-zinc-700">
                          {paginaGastos} / {totalPaginasGastos}
                        </div>

                        <Button
                          variant="outline"
                          size="sm"
                          disabled={paginaGastos >= totalPaginasGastos}
                          onClick={() => setPaginaGastos((p) => Math.min(totalPaginasGastos, p + 1))}
                          className="h-8 px-2 text-xs"
                        >
                          <span>Siguiente</span>
                          <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* PESTAÑA 2: RAYAS (AGRUPADA POR SEMANA CON SUBTOTALES) */}
      {activeTab === 'rayas' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-zinc-500">
              Nóminas y rayas semanales del personal de obra por destajo o por día.
            </p>
            <Button size="sm" onClick={() => setRayaSemanaModalOpen(true)}>
              <Plus className="w-3.5 h-3.5 mr-1" />
              Captura Semanal de Raya
            </Button>
          </div>

          {loadingRayas ? (
            <div className="p-6 space-y-3 bg-white border border-zinc-200 rounded-lg">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : !rayas || rayas.length === 0 ? (
            <EmptyState
              title="No hay pagos de raya registrados"
              description="Realiza la captura semanal de raya para los albañiles y ayudantes de la obra."
              actionLabel="Capturar Raya de la Semana"
              onAction={() => setRayaSemanaModalOpen(true)}
            />
          ) : (
            <div className="space-y-4">
              {semanasOrdenadas.map((numSemana) => {
                const pagosSemana = rayasPorSemana[numSemana]
                const subtotalSemana = pagosSemana.reduce((sum, r) => sum + parseFloat(r.importe), 0)
                const rangoFechas = pagosSemana[0]
                  ? `${formatDate(pagosSemana[0].fecha_inicio)} al ${formatDate(pagosSemana[0].fecha_fin)}`
                  : ''

                return (
                  <div
                    key={numSemana}
                    className="bg-white border border-zinc-200/90 rounded-lg overflow-hidden shadow-2xs"
                  >
                    {/* Encabezado de la semana */}
                    <div className="bg-zinc-50 px-4 py-2.5 border-b border-zinc-200 flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Calendar className="w-4 h-4 text-zinc-500" />
                        <span className="font-semibold text-zinc-900 text-xs font-mono">
                          Semana #{numSemana}
                        </span>
                        <span className="text-zinc-400 text-xs">&bull;</span>
                        <span className="text-zinc-500 text-xs">{rangoFechas}</span>
                      </div>
                      <div className="flex items-center space-x-2 text-xs">
                        <span className="text-zinc-500">Subtotal semana:</span>
                        <span className="font-bold font-mono text-zinc-900">
                          {formatMoney(subtotalSemana.toFixed(2))}
                        </span>
                      </div>
                    </div>

                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-zinc-100 text-zinc-400 font-semibold uppercase text-[10px]">
                        <tr>
                          <th className="py-2 px-4">Trabajador</th>
                          <th className="py-2 px-4">Oficio</th>
                          <th className="py-2 px-4">Modalidad</th>
                          <th className="py-2 px-4 text-right">Cantidad</th>
                          <th className="py-2 px-4 text-right">Tarifa</th>
                          <th className="py-2 px-4 text-right">Importe</th>
                          <th className="py-2 px-3 text-center w-10"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-100 font-normal text-zinc-800">
                        {pagosSemana.map((raya) => (
                          <tr key={raya.id} className="hover:bg-zinc-50/50">
                            <td className="py-2.5 px-4 font-medium">{raya.trabajador_nombre}</td>
                            <td className="py-2.5 px-4 text-zinc-500">{raya.oficio || '—'}</td>
                            <td className="py-2.5 px-4 uppercase text-[10px] text-zinc-600">{raya.tipo}</td>
                            <td className="py-2.5 px-4 text-right font-mono">{raya.cantidad}</td>
                            <td className="py-2.5 px-4 text-right font-mono">{formatMoney(raya.tarifa)}</td>
                            <td className="py-2.5 px-4 text-right font-bold text-zinc-900 font-mono">
                              {formatMoney(raya.importe)}
                            </td>
                            <td className="py-2.5 px-3 text-center">
                              <button
                                type="button"
                                onClick={() => handleEliminarRaya(raya)}
                                className="p-1 text-zinc-400 hover:text-red-600 rounded"
                                title="Eliminar pago"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* PESTAÑA 3: ANTICIPOS */}
      {activeTab === 'anticipos' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-zinc-500">
              Anticipos y transferencias entregadas por el cliente a cuenta de obra.
            </p>
            <Button
              size="sm"
              onClick={() => {
                setAnticipoAEditar(null)
                setAnticipoModalOpen(true)
              }}
            >
              <Plus className="w-3.5 h-3.5 mr-1" />
              Registrar Anticipo
            </Button>
          </div>

          <div className="bg-white border border-zinc-200/80 rounded-lg overflow-hidden shadow-2xs">
            {loadingAnticipos ? (
              <div className="p-6 space-y-3">
                <Skeleton className="h-8 w-full" />
              </div>
            ) : !anticipos || anticipos.length === 0 ? (
              <EmptyState
                title="No hay anticipos registrados"
                description="Registra anticipos entregados por el cliente para descontarlos en la memoria."
                actionLabel="Registrar Anticipo"
                onAction={() => {
                  setAnticipoAEditar(null)
                  setAnticipoModalOpen(true)
                }}
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-500 font-semibold uppercase text-[10px]">
                    <tr>
                      <th className="py-2.5 px-4">Fecha</th>
                      <th className="py-2.5 px-4">Comprobante / Referencia</th>
                      <th className="py-2.5 px-4 text-right">Importe</th>
                      <th className="py-2.5 px-4 text-center w-24">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 font-normal text-zinc-800">
                    {anticipos.map((ant) => (
                      <tr key={ant.id} className="hover:bg-zinc-50/50">
                        <td className="py-2.5 px-4 font-mono">{formatDate(ant.fecha)}</td>
                        <td className="py-2.5 px-4 font-medium">{ant.comprobante || '—'}</td>
                        <td className="py-2.5 px-4 text-right font-mono font-bold text-zinc-900">
                          {formatMoney(ant.importe)}
                        </td>
                        <td className="py-2.5 px-4 text-center space-x-1">
                          <button
                            type="button"
                            onClick={() => {
                              setAnticipoAEditar(ant)
                              setAnticipoModalOpen(true)
                            }}
                            className="p-1 text-zinc-400 hover:text-zinc-800 rounded"
                            title="Editar anticipo"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleEliminarAnticipo(ant)}
                            className="p-1 text-zinc-400 hover:text-red-600 rounded"
                            title="Eliminar anticipo"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* PESTAÑA 4: MEMORIAS */}
      {activeTab === 'memorias' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-zinc-500">
              Historial de memorias de gastos generadas para el cliente.
            </p>
            <Link to={`/obras/${obra.id}/memorias/asistente`}>
              <Button size="sm">
                <Plus className="w-3.5 h-3.5 mr-1" />
                Nueva Memoria
              </Button>
            </Link>
          </div>

          <div className="bg-white border border-zinc-200/80 rounded-lg overflow-hidden shadow-2xs">
            {loadingMemorias ? (
              <div className="p-6 space-y-3">
                <Skeleton className="h-8 w-full" />
              </div>
            ) : !memorias || memorias.length === 0 ? (
              <EmptyState
                title="No hay memorias generadas"
                description="Crea la primera memoria de gastos seleccionando un rango de fechas y los pagos a incluir."
                actionLabel="Crear Primera Memoria"
                onAction={() => navigate(`/obras/${obra.id}/memorias/asistente`)}
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-500 font-semibold uppercase text-[10px]">
                    <tr>
                      <th className="py-2.5 px-4">Memoria #</th>
                      <th className="py-2.5 px-4">Periodo de Gastos</th>
                      <th className="py-2.5 px-4">Folio Factura Arq.</th>
                      <th className="py-2.5 px-4">Estado</th>
                      <th className="py-2.5 px-4 text-right">Total Liquidación</th>
                      <th className="py-2.5 px-4 text-center">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 font-normal text-zinc-800">
                    {memorias.map((mem) => (
                      <tr key={mem.id} className="hover:bg-zinc-50/50">
                        <td className="py-2.5 px-4 font-mono font-bold text-zinc-900">
                          Memoria #{mem.numero}
                        </td>
                        <td className="py-2.5 px-4 text-zinc-600">
                          {formatDate(mem.fecha_inicio)} al {formatDate(mem.fecha_fin)}
                        </td>
                        <td className="py-2.5 px-4 font-mono text-zinc-500">
                          {mem.folio_factura_arquitecto ? formatFolioFactura(mem.folio_factura_arquitecto) : '—'}
                        </td>
                        <td className="py-2.5 px-4">
                          <Badge variant={mem.estado === 'cerrada' ? 'success' : 'warning'}>
                            {mem.estado === 'cerrada' ? 'Cerrada' : 'Borrador'}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-4 text-right font-mono font-bold text-zinc-900">
                          {formatMoney(mem.total_memoria)}
                        </td>
                        <td className="py-2.5 px-4 text-right space-x-1.5 whitespace-nowrap">
                          {mem.estado === 'borrador' && (
                            <Link to={`/obras/${obra.id}/memorias/asistente?borrador_id=${mem.id}`}>
                              <Button size="sm" className="text-xs bg-stone-900 text-white">
                                Continuar Borrador
                              </Button>
                            </Link>
                          )}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => api.descargarPdf(mem.id)}
                            className="text-xs inline-flex items-center gap-1 border-zinc-200"
                            title="Descargar PDF"
                          >
                            <FileDown className="w-3.5 h-3.5 text-red-600" />
                            <span>PDF</span>
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => api.descargarExcel(mem.id)}
                            className="text-xs inline-flex items-center gap-1 border-zinc-200"
                            title="Descargar Excel"
                          >
                            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
                            <span>Excel</span>
                          </Button>
                          <Link to={`/memorias/${mem.id}/imprimir`} target="_blank">
                            <Button variant="outline" size="sm" className="text-xs">
                              Imprimir
                            </Button>
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modales de la Etapa C */}
      <GastoEditDialog
        open={gastoAEditar !== null}
        onClose={() => setGastoAEditar(null)}
        gasto={gastoAEditar}
        proveedores={proveedores}
        onSave={async (gastoId, data) => {
          await actualizarGastoMutation.mutateAsync({ id: gastoId, data })
        }}
        isLoading={actualizarGastoMutation.isPending}
      />

      <GastoManualDialog
        open={gastoManualModalOpen}
        onClose={() => setGastoManualModalOpen(false)}
        proveedores={proveedores}
        onSubmit={async (data) => {
          await crearGastoManualMutation.mutateAsync(data)
        }}
        isLoading={crearGastoManualMutation.isPending}
      />

      <RayaSemanaDialog
        open={rayaSemanaModalOpen}
        onClose={() => setRayaSemanaModalOpen(false)}
        trabajadores={trabajadores}
        onSubmit={async (data) => {
          await crearRayasSemanaMutation.mutateAsync(data)
        }}
        isLoading={crearRayasSemanaMutation.isPending}
      />

      <AnticipoDialog
        open={anticipoModalOpen}
        onClose={() => {
          setAnticipoModalOpen(false)
          setAnticipoAEditar(null)
        }}
        anticipoToEdit={anticipoAEditar}
        onSubmit={async (data) => {
          if (anticipoAEditar) {
            await actualizarAnticipoMutation.mutateAsync({ id: anticipoAEditar.id, data })
          } else {
            await crearAnticipoMutation.mutateAsync(data)
          }
        }}
        isLoading={crearAnticipoMutation.isPending || actualizarAnticipoMutation.isPending}
      />
    </div>
  )
}
