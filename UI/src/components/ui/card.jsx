import { cn } from '../../lib/utils.js'

export function Card({ className, ...props }) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border-base bg-surface-raised shadow-sm',
        className,
      )}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }) {
  return <div className={cn('flex items-start justify-between gap-3 px-5 pt-4 pb-3', className)} {...props} />
}

export function CardTitle({ className, ...props }) {
  return <h2 className={cn('text-sm font-semibold tracking-tight text-ink', className)} {...props} />
}

export function CardDescription({ className, ...props }) {
  return <p className={cn('text-xs text-ink-muted', className)} {...props} />
}

export function CardContent({ className, ...props }) {
  return <div className={cn('px-5 pb-5', className)} {...props} />
}
