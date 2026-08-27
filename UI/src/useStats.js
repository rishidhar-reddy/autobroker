import { useCallback, useEffect, useState } from 'react'
import { fetchStats } from './api.js'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export function useStats() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  // Manual refresh, called when a negotiation reaches a terminal state.
  const refresh = useCallback(async () => {
    if (USE_MOCK) return
    try {
      setStats(await fetchStats())
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    if (USE_MOCK) return undefined
    // Guarded so a response arriving after unmount does not set state.
    let cancelled = false
    fetchStats()
      .then((data) => {
        if (!cancelled) setStats(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return { stats, error, refresh }
}
