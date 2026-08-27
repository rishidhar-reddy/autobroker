import { AlertTriangle, Package } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card.jsx'
import { Select } from './ui/select.jsx'
import { formatCurrency, formatNumber } from '../lib/utils.js'

/**
 * Choose which catalog product the agents negotiate over.
 *
 * The bargaining range is shown explicitly: if the buyer's ceiling sits below
 * the vendor's floor there is no price both sides can accept, and the run can
 * only ever terminate. Surfacing that before you press Start turns a confusing
 * "no deal" into an expected outcome.
 */
export function ProductSelector({ products, value, onChange, disabled }) {
  const selected = products.find((p) => p.product_id === value)

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Product</CardTitle>
          <p className="mt-0.5 text-xs text-ink-muted">What the two agents are trading.</p>
        </div>
        <Package aria-hidden="true" className="h-4 w-4 shrink-0 text-ink-muted" />
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="sr-only" htmlFor="product-select">
          Product to negotiate
        </label>
        <Select
          id="product-select"
          value={value ?? ''}
          disabled={disabled || products.length === 0}
          onChange={(event) => onChange(event.target.value)}
        >
          {products.length === 0 && <option value="">Loading…</option>}
          {products.map((product) => (
            <option key={product.product_id} value={product.product_id}>
              {product.name} — {product.vendor_company}
            </option>
          ))}
        </Select>

        {selected && (
          <div className="space-y-3">
            <p className="text-sm text-ink-secondary">{selected.description}</p>

            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <Row label="Vendor" value={selected.vendor_company} />
              <Row label="Buyer" value={selected.buyer_company} />
              <Row label="In stock" value={`${formatNumber(selected.stock_quantity)} ${selected.unit}`} />
              <Row label="Wants" value={`${formatNumber(selected.desired_quantity)} ${selected.unit}`} />
              <Row label="Vendor floor" value={formatCurrency(selected.vendor_floor_price)} mono />
              <Row label="Buyer ceiling" value={formatCurrency(selected.buyer_ceiling_price)} mono />
            </dl>

            {!selected.has_overlap && (
              <p className="flex items-start gap-2 rounded-lg border border-border-base bg-surface-sunken px-3 py-2 text-xs text-ink-secondary">
                <AlertTriangle
                  aria-hidden="true"
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--status-serious)]"
                />
                <span>
                  <strong className="text-ink">No overlap.</strong> The buyer&apos;s ceiling is below the
                  vendor&apos;s floor, so no price satisfies both — this run can only terminate.
                </span>
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function Row({ label, value, mono }) {
  return (
    <div className="flex flex-col">
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className={`text-ink ${mono ? 'font-mono tabular-nums' : ''}`}>{value}</dd>
    </div>
  )
}
