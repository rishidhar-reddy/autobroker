// Relative base by default → requests go same-origin and are forwarded to the
// backend by the Vite dev proxy (see vite.config.js). Set VITE_API_BASE to hit
// a backend directly (e.g. a deployed URL).
const BASE = import.meta.env.VITE_API_BASE ?? ''

// The backend guards mutating endpoints with X-API-Key when API_KEY is set.
// Left unset for the local demo, where the backend runs open.
const API_KEY = import.meta.env.VITE_API_KEY ?? ''

function headers(extra = {}) {
  return API_KEY ? { ...extra, 'X-API-Key': API_KEY } : extra
}

async function parseJSON(res, label) {
  const text = await res.text()
  if (!res.ok) {
    let detail = ''
    try {
      detail = JSON.parse(text).detail ?? ''
    } catch {
      /* non-JSON error body — fall back to the status code alone */
    }
    if (res.status === 401) throw new Error('Unauthorized — set VITE_API_KEY to match the backend')
    throw new Error(detail ? `${label} failed: ${detail}` : `${label} failed: ${res.status}`)
  }
  try {
    return JSON.parse(text)
  } catch {
    throw new Error(`${label}: server returned unexpected response (backend may be unreachable)`)
  }
}

export async function startNegotiation(productId) {
  const res = await fetch(`${BASE}/negotiations/start`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ product_id: productId ?? null }),
  })
  return parseJSON(res, 'start')
}

export async function fetchNegotiation(transactionId) {
  return parseJSON(await fetch(`${BASE}/negotiations/${transactionId}`), 'fetch')
}

export async function fetchConfig(productId) {
  const query = productId ? `?product_id=${encodeURIComponent(productId)}` : ''
  return parseJSON(await fetch(`${BASE}/config${query}`), 'config')
}

export async function fetchProducts() {
  return parseJSON(await fetch(`${BASE}/products`), 'products')
}

export async function fetchStats() {
  return parseJSON(await fetch(`${BASE}/stats`), 'stats')
}
