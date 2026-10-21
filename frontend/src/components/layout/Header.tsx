import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronRight, LogOut, CheckCircle2 } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'

export const Header: React.FC = () => {
  const location = useLocation()
  const pathnames = location.pathname.split('/').filter((x) => x)
  const obraId = pathnames[0] === 'obras' && pathnames[1] && !isNaN(Number(pathnames[1])) ? Number(pathnames[1]) : null

  const [modalSalirOpen, setModalSalirOpen] = useState(false)
  const [apagadoCompletado, setApagadoCompletado] = useState(false)
  const [apagando, setApagando] = useState(false)

  const { data: obra } = useQuery({
    queryKey: ['obra', obraId],
    queryFn: () => (obraId ? api.getObra(obraId) : null),
    enabled: !!obraId,
  })

  const handleConfirmarApagado = async () => {
    try {
      setApagando(true)
      await api.apagarSistema()
      setApagadoCompletado(true)
    } catch {
      // Si el servidor se apaga inmediatamente puede abortar la conexión, lo cual es normal
      setApagadoCompletado(true)
    } finally {
      setApagando(false)
    }
  }

  return (
    <>
      <header className="h-14 border-b border-zinc-200/80 bg-white/80 backdrop-blur sticky top-0 z-30 flex items-center justify-between px-6 no-print">
        <div className="flex items-center space-x-3">
          <Link to="/" className="flex items-center space-x-2 text-zinc-900 font-semibold tracking-tight text-sm">
            <div className="w-7 h-7 rounded bg-zinc-900 text-white flex items-center justify-center font-bold text-xs tracking-wider">
              ARQ
            </div>
            <span className="hidden sm:inline">Memorias de Gastos</span>
          </Link>
          <span className="text-zinc-300">/</span>
          <nav className="flex items-center space-x-1.5 text-xs text-zinc-500">
            <Link to="/" className="hover:text-zinc-900 transition-colors">
              Obras
            </Link>
            {obraId && (
              <>
                <ChevronRight className="w-3.5 h-3.5 text-zinc-400" />
                <Link to={`/obras/${obraId}`} className="text-zinc-900 font-medium hover:underline">
                  {obra?.nombre || `Obra #${obraId}`}
                </Link>
              </>
            )}
          </nav>
        </div>

        <div className="flex items-center space-x-3 text-xs text-zinc-500">
          <span className="hidden md:inline-flex items-center px-2 py-0.5 rounded bg-zinc-100 font-mono text-[11px] text-zinc-600">
            v2.0 Local SQLite
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setModalSalirOpen(true)}
            className="text-zinc-600 hover:text-red-700 hover:bg-red-50 text-xs px-2.5 h-8 font-medium gap-1.5"
            title="Cerrar el servidor y salir del sistema"
          >
            <LogOut className="w-3.5 h-3.5 text-zinc-500 group-hover:text-red-600" />
            <span>Salir</span>
          </Button>
        </div>
      </header>

      {/* Modal de confirmación de salida */}
      <Dialog
        open={modalSalirOpen}
        onClose={() => {
          if (!apagando && !apagadoCompletado) setModalSalirOpen(false)
        }}
        title={apagadoCompletado ? "Sistema Apagado" : "Salir de Memorias de Gastos"}
        description={apagadoCompletado ? "El servidor local se ha detenido con éxito." : "Confirmación de apagado del servidor local."}
      >
        <div className="p-5 space-y-4">
          {apagadoCompletado ? (
            <div className="text-center py-4 space-y-3">
              <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <p className="text-sm font-semibold text-zinc-900">
                El sistema se ha apagado correctamente.
              </p>
              <p className="text-xs text-zinc-500 leading-relaxed max-w-sm mx-auto">
                Tus datos están guardados de forma segura. Ya puedes cerrar esta pestaña o ventana del navegador.
              </p>
            </div>
          ) : (
            <>
              <p className="text-xs text-zinc-600 leading-relaxed">
                ¿Deseas apagar el servidor local de <strong>Memorias de Gastos</strong>?
                Todos los datos y archivos ya se encuentran guardados en tu equipo.
              </p>
              <div className="flex justify-end gap-2 pt-2 border-t border-zinc-100">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setModalSalirOpen(false)}
                  disabled={apagando}
                >
                  Continuar trabajando
                </Button>
                <Button
                  size="sm"
                  onClick={handleConfirmarApagado}
                  disabled={apagando}
                  className="bg-red-600 hover:bg-red-700 text-white"
                >
                  <LogOut className="w-3.5 h-3.5 mr-1.5" />
                  {apagando ? "Apagando..." : "Salir del Sistema"}
                </Button>
              </div>
            </>
          )}
        </div>
      </Dialog>
    </>
  )
}
