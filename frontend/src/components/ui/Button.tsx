import React from 'react'
import { cn } from '@/lib/utils'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive'
  size?: 'sm' | 'md' | 'lg'
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'md', ...props }, ref) => {
    const base = 'inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950 disabled:pointer-events-none disabled:opacity-50 select-none'
    
    const variants = {
      default: 'bg-zinc-900 text-white hover:bg-zinc-800 shadow-sm active:bg-zinc-950',
      secondary: 'bg-zinc-100 text-zinc-900 hover:bg-zinc-200 active:bg-zinc-300',
      outline: 'border border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-800 active:bg-zinc-100',
      ghost: 'hover:bg-zinc-100 text-zinc-700 active:bg-zinc-200',
      destructive: 'bg-red-600 text-white hover:bg-red-700 active:bg-red-800 shadow-sm',
    }

    const sizes = {
      sm: 'h-8 px-2.5 text-xs rounded',
      md: 'h-9 px-3.5 text-sm rounded-md',
      lg: 'h-11 px-5 text-base rounded-md',
    }

    return (
      <button
        ref={ref}
        className={cn(base, variants[variant], sizes[size], className)}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'
