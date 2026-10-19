import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Users, Plus, Search, Building2, Wallet, Briefcase, Calendar } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Dialog } from '@/components/ui/Dialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { api } from '@/lib/api'
import { formatMoney, formatDate } from '@/lib/utils'
import type { Trabajador, PagoRaya, TrabajadorPagosOut } from '@/types'

export function TrabajadoresPage() {
  const queryClient = useQueryClient()
  const [busqueda, setBusqueda] = useState('')
  const [modalNuevoOpen, setModalNuevoOpen] = useState(false)
  const [trabajadorSeleccionadoId, setTrabajadorSeleccionadoId] = useState<number | null>(null)

  // Formulario nuevo trabajador
  const [nombre, setNombre] = useState('')
  const [oficio, setOficio] = useState('')

  // Lista de trabajadores
  const { data: trabajadores, isLoading } = useQuery({
    queryKey: ['trabajadores'],
    queryFn: () => api.getTrabajadores(),
  })

  // Detalle e historial de pagos del trabajador seleccionado
  const { data: detallePagos, isLoading: cargandoPagos } = useQuery({
    queryKey: ['trabajador-pagos', trabajadorSeleccionadoId],
    queryFn: () => api.getPagosTrabajador(trabajadorSeleccionadoId!),
    enabled: trabajadorSeleccionadoId !== null,
  })

  // Mutación para crear trabajador
  const crearMutation = useMutation({
    mutationFn: (data: { nombre: string; oficio: string }) => api.createTrabajador(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trabajadores'] })
      setModalNuevoOpen(false)
      setNombre('')
      setOficio('')
    },
  })

  const filtrados = (trabajadores || []).filter((t) => {
    const q = busqueda.toLowerCase().trim()
    return t.nombre.toLowerCase().includes(q) || t.oficio.toLowerCase().includes(q)
  })

  const handleCrear = (e: React.FormEvent) => {
    e.preventDefault()
    if (!nombre.trim()) return
    crearMutation.mutate({ nombre: nombre.trim(), oficio: oficio.trim() })
  }

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-serif text-zinc-900 tracking-tight">
            Catálogo de Empleados y Trabajadores
          </h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            Gestiona los oficiales, albañiles y ayudantes de obra, y consulta el historial acumulado de sus pagos de raya.
          </p>
        </div>

        <Button size="sm" onClick={() => setModalNuevoOpen(true)}>
          <Plus className="w-3.5 h-3.5 mr-1.5" />
          Nuevo Trabajador
        </Button>
      </div>

      {/* Buscador */}
      <div className="relative max-w-sm">
        <Search className="w-4 h-4 absolute left-3 top-2.5 text-zinc-400" />
        <input
          type="text"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar por nombre u oficio..."
          className="w-full text-xs pl-9 pr-4 py-2 border border-zinc-200 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-zinc-900"
        />
      </div>

      {/* Tabla de trabajadores */}
      <div className="bg-white border border-zinc-200 rounded-lg overflow-hidden shadow-2xs">
        {isLoading ? (
          <div className="p-6 space-y-3">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : filtrados.length === 0 ? (
          <EmptyState
            title="No se encontraron trabajadores"
            description="Registra a los colaboradores del equipo de albañilería y obra para asociar sus pagos de nómina."
            actionLabel="Registrar Trabajador"
            onAction={() => setModalNuevoOpen(true)}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-500 font-semibold uppercase text-[10px]">
                <tr>
                  <th className="py-2.5 px-4">Nombre Completo</th>
                  <th className="py-2.5 px-4">Oficio / Especialidad</th>
                  <th className="py-2.5 px-4 text-center">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {filtrados.map((t) => (
                  <tr key={t.id} className="hover:bg-zinc-50/50">
                    <td className="py-3 px-4 font-medium text-zinc-900">{t.nombre}</td>
                    <td className="py-3 px-4 text-zinc-600">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] bg-zinc-100 font-medium text-zinc-800">
                        {t.oficio || 'Sin oficio registrado'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setTrabajadorSeleccionadoId(t.id)}
                        className="text-xs"
                      >
                        Ver Historial de Pagos
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Diálogo para Nuevo Trabajador */}
      <Dialog
        open={modalNuevoOpen}
        onClose={() => setModalNuevoOpen(false)}
        title="Registrar Nuevo Trabajador"
        description="Ingresa el nombre del colaborador y su especialidad u oficio."
        maxWidth="sm"
      >
        <form onSubmit={handleCrear} className="space-y-4 text-xs">
          <div>
            <label className="block font-medium text-zinc-700 mb-1">Nombre completo *</label>
            <input
              type="text"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Ej. José Juan Ibarra"
              required
              className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900"
            />
          </div>

          <div>
            <label className="block font-medium text-zinc-700 mb-1">Oficio o Especialidad *</label>
            <input
              type="text"
              value={oficio}
              onChange={(e) => setOficio(e.target.value)}
              placeholder="Ej. Maestro de Obra, Oficial Albañil, Fierrero, Ayudante"
              required
              className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900"
            />
          </div>

          <div className="flex items-center justify-end space-x-2 pt-4 border-t border-zinc-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setModalNuevoOpen(false)}
              disabled={crearMutation.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" size="sm" disabled={crearMutation.isPending}>
              {crearMutation.isPending ? 'Guardando...' : 'Crear Trabajador'}
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Diálogo con Historial de Pagos del Trabajador */}
      <Dialog
        open={trabajadorSeleccionadoId !== null}
        onClose={() => setTrabajadorSeleccionadoId(null)}
        title={detallePagos ? `Historial: ${detallePagos.trabajador.nombre}` : 'Historial de Pagos'}
        description={`Oficio: ${detallePagos?.trabajador.oficio || '—'} &bull; Pagos de raya recibidos`}
        maxWidth="md"
      >
        <div className="space-y-4 text-xs">
          {cargandoPagos ? (
            <div className="p-4 space-y-2">
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
            </div>
          ) : detallePagos ? (
            <>
              <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-md flex items-center justify-between">
                <span className="text-zinc-600 font-medium">Total Pagado Acumulado:</span>
                <span className="font-mono text-sm font-bold text-zinc-900">
                  {formatMoney(detallePagos.total_acumulado)}
                </span>
              </div>

              {detallePagos.pagos.length === 0 ? (
                <p className="text-zinc-400 text-center py-4 italic">
                  Este trabajador aún no tiene pagos de raya registrados en ninguna obra.
                </p>
              ) : (
                <div className="max-h-80 overflow-y-auto border border-zinc-100 rounded-md">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-zinc-50 text-zinc-500 font-semibold uppercase text-[10px] sticky top-0">
                      <tr>
                        <th className="py-2 px-3">Semana / Fecha</th>
                        <th className="py-2 px-3">Modalidad</th>
                        <th className="py-2 px-3 text-right">Cant. x Tarifa</th>
                        <th className="py-2 px-3 text-right">Importe</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100 font-normal">
                      {detallePagos.pagos.map((p: PagoRaya) => (
                        <tr key={p.id}>
                          <td className="py-2 px-3">
                            <span className="font-mono font-medium block">Sem {p.semana_numero}</span>
                            <span className="text-[10px] text-zinc-400">{formatDate(p.fecha_fin)}</span>
                          </td>
                          <td className="py-2 px-3 uppercase text-[10px] text-zinc-600">{p.tipo}</td>
                          <td className="py-2 px-3 text-right font-mono text-zinc-500">
                            {p.cantidad} @ {formatMoney(p.tarifa)}
                          </td>
                          <td className="py-2 px-3 text-right font-mono font-medium text-zinc-900">
                            {formatMoney(p.importe)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          ) : null}

          <div className="flex justify-end pt-2 border-t border-zinc-100">
            <Button size="sm" onClick={() => setTrabajadorSeleccionadoId(null)}>
              Cerrar
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
