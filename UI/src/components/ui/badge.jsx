import { cn } from '../../lib/utils.js'

export function Badge({ className, ...props }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border border-border-base ' +
          'bg-surface-sunken px-2.5 py-0.5 text-xs font-medium text-ink-secondary',
        className,
      )}
      {...props}
    />
  )
}
