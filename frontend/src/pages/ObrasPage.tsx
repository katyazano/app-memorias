import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Building2 } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { ObraCard } from '@/components/obras/ObraCard'
import { ObraDialog } from '@/components/obras/ObraDialog'
import type { ObraResumenCard, ObraCreate, ObraUpdate } from '@/types'

export const ObrasPage: React.FC = () => {
  const queryClient = useQueryClient()
  const [searchTerm, setSearchTerm] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [obraToEdit, setObraToEdit] = useState<ObraResumenCard | null>(null)

  const { data: obras, isLoading, isError, error } = useQuery<ObraResumenCard[]>({
    queryKey: ['obras-resumen'],
    queryFn: api.getObrasResumen,
  })

  const createMutation = useMutation({
    mutationFn: (data: ObraCreate) => api.createObra(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['obras-resumen'] })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ObraUpdate }) => api.updateObra(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['obras-resumen'] })
    },
  })

  const handleOpenCreate = () => {
    setObraToEdit(null)
    setDialogOpen(true)
  }

  const handleOpenEdit = (obra: ObraResumenCard) => {
    setObraToEdit(obra)
    setDialogOpen(true)
  }

  const handleSaveObra = async (formData: ObraCreate | ObraUpdate) => {
    if (obraToEdit) {
      await updateMutation.mutateAsync({ id: obraToEdit.id, data: formData })
    } else {
      await createMutation.mutateAsync(formData as ObraCreate)
    }
  }

  const filteredObras = obras?.filter((o) => {
    const q = searchTerm.toLowerCase()
    return o.nombre.toLowerCase().includes(q) || (o.propietario && o.propietario.toLowerCase().includes(q))
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-200/80 pb-4">
        <div>
          <h1 className="text-xl font-bold text-zinc-900 tracking-tight">Obras en Curso</h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            Gestión financiera, facturación CFDI y memorias de gastos por proyecto arquitectónico.
          </p>
        </div>
        <Button onClick={handleOpenCreate} className="shrink-0">
          <Plus className="w-4 h-4 mr-1.5" />
          Nueva Obra
        </Button>
      </div>

      <div className="flex items-center space-x-3 max-w-sm">
        <div className="relative w-full">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-zinc-400" />
          <input
            type="text"
            placeholder="Buscar por nombre o propietario..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs border border-zinc-200 rounded-md focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="p-5 border border-zinc-200 rounded-lg bg-white space-y-4">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
              <div className="grid grid-cols-2 gap-2 pt-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
          Error al cargar obras: {(error as Error).message}
        </div>
      ) : !filteredObras || filteredObras.length === 0 ? (
        <EmptyState
          title={searchTerm ? 'No se encontraron obras coincidentes' : 'Aún no hay obras registradas'}
          description={
            searchTerm
              ? 'Prueba con otro término de búsqueda o limpia el filtro.'
              : 'Comienza creando tu primera obra para gestionar facturas, rayas y generar memorias.'
          }
          actionLabel={searchTerm ? undefined : 'Crear Primera Obra'}
          onAction={searchTerm ? undefined : handleOpenCreate}
          icon={<Building2 className="w-6 h-6" />}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredObras.map((obra) => (
            <ObraCard key={obra.id} obra={obra} onEdit={handleOpenEdit} />
          ))}
        </div>
      )}

      <ObraDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        obraToEdit={obraToEdit}
        onSubmit={handleSaveObra}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />
    </div>
  )
}
