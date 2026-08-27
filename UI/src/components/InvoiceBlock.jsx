import { CheckCircle2, Receipt } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card.jsx'
import { formatCurrency, formatNumber } from '../lib/utils.js'

/** Settlement record produced once both agents accept. */
export function InvoiceBlock({ invoice }) {
  if (!invoice) return null

  const succeeded = invoice.payment_status === 'succeeded'

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Receipt aria-hidden="true" className="h-4 w-4 text-ink-muted" />
          <CardTitle>Invoice</CardTitle>
        </div>
        {succeeded && (
          <span className="flex shrink-0 items-center gap-1.5 text-xs font-medium">
            <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5 text-[var(--status-good)]" />
            <span className="text-ink">Paid</span>
          </span>
        )}
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="rounded-lg border border-border-base bg-surface-sunken px-4 py-3">
          <div className="text-xs uppercase tracking-wide text-ink-muted">Total</div>
          <div className="mt-0.5 font-mono text-3xl font-semibold tabular-nums text-ink">
            {formatCurrency(invoice.total_amount)}
          </div>
          <div className="mt-1 text-xs text-ink-muted">
            {formatNumber(invoice.quantity)} × {formatCurrency(invoice.unit_price)} per unit
          </div>
        </div>

        <dl className="grid gap-2 text-sm">
          <Line label="Product" value={invoice.product_id} mono />
          <Line label="Payment intent" value={invoice.payment_intent_id} mono truncate />
          <Line label="Transaction" value={invoice.transaction_id} mono truncate />
        </dl>

        <p className="text-xs text-ink-muted">
          Settled through a mock Stripe PaymentIntent lifecycle — shaped like the real object model,
          but no funds move.
        </p>
      </CardContent>
    </Card>
  )
}

// min-w-0 is needed on both the grid item and the flex child: each defaults to
// min-width:auto, so either one alone still lets a long id push past the card.
function Line({ label, value, mono, truncate }) {
  if (!value) return null
  return (
    <div className="flex min-w-0 items-baseline justify-between gap-4 border-b border-border-base pb-2 last:border-0 last:pb-0">
      <dt className="shrink-0 text-ink-muted">{label}</dt>
      <dd
        className={`min-w-0 text-right text-ink ${mono ? 'font-mono text-xs tabular-nums' : ''} ${truncate ? 'truncate' : ''}`}
        title={value}
      >
        {value}
      </dd>
    </div>
  )
}
