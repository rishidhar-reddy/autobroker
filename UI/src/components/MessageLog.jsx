import { useEffect, useRef } from 'react'
import { Bot, ShoppingCart, Store } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card.jsx'
import { TypingIndicator } from './TypingIndicator.jsx'
import { cn, formatCurrency, formatNumber } from '../lib/utils.js'

const AGENTS = {
  BuyerAgent:  { name: 'Buyer',  Icon: ShoppingCart, side: 'left' },
  VendorAgent: { name: 'Vendor', Icon: Store,        side: 'right' },
}

// The structured tag the agents must emit. Stripped from the bubble text and
// rendered as its own chip, so the prose stays readable and the machine-
// readable part stays visible rather than hidden.
const OFFER_TAG = /\[OFFER price=([0-9.]+) quantity=(\d+) action=(ACCEPT|COUNTER|REJECT)\]/

const ACTION_STYLE = {
  ACCEPT:  'text-[var(--status-good)]',
  COUNTER: 'text-ink-secondary',
  REJECT:  'text-[var(--status-critical)]',
}

export function MessageLog({ messages, polling }) {
  const scrollRef = useRef(null)

  useEffect(() => {
    // Scroll the container itself rather than calling scrollIntoView on a
    // sentinel: scrollIntoView can also scroll the page, and a smooth scroll
    // that has not finished leaves the newest offer clipped at the edge.
    // Deferred a frame so the new message has been laid out and scrollHeight
    // reflects it.
    const frame = requestAnimationFrame(() => {
      const el = scrollRef.current
      if (el) el.scrollTop = el.scrollHeight
    })
    return () => cancelAnimationFrame(frame)
  }, [messages?.length, polling])

  const hasMessages = messages && messages.length > 0

  return (
    <Card className="flex min-h-0 flex-col">
      <CardHeader>
        <div>
          <CardTitle>Negotiation transcript</CardTitle>
          <p className="mt-0.5 text-xs text-ink-muted">
            Every turn must end in a structured offer tag.
          </p>
        </div>
        {hasMessages && (
          <span className="shrink-0 font-mono text-xs tabular-nums text-ink-muted">
            {messages.length} messages
          </span>
        )}
      </CardHeader>

      <CardContent className="min-h-0 flex-1">
        <div ref={scrollRef} className="max-h-[32rem] space-y-3 overflow-y-auto pr-1 pb-2">
          {!hasMessages && !polling && <EmptyState />}
          {messages?.map((message, index) => (
            <MessageBubble key={`${message.timestamp}-${index}`} message={message} />
          ))}
          {polling && <TypingIndicator />}
        </div>
      </CardContent>
    </Card>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-center">
      <Bot aria-hidden="true" className="h-7 w-7 text-ink-muted" />
      <p className="text-sm text-ink-secondary">No negotiation yet</p>
      <p className="max-w-xs text-xs text-ink-muted">
        Pick a product and start a run — the two agents will trade offers until one accepts or the
        turn limit is reached.
      </p>
    </div>
  )
}

function MessageBubble({ message }) {
  const agent = AGENTS[message.sender] ?? { name: message.sender, Icon: Bot, side: 'left' }
  const { Icon, name, side } = agent
  const isRight = side === 'right'

  const match = message.text?.match(OFFER_TAG)
  const prose = match ? message.text.replace(OFFER_TAG, '').trim() : message.text
  const action = match?.[3]

  return (
    <div className={cn('flex animate-fade-rise gap-2.5', isRight && 'flex-row-reverse')}>
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border-base bg-surface-sunken">
        <Icon aria-hidden="true" className="h-3.5 w-3.5 text-ink-secondary" />
      </div>

      <div className={cn('flex min-w-0 max-w-[80%] flex-col gap-1', isRight && 'items-end')}>
        <span className="text-xs font-medium text-ink-muted">{name}</span>

        <div
          className={cn(
            'rounded-xl border px-3 py-2 text-sm',
            isRight
              ? 'rounded-tr-sm border-border-base bg-surface-sunken text-ink'
              : 'rounded-tl-sm border-transparent bg-accent-soft text-ink',
          )}
        >
          {prose}
        </div>

        {match && (
          <div className="flex flex-wrap items-center gap-2 font-mono text-xs tabular-nums">
            <span className="text-ink-secondary">{formatCurrency(Number(match[1]))}</span>
            <span className="text-ink-muted">×{formatNumber(Number(match[2]))}</span>
            <span className={cn('font-semibold', ACTION_STYLE[action] ?? 'text-ink-muted')}>
              {action}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
