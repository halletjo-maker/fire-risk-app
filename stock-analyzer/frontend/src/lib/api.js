// Client HTTP : toutes les requêtes passent par /api (servi par le backend, ou relayé par Vite en dev).
// La session est un cookie HttpOnly envoyé automatiquement par le navigateur.
const BASE = '/api'

// Session expirée ou révoquée : App revient à l'écran de connexion.
export const SESSION_EXPIRED = 'ab:session-expired'
const AUTH_PATHS = ['/users/login', '/users/register', '/users/current', '/users/password/forgot', '/users/password/reset']
const isAuthPath = (path) => AUTH_PATHS.includes(path) || path.startsWith('/public/') || path.startsWith('/users/invitation/') || path.startsWith('/users/password/reset/')

// Mode démo (VITE_DEMO=1) : API simulée dans la page, sans serveur
export const DEMO = import.meta.env.VITE_DEMO === '1'

async function request(path, { method = 'GET', body, signal } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (DEMO) {
    const { mockRequest } = await import('../demo/mockApi.js')
    return mockRequest(path, { method, body, headers })
  }
  let res
  try {
    res = await fetch(BASE + path, {
      method, headers, signal, credentials: 'same-origin', body: body ? JSON.stringify(body) : undefined,
    })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new Error('Serveur injoignable. Le backend est-il lancé ?')
  }
  const data = await res.json().catch(() => ({}))
  if (res.status === 401 && !isAuthPath(path)) {
    window.dispatchEvent(new Event(SESSION_EXPIRED))
  }
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? 'Données invalides' : data.detail
    throw new Error(detail || `Erreur ${res.status}`)
  }
  return data
}

export const api = {
  health: () => request('/health'),
  currentUser: () => request('/users/current'),
  login: (email, password) => request('/users/login', { method: 'POST', body: { email, password } }),
  register: (email, password, invitation) => request('/users/register', { method: 'POST', body: { email, password, invitation } }),
  forgotPassword: (email) => request('/users/password/forgot', { method: 'POST', body: { email, app_url: window.location.origin } }),
  resetInfo: (token) => request(`/users/password/reset/${encodeURIComponent(token)}`),
  resetPassword: (token, password) => request('/users/password/reset', { method: 'POST', body: { token, password } }),
  invitationInfo: (token) => request(`/users/invitation/${encodeURIComponent(token)}`),
  members: () => request('/users/members'),
  adminVersion: () => request('/admin/version'),
  domainStatus: () => request('/admin/domain'),
  setDomain: (domain) => request('/admin/domain', { method: 'POST', body: { domain } }),
  mailSettings: () => request('/admin/mail'),
  saveMailSettings: (body) => request('/admin/mail', { method: 'PUT', body }),
  backupStatus: () => request('/admin/backup'),
  setBackupPassphrase: (passphrase) => request('/admin/backup', { method: 'PUT', body: { passphrase } }),
  sendBackup: () => request('/admin/backup/send', { method: 'POST' }),
  setPreferences: (body) => request('/users/me/preferences', { method: 'PUT', body }),
  sendMonthlyReport: (period) => request('/portfolios/report/send', { method: 'POST', body: { period } }),
  adminUpdate: () => request('/admin/update', { method: 'POST' }),
  invite: (email) => request('/users/invitations', { method: 'POST', body: { email, app_url: window.location.origin } }),
  cancelInvitation: (id) => request(`/users/invitations/${id}`, { method: 'DELETE' }),
  removeMember: (id) => request(`/users/members/${id}`, { method: 'DELETE' }),
  logout: () => request('/users/logout', { method: 'POST' }),
  changePassword: (current, next) => request('/users/password', { method: 'POST', body: { current_password: current, new_password: next } }),
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
  portfolios: () => request('/portfolios'),
  portfolio: (id) => request(`/portfolios/${id}`),
  createPortfolio: (body) => request('/portfolios', { method: 'POST', body }),
  deletePortfolio: (id) => request(`/portfolios/${id}`, { method: 'DELETE' }),
  setPortfolioPublic: (id, isPublic) => request(`/portfolios/${id}/public`, { method: 'POST', body: { public: isPublic } }),
  publicPortfolio: () => request('/public/portfolio'),
  requestAccess: (body) => request('/public/access-request', { method: 'POST', body }),
  accessRequests: () => request('/users/access-requests'),
  acceptAccessRequest: (id) => request(`/users/access-requests/${id}/accept`, { method: 'POST', body: { app_url: window.location.origin } }),
  declineAccessRequest: (id) => request(`/users/access-requests/${id}`, { method: 'DELETE' }),
  createPresetWatchlist: (key) => request(`/watchlists/presets/${key}`, { method: 'POST' }),
  refreshWatchlist: (id) => request(`/watchlists/${id}/refresh`, { method: 'POST' }),
  watchlistSuggestions: (id) => request(`/watchlists/${id}/suggestions`),
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
