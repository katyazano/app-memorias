import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Building2, Plus, Search, Edit2, Check, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { api } from '@/lib/api'
import type { Proveedor } from '@/types'

export function ProveedoresPage() {
  const queryClient = useQueryClient()
  const [busqueda, setBusqueda] = useState('')
  const [filtroTipo, setFiltroTipo] = useState<'todos' | 'con_factura' | 'sin_factura'>('todos')
  const [modalNuevoOpen, setModalNuevoOpen] = useState(false)

  // Estado para conversión de sin_factura a con_factura
  const [proveedorAConvertir, setProveedorAConvertir] = useState<Proveedor | null>(null)
  const [rfcConversion, setRfcConversion] = useState('')
  const [errorConversion, setErrorConversion] = useState('')

  // Estado para edición en línea del alias
  const [editandoId, setEditandoId] = useState<number | null>(null)
  const [aliasEditando, setAliasEditando] = useState('')

  // Formulario nuevo proveedor
  const [tipoNuevo, setTipoNuevo] = useState<'con_factura' | 'sin_factura'>('con_factura')
  const [rfc, setRfc] = useState('')
  const [razonSocial, setRazonSocial] = useState('')
  const [alias, setAlias] = useState('')
  const [errorNuevo, setErrorNuevo] = useState('')

  // Consulta de proveedores con debounce/búsqueda
  const { data: proveedores, isLoading } = useQuery({
    queryKey: ['proveedores', busqueda],
    queryFn: () => api.getProveedores(busqueda),
  })

  // Mutación para crear proveedor
  const crearMutation = useMutation({
    mutationFn: (data: Partial<Proveedor> & { razon_social: string }) =>
      api.createProveedor(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proveedores'] })
      setModalNuevoOpen(false)
      setTipoNuevo('con_factura')
      setRfc('')
      setRazonSocial('')
      setAlias('')
      setErrorNuevo('')
    },
    onError: (err: any) => {
      setErrorNuevo(err.message || 'Error al registrar proveedor')
    },
  })

  // Mutación para actualizar alias o convertir proveedor
  const actualizarMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Proveedor> }) =>
      api.updateProveedor(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proveedores'] })
      setEditandoId(null)
      setAliasEditando('')
      setProveedorAConvertir(null)
      setRfcConversion('')
      setErrorConversion('')
    },
    onError: (err: any) => {
      setErrorConversion(err.message || 'Error al actualizar proveedor')
    },
  })

  const handleIniciarEdicion = (p: Proveedor) => {
    setEditandoId(p.id)
    setAliasEditando(p.alias || '')
  }

  const handleGuardarEdicion = (id: number) => {
    actualizarMutation.mutate({ id, data: { alias: aliasEditando.trim() } })
  }

  const handleCancelarEdicion = () => {
    setEditandoId(null)
    setAliasEditando('')
  }

  const handleCrear = (e: React.FormEvent) => {
    e.preventDefault()
    setErrorNuevo('')
    if (!razonSocial.trim()) return
    if (tipoNuevo === 'con_factura' && !rfc.trim()) {
      setErrorNuevo('El RFC es obligatorio para proveedores con factura.')
      return
    }

    crearMutation.mutate({
      tipo: tipoNuevo,
      rfc: tipoNuevo === 'con_factura' ? rfc.trim().toUpperCase() : undefined,
      razon_social: razonSocial.trim(),
      alias: alias.trim() || undefined,
    })
  }

  const handleConvertir = (e: React.FormEvent) => {
    e.preventDefault()
    if (!proveedorAConvertir || !rfcConversion.trim()) return
    setErrorConversion('')
    actualizarMutation.mutate({
      id: proveedorAConvertir.id,
      data: {
        tipo: 'con_factura',
        rfc: rfcConversion.trim().toUpperCase(),
      },
    })
  }

  const proveedoresFiltrados = (proveedores || []).filter((p) => {
    if (filtroTipo === 'con_factura') return p.tipo === 'con_factura'
    if (filtroTipo === 'sin_factura') return p.tipo === 'sin_factura'
    return true
  })

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-serif text-zinc-900 tracking-tight">
            Catálogo de Proveedores y Alias Comerciales
          </h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            Configura los alias comerciales memorables y gestiona proveedores con y sin factura para memorias de obra.
          </p>
        </div>

        <Button size="sm" onClick={() => setModalNuevoOpen(true)}>
          <Plus className="w-3.5 h-3.5 mr-1.5" />
          Nuevo Proveedor
        </Button>
      </div>

      {/* Buscador y Filtro por Tipo */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="relative max-w-sm w-full">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-zinc-400" />
          <input
            type="text"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar por RFC, razón social o alias..."
            className="w-full text-xs pl-9 pr-4 py-2 border border-zinc-200 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-zinc-900"
          />
        </div>

        {/* Pestañas de filtro por tipo */}
        <div className="flex items-center space-x-1 bg-zinc-100 p-1 rounded-lg text-xs font-medium self-start sm:self-auto">
          <button
            type="button"
            onClick={() => setFiltroTipo('todos')}
            className={`px-3 py-1 rounded-md transition-colors ${
              filtroTipo === 'todos' ? 'bg-white shadow-2xs text-zinc-900 font-semibold' : 'text-zinc-600 hover:text-zinc-900'
            }`}
          >
            Todos ({proveedores?.length || 0})
          </button>
          <button
            type="button"
            onClick={() => setFiltroTipo('con_factura')}
            className={`px-3 py-1 rounded-md transition-colors ${
              filtroTipo === 'con_factura' ? 'bg-white shadow-2xs text-zinc-900 font-semibold' : 'text-zinc-600 hover:text-zinc-900'
            }`}
          >
            Con factura ({proveedores?.filter((p) => p.tipo === 'con_factura').length || 0})
          </button>
          <button
            type="button"
            onClick={() => setFiltroTipo('sin_factura')}
            className={`px-3 py-1 rounded-md transition-colors ${
              filtroTipo === 'sin_factura' ? 'bg-white shadow-2xs text-zinc-900 font-semibold' : 'text-zinc-600 hover:text-zinc-900'
            }`}
          >
            Sin factura ({proveedores?.filter((p) => p.tipo === 'sin_factura').length || 0})
          </button>
        </div>
      </div>

      {/* Tabla de Proveedores */}
      <div className="bg-white border border-zinc-200 rounded-lg overflow-hidden shadow-2xs">
        {isLoading ? (
          <div className="p-6 space-y-3">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : proveedoresFiltrados.length === 0 ? (
          <EmptyState
            title="No se encontraron proveedores"
            description="Los proveedores se van registrando automáticamente al cargar facturas CFDI o puedes agregarlos manualmente aquí."
            actionLabel="Registrar Proveedor"
            onAction={() => setModalNuevoOpen(true)}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-500 font-semibold uppercase text-[10px]">
                <tr>
                  <th className="py-2.5 px-4 w-28">Tipo</th>
                  <th className="py-2.5 px-4 w-36">RFC</th>
                  <th className="py-2.5 px-4">Razón Social Fiscal / Nombre</th>
                  <th className="py-2.5 px-4 w-72">Alias Comercial (Aparece en memoria)</th>
                  <th className="py-2.5 px-4 w-36 text-center">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {proveedoresFiltrados.map((p) => {
                  const estaEditando = editandoId === p.id

                  return (
                    <tr key={p.id} className="hover:bg-zinc-50/50 transition-colors">
                      <td className="py-3 px-4">
                        {p.tipo === 'con_factura' ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200/50">
                            Con factura
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-zinc-100 text-zinc-700 border border-zinc-200">
                            Sin factura
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-mono font-semibold text-zinc-800">
                        {p.rfc || <span className="text-zinc-400 font-normal italic">Sin RFC</span>}
                      </td>
                      <td className="py-3 px-4 text-zinc-700">{p.razon_social}</td>
                      <td className="py-3 px-4">
                        {estaEditando ? (
                          <div className="flex items-center space-x-1.5">
                            <input
                              type="text"
                              value={aliasEditando}
                              onChange={(e) => setAliasEditando(e.target.value)}
                              placeholder="Alias comercial..."
                              autoFocus
                              className="w-full px-2 py-1 text-xs border border-zinc-300 rounded font-medium focus:ring-1 focus:ring-zinc-900 bg-white"
                            />
                            <button
                              type="button"
                              onClick={() => handleGuardarEdicion(p.id)}
                              className="p-1 text-emerald-600 hover:bg-emerald-50 rounded"
                              title="Guardar alias"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                            <button
                              type="button"
                              onClick={handleCancelarEdicion}
                              className="p-1 text-zinc-400 hover:bg-zinc-100 rounded"
                              title="Cancelar"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center justify-between group">
                            <span className="font-medium text-zinc-900">
                              {p.alias || <span className="text-zinc-400 italic">Sin alias (se usa razón social)</span>}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleIniciarEdicion(p)}
                              className="opacity-0 group-hover:opacity-100 p-1 text-zinc-400 hover:text-zinc-800 rounded transition-opacity"
                              title="Editar alias en línea"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <div className="flex items-center justify-center space-x-2">
                          {!estaEditando && (
                            <Button variant="ghost" size="sm" onClick={() => handleIniciarEdicion(p)}>
                              Editar
                            </Button>
                          )}
                          {p.tipo === 'sin_factura' && (
                            <button
                              type="button"
                              onClick={() => {
                                setProveedorAConvertir(p)
                                setRfcConversion('')
                                setErrorConversion('')
                              }}
                              className="text-[11px] text-blue-600 hover:text-blue-800 font-medium underline"
                            >
                              Agregar RFC
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Diálogo para Nuevo Proveedor */}
      <Dialog
        open={modalNuevoOpen}
        onClose={() => setModalNuevoOpen(false)}
        title="Registrar Nuevo Proveedor"
        description="Ingresa los datos del proveedor y selecciona si genera facturas CFDI o es sin factura."
        maxWidth="md"
      >
        <form onSubmit={handleCrear} className="space-y-4 text-xs">
          {errorNuevo && (
            <div className="p-2.5 bg-red-50 border border-red-200 rounded text-red-700 font-medium">
              {errorNuevo}
            </div>
          )}

          <div>
            <label className="block font-medium text-zinc-700 mb-1">Tipo de Proveedor *</label>
            <div className="grid grid-cols-2 gap-3">
              <label
                className={`flex items-center p-2.5 border rounded-md cursor-pointer ${
                  tipoNuevo === 'con_factura' ? 'border-zinc-900 bg-zinc-50 font-medium text-zinc-900' : 'border-zinc-200 text-zinc-600'
                }`}
              >
                <input
                  type="radio"
                  name="tipo"
                  checked={tipoNuevo === 'con_factura'}
                  onChange={() => setTipoNuevo('con_factura')}
                  className="mr-2"
                />
                Con Factura (Requiere RFC)
              </label>
              <label
                className={`flex items-center p-2.5 border rounded-md cursor-pointer ${
                  tipoNuevo === 'sin_factura' ? 'border-zinc-900 bg-zinc-50 font-medium text-zinc-900' : 'border-zinc-200 text-zinc-600'
                }`}
              >
                <input
                  type="radio"
                  name="tipo"
                  checked={tipoNuevo === 'sin_factura'}
                  onChange={() => setTipoNuevo('sin_factura')}
                  className="mr-2"
                />
                Sin Factura (RFC opcional)
              </label>
            </div>
          </div>

          {tipoNuevo === 'con_factura' && (
            <div>
              <label className="block font-medium text-zinc-700 mb-1">RFC Fiscal *</label>
              <input
                type="text"
                value={rfc}
                onChange={(e) => setRfc(e.target.value.toUpperCase())}
                placeholder="Ej. SSO020201MJ6"
                required={tipoNuevo === 'con_factura'}
                className="w-full px-3 py-2 border border-zinc-200 rounded-md font-mono uppercase focus:ring-1 focus:ring-zinc-900"
              />
            </div>
          )}

          <div>
            <label className="block font-medium text-zinc-700 mb-1">
              {tipoNuevo === 'con_factura' ? 'Razón Social Fiscal *' : 'Nombre del Proveedor / Persona *'}
            </label>
            <input
              type="text"
              value={razonSocial}
              onChange={(e) => setRazonSocial(e.target.value)}
              placeholder={tipoNuevo === 'con_factura' ? 'Ej. SILICONES Y SELLADORES DE OCCIDENTE SA DE CV' : 'Ej. Don Pedro Ferretero'}
              required
              className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900"
            />
          </div>

          <div>
            <label className="block font-medium text-zinc-700 mb-1">Alias Comercial (Opcional)</label>
            <input
              type="text"
              value={alias}
              onChange={(e) => setAlias(e.target.value)}
              placeholder="Ej. SILICONES Y SELLADORES"
              className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900"
            />
            <span className="text-[10px] text-zinc-400 mt-0.5 block">
              Nombre abreviado con el que aparecerá en el reporte de la memoria. Si lo dejas vacío, se usa el nombre principal.
            </span>
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
              {crearMutation.isPending ? 'Guardando...' : 'Crear Proveedor'}
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Diálogo para convertir Proveedor sin factura a con factura */}
      <Dialog
        open={!!proveedorAConvertir}
        onClose={() => setProveedorAConvertir(null)}
        title="Asignar RFC y Convertir a Proveedor con Factura"
        description={`Asigna un RFC oficial a "${proveedorAConvertir?.nombre_memoria}" para poder asociar facturas CFDI.`}
        maxWidth="sm"
      >
        <form onSubmit={handleConvertir} className="space-y-4 text-xs">
          {errorConversion && (
            <div className="p-2.5 bg-red-50 border border-red-200 rounded text-red-700 font-medium">
              {errorConversion}
            </div>
          )}

          <div>
            <label className="block font-medium text-zinc-700 mb-1">RFC Fiscal Oficial *</label>
            <input
              type="text"
              value={rfcConversion}
              onChange={(e) => setRfcConversion(e.target.value.toUpperCase())}
              placeholder="Ej. PDM800101XYZ"
              required
              autoFocus
              className="w-full px-3 py-2 border border-zinc-200 rounded-md font-mono uppercase focus:ring-1 focus:ring-zinc-900"
            />
          </div>

          <div className="flex items-center justify-end space-x-2 pt-4 border-t border-zinc-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setProveedorAConvertir(null)}
              disabled={actualizarMutation.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" size="sm" disabled={actualizarMutation.isPending}>
              {actualizarMutation.isPending ? 'Guardando...' : 'Convertir a Con Factura'}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  )
}
