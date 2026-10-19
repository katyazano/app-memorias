import React, { useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { api } from '@/lib/api'
import type { GastoManualCreate, Proveedor } from '@/types'

const gastoManualSchema = z.object({
  fecha: z.string().min(1, 'La fecha es obligatoria'),
  proveedor_texto: z.string().optional(),
  proveedor_id: z.string().optional(),
  concepto_resumido: z.string().min(1, 'El concepto es obligatorio'),
  comprobante: z.string().optional(),
  tipo_comprobante: z.enum(['NOTA', 'TICKET', 'FACTURA', 'RECIBO']),
  importe: z.string().refine((v) => !isNaN(parseFloat(v)) && parseFloat(v) > 0, 'Importe mayor a 0 obligatorio'),
  metodo_pago: z.enum(['transferencia', 'efectivo']),
  origen: z.enum(['manual', 'nota']),
})

type GastoManualFormValues = z.infer<typeof gastoManualSchema>

interface GastoManualDialogProps {
  open: boolean
  onClose: () => void
  proveedores: Proveedor[]
  onSubmit: (data: GastoManualCreate) => Promise<void>
  isLoading?: boolean
}

export const GastoManualDialog: React.FC<GastoManualDialogProps> = ({
  open,
  onClose,
  proveedores,
  onSubmit,
  isLoading,
}) => {
  const conceptoInputRef = useRef<HTMLInputElement | null>(null)
  const [busquedaProveedor, setBusquedaProveedor] = useState('')
  const [mostrarOpciones, setMostrarOpciones] = useState(false)
  const [proveedorSeleccionado, setProveedorSeleccionado] = useState<Proveedor | null>(null)
  const [creandoProv, setCreandoProv] = useState(false)
  const [errorProveedor, setErrorProveedor] = useState('')

  const {
    register,
    handleSubmit,
    reset,
    getValues,
    setValue,
    formState: { errors },
  } = useForm<GastoManualFormValues>({
    resolver: zodResolver(gastoManualSchema),
    defaultValues: {
      fecha: new Date().toISOString().slice(0, 10),
      proveedor_texto: '',
      proveedor_id: '',
      concepto_resumido: '',
      comprobante: '',
      tipo_comprobante: 'NOTA',
      importe: '',
      metodo_pago: 'efectivo',
      origen: 'nota',
    },
  })

  React.useEffect(() => {
    if (open) {
      setBusquedaProveedor('')
      setProveedorSeleccionado(null)
      setMostrarOpciones(false)
      reset({
        fecha: new Date().toISOString().slice(0, 10),
        proveedor_texto: '',
        proveedor_id: '',
        concepto_resumido: '',
        comprobante: '',
        tipo_comprobante: 'NOTA',
        importe: '',
        metodo_pago: 'efectivo',
        origen: 'nota',
      })
    }
  }, [open, reset])

  const proveedoresFiltrados = proveedores.filter((p) => {
    if (!busquedaProveedor.trim()) return true
    const term = busquedaProveedor.toLowerCase()
    return (
      p.nombre_memoria.toLowerCase().includes(term) ||
      (p.rfc && p.rfc.toLowerCase().includes(term)) ||
      p.razon_social.toLowerCase().includes(term)
    )
  })

  const proveedorExiste = proveedores.some(
    (p) => p.nombre_memoria.toLowerCase() === busquedaProveedor.trim().toLowerCase()
  )

  const guardarGasto = async (values: GastoManualFormValues) => {
    const payload: GastoManualCreate = {
      fecha: values.fecha,
      proveedor_id: values.proveedor_id ? Number(values.proveedor_id) : null,
      concepto_resumido: values.concepto_resumido.trim(),
      comprobante: values.comprobante?.trim() || '',
      tipo_comprobante: values.tipo_comprobante,
      importe: values.importe,
      metodo_pago: values.metodo_pago,
      origen: values.origen,
    }
    await onSubmit(payload)
  }

  const handleSoloGuardar = async (values: GastoManualFormValues) => {
    await guardarGasto(values)
    onClose()
  }

  const handleGuardarYAgregarOtro = async () => {
    const values = getValues()
    // Validar manualmente campos requeridos
    if (!values.concepto_resumido.trim() || !values.importe || isNaN(parseFloat(values.importe))) {
      return
    }
    await guardarGasto(values)
    // Limpiar para el siguiente manteniendo la fecha y el método
    setValue('concepto_resumido', '')
    setValue('comprobante', '')
    setValue('importe', '')
    conceptoInputRef.current?.focus()
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Registrar Gasto Manual / Nota"
      description="Registra pagos en efectivo, transferencias directas o compras con notas que no generan CFDI."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit(handleSoloGuardar)} className="space-y-4 text-xs">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-medium text-zinc-700 mb-1">Fecha del Gasto *</label>
            <input
              {...register('fecha')}
              type="date"
              className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900 font-mono"
            />
            {errors.fecha && <p className="text-[11px] text-red-600 mt-1">{errors.fecha.message}</p>}
          </div>

          <div>
            <label className="block font-medium text-zinc-700 mb-1">Tipo de Origen *</label>
            <select
              {...register('origen')}
              className="w-full px-3 py-2 border border-zinc-200 rounded-md bg-white focus:ring-1 focus:ring-zinc-900 font-medium"
            >
              <option value="nota">Nota de remisión / Ticket</option>
              <option value="manual">Pago manual sin comprobante</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-medium text-zinc-700 mb-1">Método de Pago *</label>
            <select
              {...register('metodo_pago')}
              className="w-full px-3 py-2 border border-zinc-200 rounded-md bg-white focus:ring-1 focus:ring-zinc-900 font-medium"
            >
              <option value="efectivo">Efectivo</option>
              <option value="transferencia">Transferencia bancaria</option>
            </select>
          </div>

          <div className="relative">
            <label className="block font-medium text-zinc-700 mb-1">Proveedor / Beneficiario</label>
            <div className="flex items-center space-x-1">
              <input
                type="text"
                value={busquedaProveedor}
                onChange={(e) => {
                  setBusquedaProveedor(e.target.value)
                  setProveedorSeleccionado(null)
                  setValue('proveedor_id', '')
                  setMostrarOpciones(true)
                }}
                onFocus={() => setMostrarOpciones(true)}
                placeholder="Buscar o escribir nombre nuevo..."
                className="w-full px-3 py-2 border border-zinc-200 rounded-md bg-white focus:ring-1 focus:ring-zinc-900 text-xs"
              />
              {proveedorSeleccionado && (
                <button
                  type="button"
                  onClick={() => {
                    setProveedorSeleccionado(null)
                    setBusquedaProveedor('')
                    setValue('proveedor_id', '')
                  }}
                  className="px-2 py-1 text-zinc-400 hover:text-zinc-600 text-xs font-bold"
                  title="Limpiar proveedor"
                >
                  ✕
                </button>
              )}
            </div>

            {mostrarOpciones && (
              <div className="absolute z-20 left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border border-zinc-200 rounded-md shadow-lg py-1 text-xs">
                {proveedoresFiltrados.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      setProveedorSeleccionado(p)
                      setBusquedaProveedor(p.nombre_memoria)
                      setValue('proveedor_id', String(p.id))
                      setMostrarOpciones(false)
                    }}
                    className="w-full text-left px-3 py-1.5 hover:bg-zinc-100 flex items-center justify-between"
                  >
                    <span className="font-medium text-zinc-900">{p.nombre_memoria}</span>
                    <span className="text-[10px] text-zinc-400">
                      {p.tipo === 'sin_factura' ? '(Sin factura)' : p.rfc || ''}
                    </span>
                  </button>
                ))}

                {busquedaProveedor.trim() && !proveedorExiste && (
                  <button
                    type="button"
                    disabled={creandoProv}
                    onClick={async () => {
                      try {
                        setCreandoProv(true)
                        setErrorProveedor('')
                        const nuevo = await api.createProveedor({
                          tipo: 'sin_factura',
                          razon_social: busquedaProveedor.trim(),
                          alias: busquedaProveedor.trim(),
                        })
                        setProveedorSeleccionado(nuevo)
                        setBusquedaProveedor(nuevo.nombre_memoria)
                        setValue('proveedor_id', String(nuevo.id))
                        setMostrarOpciones(false)
                      } catch (err: any) {
                        setErrorProveedor(err.message || 'Error al registrar proveedor')
                      } finally {
                        setCreandoProv(false)
                      }
                    }}
                    className="w-full text-left px-3 py-2 hover:bg-emerald-50 text-emerald-800 font-medium border-t border-zinc-100 flex items-center space-x-1"
                  >
                    <span>+ Registrar "<strong>{busquedaProveedor.trim()}</strong>" como proveedor sin factura</span>
                  </button>
                )}

                {proveedoresFiltrados.length === 0 && !busquedaProveedor.trim() && (
                  <div className="px-3 py-2 text-zinc-400 text-[11px]">Escribe para buscar o agregar</div>
                )}
              </div>
            )}

            {errorProveedor && (
              <p className="text-[11px] text-red-600 mt-1 font-medium">{errorProveedor}</p>
            )}
          </div>
        </div>

        <div>
          <label className="block font-medium text-zinc-700 mb-1">Concepto Resumido *</label>
          <input
            {...register('concepto_resumido')}
            ref={(e) => {
              register('concepto_resumido').ref(e)
              conceptoInputRef.current = e
            }}
            placeholder="Ej. Viaje de arena fina, tornillería menor, viáticos"
            className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900"
          />
          {errors.concepto_resumido && (
            <p className="text-[11px] text-red-600 mt-1">{errors.concepto_resumido.message}</p>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block font-medium text-zinc-700 mb-1">Tipo de Comprobante *</label>
            <select
              {...register('tipo_comprobante')}
              className="w-full px-2.5 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900 bg-white font-medium"
            >
              <option value="NOTA">NOTA</option>
              <option value="TICKET">TICKET</option>
              <option value="FACTURA">FACTURA</option>
              <option value="RECIBO">RECIBO</option>
            </select>
          </div>

          <div>
            <label className="block font-medium text-zinc-700 mb-1">Folio / Número</label>
            <input
              {...register('comprobante')}
              placeholder="Ej. 213, 92989"
              className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900 font-mono"
            />
          </div>

          <div>
            <label className="block font-medium text-zinc-700 mb-1">Importe Total ($) *</label>
            <input
              {...register('importe')}
              type="number"
              step="0.01"
              placeholder="0.00"
              className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:ring-1 focus:ring-zinc-900 font-mono font-semibold"
            />
            {errors.importe && <p className="text-[11px] text-red-600 mt-1">{errors.importe.message}</p>}
          </div>
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-zinc-100">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleGuardarYAgregarOtro}
            disabled={isLoading}
          >
            Guardar y agregar otro
          </Button>

          <div className="flex items-center space-x-2">
            <Button type="button" variant="ghost" size="sm" onClick={onClose} disabled={isLoading}>
              Cancelar
            </Button>
            <Button type="submit" size="sm" disabled={isLoading}>
              {isLoading ? 'Guardando...' : 'Guardar Gasto'}
            </Button>
          </div>
        </div>
      </form>
    </Dialog>
  )
}
