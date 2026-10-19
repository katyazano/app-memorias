import React, { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import type { ObraResumenCard, ObraCreate, ObraUpdate } from '@/types'

const obraSchema = z.object({
  nombre: z.string().min(1, 'El nombre es obligatorio'),
  ubicacion: z.string().optional(),
  propietario: z.string().optional(),
  porcentaje_honorarios: z.string().refine((val) => {
    const n = parseFloat(val)
    return !isNaN(n) && n >= 0 && n <= 100
  }, 'Debe ser un porcentaje entre 0 y 100'),
  saldo_inicial_transferencias: z.string().refine((val) => !isNaN(parseFloat(val)) && parseFloat(val) >= 0, 'Monto inválido'),
  saldo_inicial_efectivo: z.string().refine((val) => !isNaN(parseFloat(val)) && parseFloat(val) >= 0, 'Monto inválido'),
  saldo_inicial_rayas: z.string().refine((val) => !isNaN(parseFloat(val)) && parseFloat(val) >= 0, 'Monto inválido'),
  saldo_inicial_memorias_anteriores: z.string().refine((val) => !isNaN(parseFloat(val)) && parseFloat(val) >= 0, 'Monto inválido'),
  numero_ultima_memoria_previa: z.number().int().min(0, 'Debe ser un número entero mayor o igual a 0'),
  estado: z.enum(['en_curso', 'pausada', 'concluida']),
})

type ObraFormValues = z.infer<typeof obraSchema>

interface ObraDialogProps {
  open: boolean
  onClose: () => void
  obraToEdit?: ObraResumenCard | null
  onSubmit: (data: ObraCreate | ObraUpdate) => Promise<void>
  isLoading?: boolean
}

export const ObraDialog: React.FC<ObraDialogProps> = ({
  open,
  onClose,
  obraToEdit,
  onSubmit,
  isLoading,
}) => {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ObraFormValues>({
    resolver: zodResolver(obraSchema),
    defaultValues: {
      nombre: '',
      ubicacion: '',
      propietario: '',
      porcentaje_honorarios: '10.00',
      saldo_inicial_transferencias: '0.00',
      saldo_inicial_efectivo: '0.00',
      saldo_inicial_rayas: '0.00',
      saldo_inicial_memorias_anteriores: '0.00',
      numero_ultima_memoria_previa: 0,
      estado: 'en_curso',
    },
  })

  useEffect(() => {
    if (obraToEdit) {
      reset({
        nombre: obraToEdit.nombre,
        ubicacion: obraToEdit.ubicacion || '',
        propietario: obraToEdit.propietario || '',
        porcentaje_honorarios: obraToEdit.porcentaje_honorarios,
        saldo_inicial_transferencias: obraToEdit.saldo_inicial_transferencias || obraToEdit.saldo_inicial_acumulado || '0.00',
        saldo_inicial_efectivo: obraToEdit.saldo_inicial_efectivo || '0.00',
        saldo_inicial_rayas: obraToEdit.saldo_inicial_rayas || '0.00',
        saldo_inicial_memorias_anteriores: obraToEdit.saldo_inicial_memorias_anteriores || obraToEdit.saldo_inicial_gastado || '0.00',
        numero_ultima_memoria_previa: obraToEdit.numero_ultima_memoria_previa || 0,
        estado: obraToEdit.estado,
      })
    } else {
      reset({
        nombre: '',
        ubicacion: '',
        propietario: '',
        porcentaje_honorarios: '10.00',
        saldo_inicial_transferencias: '0.00',
        saldo_inicial_efectivo: '0.00',
        saldo_inicial_rayas: '0.00',
        saldo_inicial_memorias_anteriores: '0.00',
        numero_ultima_memoria_previa: 0,
        estado: 'en_curso',
      })
    }
  }, [obraToEdit, reset, open])

  const handleFormSubmit = async (values: ObraFormValues) => {
    await onSubmit(values)
    onClose()
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={obraToEdit ? 'Editar Obra' : 'Nueva Obra'}
      description="Ingresa los datos generales, porcentaje de honorarios y saldos iniciales."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-zinc-700 mb-1">Nombre de la obra *</label>
          <input
            {...register('nombre')}
            placeholder="Ej. Residencia Lomas del Valle"
            className="w-full text-xs px-3 py-2 border border-zinc-200 rounded-md focus:outline-none focus:ring-1 focus:ring-zinc-900"
          />
          {errors.nombre && <p className="text-[11px] text-red-600 mt-1">{errors.nombre.message}</p>}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">Propietario / Cliente</label>
            <input
              {...register('propietario')}
              placeholder="Ej. Ing. Carlos Mendoza"
              className="w-full text-xs px-3 py-2 border border-zinc-200 rounded-md focus:outline-none focus:ring-1 focus:ring-zinc-900"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">Ubicación</label>
            <input
              {...register('ubicacion')}
              placeholder="Ej. Bosques de las Lomas"
              className="w-full text-xs px-3 py-2 border border-zinc-200 rounded-md focus:outline-none focus:ring-1 focus:ring-zinc-900"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">% Honorarios *</label>
            <div className="relative">
              <input
                {...register('porcentaje_honorarios')}
                type="number"
                step="0.01"
                className="w-full text-xs px-3 py-2 pr-7 border border-zinc-200 rounded-md focus:outline-none focus:ring-1 focus:ring-zinc-900"
              />
              <span className="absolute right-2.5 top-2 text-xs text-zinc-400 font-medium">%</span>
            </div>
            {errors.porcentaje_honorarios && (
              <p className="text-[11px] text-red-600 mt-1">{errors.porcentaje_honorarios.message}</p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">Estado</label>
            <select
              {...register('estado')}
              className="w-full text-xs px-3 py-2 border border-zinc-200 rounded-md focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white"
            >
              <option value="en_curso">En curso</option>
              <option value="pausada">Pausada</option>
              <option value="concluida">Terminada</option>
            </select>
          </div>
        </div>

        <div className="border-t border-zinc-100 pt-3">
          <p className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider mb-2">
            Historial previo al sistema (Obras ya iniciadas)
          </p>

          <div className="mb-3">
            <label className="block text-xs font-medium text-zinc-700 mb-1">
              Número de la última memoria previa al sistema
            </label>
            <input
              {...register('numero_ultima_memoria_previa', { valueAsNumber: true })}
              type="number"
              min="0"
              placeholder="0"
              className="w-full text-xs px-3 py-2 border border-zinc-200 rounded-md focus:outline-none focus:ring-1 focus:ring-zinc-900 font-mono"
            />
            <span className="text-[10px] text-zinc-400 mt-0.5 block">
              La siguiente memoria sugerida iniciará a partir de este número + 1 (ej. si fue 15, sugerirá Memoria #16)
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">
                Importe de memorias anteriores ($)
              </label>
              <input
                {...register('saldo_inicial_memorias_anteriores')}
                type="number"
                step="0.01"
                placeholder="0.00"
                className="w-full text-xs px-3 py-2 border border-zinc-200 rounded-md focus:outline-none focus:ring-1 focus:ring-zinc-900 font-mono"
              />
              <span className="text-[10px] text-zinc-400 mt-0.5 block">Total gastado en memorias antes de este sistema</span>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">
                Transferencias anteriores ($)
              </label>
              <input
                {...register('saldo_inicial_transferencias')}
                type="number"
                step="0.01"
                placeholder="0.00"
                className="w-full text-xs px-3 py-2 border border-zinc-200 rounded-md focus:outline-none focus:ring-1 focus:ring-zinc-900 font-mono"
              />
              <span className="text-[10px] text-zinc-400 mt-0.5 block">Transferencias pagadas previas al sistema</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">
                Efectivo anterior ($)
              </label>
              <input
                {...register('saldo_inicial_efectivo')}
                type="number"
                step="0.01"
                placeholder="0.00"
                className="w-full text-xs px-3 py-2 border border-zinc-200 rounded-md focus:outline-none focus:ring-1 focus:ring-zinc-900 font-mono"
              />
              <span className="text-[10px] text-zinc-400 mt-0.5 block">Gastos en efectivo previos al sistema</span>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">
                Rayas / Nómina anterior ($)
              </label>
              <input
                {...register('saldo_inicial_rayas')}
                type="number"
                step="0.01"
                placeholder="0.00"
                className="w-full text-xs px-3 py-2 border border-zinc-200 rounded-md focus:outline-none focus:ring-1 focus:ring-zinc-900 font-mono"
              />
              <span className="text-[10px] text-zinc-400 mt-0.5 block">Pagos de rayas previos al sistema</span>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end space-x-2 pt-4 border-t border-zinc-100">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
            Cancelar
          </Button>
          <Button type="submit" size="sm" disabled={isLoading}>
            {isLoading ? 'Guardando...' : obraToEdit ? 'Actualizar Obra' : 'Crear Obra'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
