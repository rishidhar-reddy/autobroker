import { useState } from 'react'
import { AlertCircle, Moon, Play, Sun } from 'lucide-react'
import { Button } from './components/ui/button.jsx'
import { InvoiceBlock } from './components/InvoiceBlock.jsx'
import { MessageLog } from './components/MessageLog.jsx'
import { ProductSelector } from './components/ProductSelector.jsx'
import { StatsPanel } from './components/StatsPanel.jsx'
import { StatusBadge } from './components/StatusBadge.jsx'
import { useNegotiation } from './useNegotiation.js'
import { useProducts } from './useProducts.js'
import { useStats } from './useStats.js'
import { useTheme } from './useTheme.js'

export default function App() {
  const { products, defaultId, error: productsError } = useProducts()
  const { stats, refresh: refreshStats } = useStats()
  // Refresh the aggregates as soon as a run reaches a terminal state, so the
  // panel reflects the run you just watched rather than lagging a run behind.
  const { state, error, loading, polling, start } = useNegotiation({ onSettled: refreshStats })
  const { theme, toggle } = useTheme()

  // Derived rather than synced into state with an effect: the selection is
  // simply "whatever the user picked, else the catalog default", so there is no
  // second source of truth to keep in step.
  const [chosenId, setChosenId] = useState(null)
  const productId = chosenId ?? defaultId

  const busy = loading || polling
  const problem = error ?? productsError

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b border-border-base bg-surface-raised">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold tracking-tight text-ink">
              Autonomous Negotiation Platform
            </h1>
            <p className="mt-0.5 truncate text-xs text-ink-muted">
              Two LLM agents negotiate a deal and settle payment, with no human in the loop.
            </p>
          </div>

          <Button
            variant="ghost"
            size="icon"
            onClick={toggle}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            title="Toggle theme"
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <Button size="lg" onClick={() => start(productId)} disabled={busy || !productId}>
            <Play aria-hidden="true" className="h-4 w-4" />
            {loading ? 'Starting…' : polling ? 'Negotiating…' : 'Start negotiation'}
          </Button>

          {state && <StatusBadge status={state.status} />}
          {state && (
            <span className="font-mono text-xs tabular-nums text-ink-muted">turn {state.turn}</span>
          )}
        </div>

        {problem && (
          <div
            role="alert"
            className="mb-5 flex items-start gap-2.5 rounded-xl border border-border-base bg-surface-raised px-4 py-3"
          >
            <AlertCircle
              aria-hidden="true"
              className="mt-0.5 h-4 w-4 shrink-0 text-[var(--status-critical)]"
            />
            <div className="min-w-0">
              <p className="text-sm font-medium text-ink">Something went wrong</p>
              <p className="mt-0.5 break-words text-xs text-ink-secondary">{problem}</p>
            </div>
          </div>
        )}

        {state?.status === 'TERMINATED' && (
          <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-border-base bg-surface-raised px-4 py-3">
            <AlertCircle
              aria-hidden="true"
              className="mt-0.5 h-4 w-4 shrink-0 text-[var(--status-critical)]"
            />
            <div>
              <p className="text-sm font-medium text-ink">No deal reached</p>
              <p className="mt-0.5 text-xs text-ink-secondary">
                The agents could not agree inside their price bounds before the turn limit, or one
                side breached a hard constraint.
              </p>
            </div>
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[22rem_minmax(0,1fr)] lg:items-start">
          <div className="space-y-5">
            <ProductSelector
              products={products}
              value={productId}
              onChange={setChosenId}
              disabled={busy}
            />
            {state?.status === 'FULFILLED' && <InvoiceBlock invoice={state.invoice} />}
          </div>

          <div className="space-y-5">
            <MessageLog messages={state?.messages} polling={polling} />
            <StatsPanel stats={stats} />
          </div>
        </div>
      </main>
    </div>
  )
}
