import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export const Header: React.FC = () => {
  const location = useLocation()
  const pathnames = location.pathname.split('/').filter((x) => x)
  const obraId = pathnames[0] === 'obras' && pathnames[1] && !isNaN(Number(pathnames[1])) ? Number(pathnames[1]) : null

  const { data: obra } = useQuery({
    queryKey: ['obra', obraId],
    queryFn: () => (obraId ? api.getObra(obraId) : null),
    enabled: !!obraId,
  })

  return (
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

      <div className="flex items-center space-x-4 text-xs text-zinc-500">
        <span className="hidden md:inline-flex items-center px-2 py-0.5 rounded bg-zinc-100 font-mono text-[11px] text-zinc-600">
          v2.0 Local SQLite
        </span>
      </div>
    </header>
  )
}
