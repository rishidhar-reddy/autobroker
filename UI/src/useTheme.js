import { useCallback, useEffect, useState } from 'react'

const KEY = 'autobroker-theme'

/**
 * Theme preference: 'light', 'dark', or null to follow the OS.
 * Reads and writes are wrapped because storage throws outright in some
 * contexts (private windows, blocked site data) rather than returning empty.
 */
function read() {
  try {
    const stored = localStorage.getItem(KEY)
    return stored === 'light' || stored === 'dark' ? stored : null
  } catch {
    return null
  }
}

export function useTheme() {
  const [theme, setTheme] = useState(read)

  useEffect(() => {
    const root = document.documentElement
    if (theme) root.setAttribute('data-theme', theme)
    else root.removeAttribute('data-theme')
    try {
      if (theme) localStorage.setItem(KEY, theme)
      else localStorage.removeItem(KEY)
    } catch {
      /* preference simply will not persist — the page still renders correctly */
    }
  }, [theme])

  const toggle = useCallback(() => {
    setTheme((current) => {
      if (current) return current === 'dark' ? 'light' : 'dark'
      const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
      return prefersDark ? 'light' : 'dark'
    })
  }, [])

  return { theme, toggle }
}
