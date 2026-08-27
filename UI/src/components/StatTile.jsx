import { Skeleton } from './ui/skeleton.jsx'
import { cn } from '../lib/utils.js'

/**
 * A single headline number. Deliberately not a chart: these are one-value
 * measures with no series and no time axis, so a plot would add ink without
 * adding information.
 */
export function StatTile({ label, value, hint, loading, className }) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border-base bg-surface-raised px-4 py-3.5',
        className,
      )}
    >
      <div className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</div>
      {loading ? (
        <Skeleton className="mt-2 h-7 w-20" />
      ) : (
        <div className="mt-1 font-mono text-2xl font-semibold tabular-nums text-ink">{value}</div>
      )}
      {hint && !loading && <div className="mt-0.5 text-xs text-ink-muted">{hint}</div>}
    </div>
  )
}
