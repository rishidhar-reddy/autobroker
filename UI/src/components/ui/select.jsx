import { ChevronDown } from 'lucide-react'
import { cn } from '../../lib/utils.js'

/** Native select styled to match the system — keyboard and screen-reader
 *  behaviour comes free, which a div-based menu would have to re-implement. */
export function Select({ className, children, ...props }) {
  return (
    <div className="relative">
      <select
        className={cn(
          'h-10 w-full appearance-none rounded-lg border border-border-strong bg-surface-raised',
          'pl-3 pr-9 text-sm text-ink transition',
          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent',
          'disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted"
      />
    </div>
  )
}
