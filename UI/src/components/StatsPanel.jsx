import { Card, CardContent, CardHeader, CardTitle } from './ui/card.jsx'
import { StatTile } from './StatTile.jsx'
import { STATUS_META } from './StatusBadge.jsx'
import { formatCurrency, formatNumber, formatPercent } from '../lib/utils.js'

/**
 * Aggregate view over every negotiation the backend has persisted.
 *
 * Five single-value measures rendered as stat tiles, plus a status breakdown.
 * The breakdown is a labelled count row rather than a bar chart: with a handful
 * of categories and small integer counts, the numbers are the information and a
 * plot would only make them harder to read.
 */
export function StatsPanel({ stats }) {
  const loading = !stats
  const byStatus = stats?.by_status ?? {}
  const statuses = Object.keys(STATUS_META).filter((key) => byStatus[key])

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Across all negotiations</CardTitle>
          <p className="mt-0.5 text-xs text-ink-muted">
            Persisted server-side, so these survive a restart.
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          <StatTile label="Total runs" value={formatNumber(stats?.total_negotiations)} loading={loading} />
          <StatTile
            label="Settled"
            value={formatPercent(stats?.convergence_rate)}
            hint={
              stats?.finished
                ? `${stats.settled} of ${stats.finished} finished`
                : 'no finished runs yet'
            }
            loading={loading}
          />
          <StatTile
            label="Avg turns"
            value={stats?.avg_turns_to_settle != null ? formatNumber(stats.avg_turns_to_settle, 1) : '—'}
            hint="to settle"
            loading={loading}
          />
          <StatTile
            label="Avg unit price"
            value={formatCurrency(stats?.avg_agreed_unit_price)}
            loading={loading}
          />
          <StatTile label="Avg deal" value={formatCurrency(stats?.avg_deal_value)} loading={loading} />
          <StatTile
            label="Total settled"
            value={formatCurrency(stats?.total_settled_value, { maximumFractionDigits: 0 })}
            loading={loading}
          />
        </div>

        {statuses.length > 0 && (
          <div className="flex flex-wrap gap-x-5 gap-y-2 border-t border-border-base pt-3">
            {statuses.map((key) => {
              const { label, Icon, color } = STATUS_META[key]
              return (
                <div key={key} className="flex items-center gap-1.5 text-xs">
                  <Icon aria-hidden="true" className={`h-3.5 w-3.5 ${color}`} />
                  <span className="text-ink-secondary">{label}</span>
                  <span className="font-mono font-semibold tabular-nums text-ink">{byStatus[key]}</span>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
