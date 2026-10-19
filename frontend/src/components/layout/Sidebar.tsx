import React from 'react'
import { NavLink } from 'react-router-dom'
import { Building2, Users, Store, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'

export const Sidebar: React.FC = () => {
  const links = [
    { to: '/', label: 'Obras', icon: Building2 },
    { to: '/trabajadores', label: 'Empleados', icon: Users },
    { to: '/proveedores', label: 'Proveedores', icon: Store },
    { to: '/configuracion', label: 'Configuración', icon: Settings },
  ]

  return (
    <aside className="w-56 border-r border-zinc-200/80 bg-white min-h-[calc(100vh-3.5rem)] p-4 flex flex-col justify-between no-print">
      <div className="space-y-1">
        <p className="px-3 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">
          Gestión
        </p>
        {links.map((link) => {
          const Icon = link.icon
          return (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center space-x-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors',
                  isActive
                    ? 'bg-zinc-100 text-zinc-950 font-semibold'
                    : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-50'
                )
              }
            >
              <Icon className="w-4 h-4 text-zinc-500" />
              <span>{link.label}</span>
            </NavLink>
          )
        })}
      </div>

      <div className="pt-4 border-t border-zinc-100 px-3">
        <p className="text-[11px] text-zinc-400 font-medium">Despacho de Arquitectura</p>
        <p className="text-[10px] text-zinc-400">Control Financiero de Obra</p>
      </div>
    </aside>
  )
}
