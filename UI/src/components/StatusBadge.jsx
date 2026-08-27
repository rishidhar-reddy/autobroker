import { CheckCircle2, CircleDashed, CreditCard, Handshake, XCircle } from 'lucide-react'
import { Badge } from './ui/badge.jsx'
import { cn } from '../lib/utils.js'

// Status colour is always paired with an icon and a text label, so the state is
// never carried by colour alone — which matters for colour-blind readers and in
// forced-colours mode, and because two of these steps sit below 3:1 on the
// light surface by design.
const STATUS = {
  NEGOTIATING:     { label: 'Negotiating',     Icon: CircleDashed, color: 'text-ink-secondary' },
  AGREEMENT:       { label: 'Agreement',       Icon: Handshake,    color: 'text-[var(--status-warning)]' },
  PAYMENT_PENDING: { label: 'Payment pending', Icon: CreditCard,   color: 'text-[var(--status-serious)]' },
  FULFILLED:       { label: 'Settled',         Icon: CheckCircle2, color: 'text-[var(--status-good)]' },
  TERMINATED:      { label: 'No deal',         Icon: XCircle,      color: 'text-[var(--status-critical)]' },
}

export function StatusBadge({ status, className }) {
  const meta = STATUS[status] ?? { label: status ?? 'Unknown', Icon: CircleDashed, color: 'text-ink-muted' }
  const { label, Icon, color } = meta
  return (
    <Badge className={className}>
      <Icon aria-hidden="true" className={cn('h-3.5 w-3.5', color)} />
      <span className="text-ink">{label}</span>
    </Badge>
  )
}

export const STATUS_META = STATUS
