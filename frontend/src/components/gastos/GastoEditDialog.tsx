import React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { formatMoney } from '@/lib/utils'
import type { Gasto, Proveedor } from '@/types'

const gastoEditSchema = z.object({
  fecha: z.string().min(1, 'La fecha es obligatoria'),
  concepto_resumido: z.string().min(1, 'El concepto es obligatorio'),
  comprobante: z.string().optional(),
  tipo_comprobante: z.enum(['NOTA', 'TICKET', 'FACTURA', 'RECIBO']).optional(),
  metodo_pago: z.enum(['transferencia', 'efectivo']),
  importe: z.string().optional(),
  proveedor_id: z.string().optional(),
})

type GastoEditValues = z.infer<typeof gastoEditSchema>

interface GastoEditDialogProps {
  open: boolean
  onClose: () => void
  gasto: Gasto | null
  proveedores: Proveedor[]
  onSave: (id: number, data: any) => Promise<void>
  isLoading?: boolean
}

export const GastoEditDialog: React.FC<GastoEditDialogProps> = ({
  open,
  onClose,
  gasto,
  proveedores,
  onSave,
  isLoading,
}) => {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<GastoEditValues>({
    resolver: zodResolver(gastoEditSchema),
  })

  React.useEffect(() => {
    if (gasto) {
      reset({
        fecha: gasto.fecha,
        concepto_resumido: gasto.concepto_resumido,
        comprobante: gasto.comprobante || '',
        tipo_comprobante: (gasto.tipo_comprobante as any) || (gasto.origen === 'xml' ? 'FACTURA' : 'NOTA'),
        metodo_pago: gasto.metodo_pago,
        importe: gasto.importe,
        proveedor_id: gasto.proveedor_id ? String(gasto.proveedor_id) : '',
      })
    }
  }, [gasto, reset, open])

  if (!gasto) return null

  const esXml = gasto.origen === 'xml'

  const handleFormSubmit = async (values: GastoEditValues) => {
    const payload: any = {
      fecha: values.fecha,
      concepto_resumido: values.concepto_resumido,
      comprobante: values.comprobante || '',
      metodo_pago: values.metodo_pago,
      proveedor_id: values.proveedor_id ? Number(values.proveedor_id) : null,
    }
    if (!esXml) {
      if (values.tipo_comprobante) payload.tipo_comprobante = values.tipo_comprobante
      if (values.importe) payload.importe = values.importe
    }
    await onSave(gasto.id, payload)
    onClose()
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Editar Gasto"
      description={`Modifica los datos del comprobante #${gasto.id} (${gasto.origen.toUpperCase()})`}
      maxWidth="md"
    >
      <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4 text-xs">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-medium text-zinc-700 mb-1">Fecha *</label>
            <input
              {...register('fecha')}
              type="date"
              className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900 font-mono"
            />
            {errors.fecha && <p className="text-[11px] text-red-600 mt-1">{errors.fecha.message}</p>}
          </div>

          <div>
            <label className="block font-medium text-zinc-700 mb-1">Método de Pago *</label>
            <select
              {...register('metodo_pago')}
              className="w-full px-3 py-2 border border-zinc-200 rounded-md bg-white focus:ring-1 focus:ring-zinc-900"
            >
              <option value="transferencia">Transferencia</option>
              <option value="efectivo">Efectivo</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block font-medium text-zinc-700 mb-1">Proveedor / Alias comercial</label>
          <select
            {...register('proveedor_id')}
            className="w-full px-3 py-2 border border-zinc-200 rounded-md bg-white focus:ring-1 focus:ring-zinc-900"
          >
            <option value="">-- Sin proveedor asignado --</option>
            {proveedores.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre_memoria} ({p.rfc})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block font-medium text-zinc-700 mb-1">Concepto Resumido *</label>
          <input
            {...register('concepto_resumido')}
            placeholder="Descripción del gasto"
            className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900"
          />
          {errors.concepto_resumido && (
            <p className="text-[11px] text-red-600 mt-1">{errors.concepto_resumido.message}</p>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block font-medium text-zinc-700 mb-1">Tipo Comprobante</label>
            {esXml ? (
              <div className="px-3 py-2 bg-zinc-100 border border-zinc-200 rounded-md font-mono text-zinc-500 font-bold">
                FACTURA
              </div>
            ) : (
              <select
                {...register('tipo_comprobante')}
                className="w-full px-2.5 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900 bg-white font-medium"
              >
                <option value="NOTA">NOTA</option>
                <option value="TICKET">TICKET</option>
                <option value="FACTURA">FACTURA</option>
                <option value="RECIBO">RECIBO</option>
              </select>
            )}
          </div>

          <div>
            <label className="block font-medium text-zinc-700 mb-1">Comprobante / Folio</label>
            <input
              {...register('comprobante')}
              placeholder="Ej. 213, FLC 90648"
              className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900 font-mono"
            />
          </div>

          <div>
            <label className="block font-medium text-zinc-700 mb-1">
              Importe Total ($) {esXml && <span className="text-zinc-400 font-normal">(XML)</span>}
            </label>
            {esXml ? (
              <div className="px-3 py-2 bg-zinc-100 border border-zinc-200 rounded-md font-mono font-bold text-zinc-900">
                {formatMoney(gasto.importe)}
              </div>
            ) : (
              <input
                {...register('importe')}
                type="number"
                step="0.01"
                className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900 font-mono"
              />
            )}
          </div>
        </div>

        <div className="flex items-center justify-end space-x-2 pt-4 border-t border-zinc-100">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
            Cancelar
          </Button>
          <Button type="submit" size="sm" disabled={isLoading}>
            {isLoading ? 'Guardando...' : 'Guardar Cambios'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
