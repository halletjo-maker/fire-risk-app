// Client HTTP : toutes les requêtes passent par /api (relayé vers le backend par Vite).
const BASE = '/api'
const STORAGE_KEY = 'ab_user_email'

export const storedEmail = {
  get: () => { try { return localStorage.getItem(STORAGE_KEY) } catch { return null } },
  set: (v) => { try { localStorage.setItem(STORAGE_KEY, v) } catch { /* navigation privée */ } },
  clear: () => { try { localStorage.removeItem(STORAGE_KEY) } catch { /* idem */ } },
}

async function request(path, { method = 'GET', body, signal } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const email = storedEmail.get()
  if (email) headers['X-User-Email'] = email
  let res
  try {
    res = await fetch(BASE + path, { method, headers, signal, body: body ? JSON.stringify(body) : undefined })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new Error('Serveur injoignable. Le backend est-il lancé ?')
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? 'Données invalides' : data.detail
    throw new Error(detail || `Erreur ${res.status}`)
  }
  return data
}

export const api = {
  health: () => request('/health'),
  currentUser: () => request('/users/current'),
  login: (email) => request('/users/login', { method: 'POST', body: { email } }),
  logout: () => request('/users/logout', { method: 'POST' }),
  knownUsers: () => request('/users/known'),
  me: () => request('/users/me'),
  watchlists: () => request('/watchlists'),
  createWatchlist: (name, color) => request('/watchlists', { method: 'POST', body: { name, color } }),
  updateWatchlist: (id, patch) => request(`/watchlists/${id}`, { method: 'PATCH', body: patch }),
  deleteWatchlist: (id) => request(`/watchlists/${id}`, { method: 'DELETE' }),
  duplicateWatchlist: (id) => request(`/watchlists/${id}/duplicate`, { method: 'POST' }),
  watchlistItems: (id) => request(`/watchlists/${id}/items`),
  addItem: (id, productId, isin) => request(`/watchlists/${id}/items`, { method: 'POST', body: { product_id: productId, isin } }),
  removeItem: (id, itemId) => request(`/watchlists/${id}/items/${itemId}`, { method: 'DELETE' }),
  reorderItems: (id, ids) => request(`/watchlists/${id}/items/order`, { method: 'PUT', body: { ids } }),
  refreshWatchlist: (id) => request(`/watchlists/${id}/refresh`, { method: 'POST' }),
  itemAlerts: (itemId) => request(`/alerts/item/${itemId}`),
  saveItemAlerts: (itemId, alerts) => request(`/alerts/item/${itemId}`, { method: 'PUT', body: { alerts } }),
  alertHistory: (limit = 10) => request(`/alerts/history?limit=${limit}`),
  testMail: () => request('/alerts/test', { method: 'POST' }),
  checkAlerts: () => request('/alerts/check', { method: 'POST' }),
  search: (q, signal) => request(`/search?q=${encodeURIComponent(q)}`, { signal }),
  report: (id, isin) => {
    const p = new URLSearchParams({ id })
    if (isin) p.set('isin', isin)
    return request(`/report?${p}`)
  },
  decision: (id, isin) => {
    const p = new URLSearchParams({ id })
    if (isin) p.set('isin', isin)
    return request(`/decision?${p}`)
  },
  sentiment: (id, isin) => {
    const p = new URLSearchParams({ id })
    if (isin) p.set('isin', isin)
    return request(`/sentiment?${p}`)
  },
  technical: (id, isin) => {
    const p = new URLSearchParams({ id })
    if (isin) p.set('isin', isin)
    return request(`/technical?${p}`)
  },
  fundamentals: (id, isin) => {
    const p = new URLSearchParams({ id })
    if (isin) p.set('isin', isin)
    return request(`/fundamentals?${p}`)
  },
  analyze: (q, id, isin) => {
    const p = new URLSearchParams({ q })
    if (id) p.set('id', id)
    if (isin) p.set('isin', isin)
    return request(`/analyze?${p}`)
  },
}

// Les 8 couleurs proposées (identiques au backend).
export const WATCHLIST_COLORS = [
  '#00FF88', '#3B82F6', '#A855F7', '#F59E0B', '#EF4444', '#06B6D4', '#EC4899', '#94A3B8',
]
