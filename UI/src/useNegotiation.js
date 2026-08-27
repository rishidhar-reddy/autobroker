import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchNegotiation, startNegotiation } from './api.js'
import { mockFetch, mockStart } from './mock.js'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const POLL_MS = 1000

export function useNegotiation({ onSettled } = {}) {
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [polling, setPolling] = useState(false)
  const intervalRef = useRef(null)
  const txIdRef = useRef(null)
  // Kept in a ref so `poll` does not need it as a dependency, which would
  // rebuild the callback on every render and restart the interval. Assigned in
  // an effect rather than during render, since writing a ref while rendering is
  // not safe under concurrent rendering.
  const onSettledRef = useRef(onSettled)
  useEffect(() => {
    onSettledRef.current = onSettled
  }, [onSettled])

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setPolling(false)
  }, [])

  const poll = useCallback(async () => {
    try {
      const data = USE_MOCK ? await mockFetch() : await fetchNegotiation(txIdRef.current)
      setState(data)
      if (data.status === 'FULFILLED' || data.status === 'TERMINATED') {
        stopPolling()
        onSettledRef.current?.()
      }
    } catch (err) {
      setError(err.message)
      stopPolling()
    }
  }, [stopPolling])

  const start = useCallback(
    async (productId) => {
      setError(null)
      setLoading(true)
      setState(null)
      stopPolling()
      try {
        const { transaction_id } = USE_MOCK ? await mockStart() : await startNegotiation(productId)
        txIdRef.current = transaction_id
        setPolling(true)
        await poll()
        intervalRef.current = setInterval(poll, POLL_MS)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    },
    [poll, stopPolling],
  )

  useEffect(() => stopPolling, [stopPolling])

  return { state, error, loading, polling, start }
}
