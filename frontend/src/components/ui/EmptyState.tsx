import React from 'react'
import { FolderOpen } from 'lucide-react'
import { Button } from './Button'

interface EmptyStateProps {
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
  icon?: React.ReactNode
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  actionLabel,
  onAction,
  icon,
}) => {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center rounded-lg border border-dashed border-zinc-200 bg-zinc-50/50">
      <div className="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center text-zinc-400 mb-3">
        {icon || <FolderOpen className="w-6 h-6" />}
      </div>
      <h3 className="text-sm font-semibold text-zinc-900">{title}</h3>
      <p className="text-xs text-zinc-500 max-w-sm mt-1 mb-4">{description}</p>
      {actionLabel && onAction && (
        <Button size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
