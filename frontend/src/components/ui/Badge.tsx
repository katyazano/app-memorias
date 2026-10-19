import React from 'react'
import { cn } from '@/lib/utils'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'muted' | 'outline'
}

export const Badge: React.FC<BadgeProps> = ({ className, variant = 'default', ...props }) => {
  const variants = {
    default: 'bg-zinc-900 text-white',
    success: 'bg-emerald-50 text-emerald-800 border border-emerald-200',
    warning: 'bg-amber-50 text-amber-800 border border-amber-200',
    muted: 'bg-zinc-100 text-zinc-700 border border-zinc-200',
    outline: 'border border-zinc-300 text-zinc-800',
  }

  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
        variants[variant],
        className
      )}
      {...props}
    />
  )
}
