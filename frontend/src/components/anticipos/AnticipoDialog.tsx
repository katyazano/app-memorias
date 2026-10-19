import React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import type { Anticipo } from '@/types'

const anticipoSchema = z.object({
  fecha: z.string().min(1, 'La fecha es obligatoria'),
  comprobante: z.string().min(1, 'El comprobante o referencia es obligatorio'),
  importe: z.string().refine((v) => !isNaN(parseFloat(v)) && parseFloat(v) > 0, 'Importe mayor a 0 obligatorio'),
})

type AnticipoFormValues = z.infer<typeof anticipoSchema>

interface AnticipoDialogProps {
  open: boolean
  onClose: () => void
  anticipoToEdit?: Anticipo | null
  onSubmit: (data: { fecha: string; comprobante: string; importe: string }) => Promise<void>
  isLoading?: boolean
}

export const AnticipoDialog: React.FC<AnticipoDialogProps> = ({
  open,
  onClose,
  anticipoToEdit,
  onSubmit,
  isLoading,
}) => {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AnticipoFormValues>({
    resolver: zodResolver(anticipoSchema),
  })

  React.useEffect(() => {
    if (anticipoToEdit) {
      reset({
        fecha: anticipoToEdit.fecha,
        comprobante: anticipoToEdit.comprobante,
        importe: anticipoToEdit.importe,
      })
    } else {
      reset({
        fecha: new Date().toISOString().slice(0, 10),
        comprobante: '',
        importe: '',
      })
    }
  }, [anticipoToEdit, reset, open])

  const handleFormSubmit = async (values: AnticipoFormValues) => {
    await onSubmit({
      fecha: values.fecha,
      comprobante: values.comprobante.trim(),
      importe: values.importe,
    })
    onClose()
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={anticipoToEdit ? 'Editar Anticipo' : 'Registrar Anticipo'}
      description="Registra transferencias o pagos a cuenta entregados por el cliente."
      maxWidth="sm"
    >
      <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4 text-xs">
        <div>
          <label className="block font-medium text-zinc-700 mb-1">Fecha del Anticipo *</label>
          <input
            {...register('fecha')}
            type="date"
            className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900 font-mono"
          />
          {errors.fecha && <p className="text-[11px] text-red-600 mt-1">{errors.fecha.message}</p>}
        </div>

        <div>
          <label className="block font-medium text-zinc-700 mb-1">Comprobante / Referencia bancaria *</label>
          <input
            {...register('comprobante')}
            placeholder="Ej. TRANSF-09124, CHEQUE 105"
            className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900 font-mono"
          />
          {errors.comprobante && <p className="text-[11px] text-red-600 mt-1">{errors.comprobante.message}</p>}
        </div>

        <div>
          <label className="block font-medium text-zinc-700 mb-1">Importe del Anticipo ($) *</label>
          <input
            {...register('importe')}
            type="number"
            step="0.01"
            placeholder="0.00"
            className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900 font-mono font-semibold"
          />
          {errors.importe && <p className="text-[11px] text-red-600 mt-1">{errors.importe.message}</p>}
        </div>

        <div className="flex items-center justify-end space-x-2 pt-4 border-t border-zinc-100">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
            Cancelar
          </Button>
          <Button type="submit" size="sm" disabled={isLoading}>
            {isLoading ? 'Guardando...' : anticipoToEdit ? 'Actualizar Anticipo' : 'Guardar Anticipo'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
