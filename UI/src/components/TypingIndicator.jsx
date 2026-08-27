export function TypingIndicator({ label = 'Agent is responding' }) {
  return (
    <div className="flex items-center gap-2 px-1 py-2" role="status" aria-live="polite">
      <span className="flex gap-1" aria-hidden="true">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-muted"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
      <span className="text-xs text-ink-muted">{label}…</span>
    </div>
  )
}
