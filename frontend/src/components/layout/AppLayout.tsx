import React from 'react'
import { Outlet, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { api } from '@/lib/api'
import { FRONTEND_BUILD_VERSION } from '@/version'

export const AppLayout: React.FC = () => {
  // Latido continuo mientras el usuario tenga abierta la aplicación (cada 30s)
  React.useEffect(() => {
    api.enviarHeartbeat()
    const timer = setInterval(() => {
      api.enviarHeartbeat()
    }, 30000)
    return () => clearInterval(timer)
  }, [])

  const { data: healthData } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.getHealth(),
    staleTime: 15000,
  })

  const backendVersion = healthData?.version_build?.version_codigo
  const hayDesincronizacion = Boolean(
    healthData && (!healthData.version_build || backendVersion !== FRONTEND_BUILD_VERSION)
  )

  return (
    <div className="min-h-screen bg-[#fafafa] flex flex-col font-sans">
      <Header />
      {hayDesincronizacion && (
        <div className="bg-amber-500 text-white px-4 py-2 text-xs font-medium flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>
              <strong>Aviso de versión:</strong> El servidor backend ({backendVersion || 'desactualizado'}) no coincide con el frontend ({FRONTEND_BUILD_VERSION}). Reinicia el servidor para cargar las últimas correcciones de Excel y PDF.
            </span>
          </div>
          <Link
            to="/configuracion"
            className="underline hover:text-amber-100 font-semibold ml-4 shrink-0"
          >
            Ver en Configuración
          </Link>
        </div>
      )}
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-8 max-w-7xl mx-auto w-full">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

