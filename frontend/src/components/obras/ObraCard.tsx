import React from 'react'
import { Link } from 'react-router-dom'
import { Building2, User, MapPin, ArrowRight, Edit, Receipt } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { formatMoney } from '@/lib/utils'
import type { ObraResumenCard } from '@/types'

interface ObraCardProps {
  obra: ObraResumenCard
  onEdit: (obra: ObraResumenCard) => void
}

export const ObraCard: React.FC<ObraCardProps> = ({ obra, onEdit }) => {
  const estadoBadge = {
    en_curso: { label: 'En curso', variant: 'success' as const },
    pausada: { label: 'Pausada', variant: 'warning' as const },
    concluida: { label: 'Concluida', variant: 'muted' as const },
  }[obra.estado] || { label: obra.estado, variant: 'muted' as const }

  return (
    <Card className="hover:border-zinc-300 transition-all duration-150 flex flex-col justify-between group">
      <div>
        <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
          <div className="space-y-1 pr-2">
            <CardTitle className="text-base group-hover:text-zinc-950 transition-colors">
              <Link to={`/obras/${obra.id}`} className="hover:underline">
                {obra.nombre}
              </Link>
            </CardTitle>
            <div className="flex items-center space-x-1.5 text-xs text-zinc-500">
              <User className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
              <span className="truncate">{obra.propietario || 'Sin propietario especificado'}</span>
            </div>
            {obra.ubicacion && (
              <div className="flex items-center space-x-1.5 text-xs text-zinc-400">
                <MapPin className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                <span className="truncate">{obra.ubicacion}</span>
              </div>
            )}
          </div>
          <Badge variant={estadoBadge.variant}>{estadoBadge.label}</Badge>
        </CardHeader>

        <CardContent className="space-y-3 pt-2">
          <div className="grid grid-cols-2 gap-2 p-2.5 rounded-md bg-zinc-50 border border-zinc-100 text-xs">
            <div>
              <p className="text-[11px] text-zinc-400 uppercase font-semibold">Gastado a la fecha</p>
              <p className="font-semibold text-zinc-900 mt-0.5">{formatMoney(obra.gastado_a_la_fecha)}</p>
            </div>
            <div>
              <p className="text-[11px] text-zinc-400 uppercase font-semibold">Honorarios</p>
              <p className="font-semibold text-zinc-800 mt-0.5">{obra.porcentaje_honorarios}%</p>
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-zinc-500 px-0.5">
            <span className="flex items-center space-x-1">
              <Receipt className="w-3.5 h-3.5 text-zinc-400" />
              <span>
                {obra.numero_ultima_memoria ? `Última: Memoria #${obra.numero_ultima_memoria}` : 'Sin memorias'}
              </span>
            </span>
            <span>{obra.total_gastos} gastos reg.</span>
          </div>
        </CardContent>
      </div>

      <CardFooter className="bg-zinc-50/50 justify-between gap-2">
        <Button variant="ghost" size="sm" onClick={() => onEdit(obra)} className="text-xs text-zinc-600">
          <Edit className="w-3.5 h-3.5 mr-1" />
          Editar
        </Button>
        <Link to={`/obras/${obra.id}`}>
          <Button variant="default" size="sm" className="text-xs">
            Abrir
            <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Button>
        </Link>
      </CardFooter>
    </Card>
  )
}
