import React from 'react'
import { Printer, ExternalLink, AlertTriangle } from 'lucide-react'
import { Dialog } from './ui/Dialog'
import { Button } from './ui/Button'

interface FallbackPdfModalProps {
  open: boolean
  onClose: () => void
  memoriaId: number | null
  errorMessage?: string | null
}

export const FallbackPdfModal: React.FC<FallbackPdfModalProps> = ({
  open,
  onClose,
  memoriaId,
  errorMessage,
}) => {
  const handleAbrirImprimir = () => {
    if (memoriaId) {
      window.open(`/memorias/${memoriaId}/imprimir`, '_blank')
    }
    onClose()
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Generación de PDF"
      description="Alternativa de guardado directo mediante tu navegador"
      maxWidth="md"
    >
      <div className="space-y-4 text-sm text-zinc-700">
        <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-amber-950">
              No se pudo completar la generación automática en segundo plano
            </p>
            <p className="text-amber-800 leading-relaxed">
              {errorMessage || 'El navegador del sistema no completó la renderización del archivo PDF.'}
            </p>
          </div>
        </div>

        <div className="bg-zinc-50 border border-zinc-200 rounded-lg p-4 space-y-2">
          <p className="font-medium text-zinc-900 flex items-center gap-1.5">
            <Printer className="w-4 h-4 text-indigo-600" />
            ¿Cómo guardar tu PDF con la versión imprimible?
          </p>
          <ol className="list-decimal list-inside space-y-1.5 text-xs text-zinc-600 pl-1">
            <li>
              Haz clic en <strong className="text-zinc-800">"Abrir versión imprimible"</strong> abajo para abrir la memoria formateada en una nueva pestaña.
            </li>
            <li>
              En esa pestaña, presiona <strong className="text-zinc-800">Ctrl + P</strong> (o el botón Imprimir arriba a la derecha).
            </li>
            <li>
              En el diálogo de impresión, selecciona como Destino: <strong className="text-zinc-800">"Guardar como PDF"</strong> (tamaño Carta).
            </li>
            <li>
              Haz clic en Guardar y elige la ubicación deseada.
            </li>
          </ol>
        </div>

        <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-100">
          <Button variant="outline" size="sm" onClick={onClose}>
            Cerrar
          </Button>
          <Button
            size="sm"
            onClick={handleAbrirImprimir}
            className="bg-indigo-600 hover:bg-indigo-700 text-white inline-flex items-center gap-1.5 shadow-sm"
          >
            <ExternalLink className="w-4 h-4" />
            <span>Abrir versión imprimible</span>
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
