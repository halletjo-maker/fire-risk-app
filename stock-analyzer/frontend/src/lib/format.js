// Mise en forme des nombres à la belge (« 1 234,56 € »).
const ISO = /^[A-Z]{3}$/

export function fmtPrice(value, currency) {
  if (value == null) return '—'
  const abs = Math.abs(value)
  const digits = abs >= 1000 ? 2 : abs >= 10 ? 2 : abs >= 1 ? 3 : 4
  const opts = { minimumFractionDigits: digits, maximumFractionDigits: digits }
  if (currency && ISO.test(currency)) {
    try {
      return new Intl.NumberFormat('fr-BE', { style: 'currency', currency, ...opts }).format(value)
    } catch { /* devise inconnue */ }
  }
  const n = new Intl.NumberFormat('fr-BE', opts).format(value)
  return currency ? `${n} ${currency}` : n
}

export function fmtPct(value, { sign = true } = {}) {
  if (value == null) return '—'
  const n = new Intl.NumberFormat('fr-BE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Math.abs(value))
  const s = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign ? s : ''}${n} %`
}

export function fmtNumber(value, digits = 2) {
  if (value == null) return '—'
  return new Intl.NumberFormat('fr-BE', { maximumFractionDigits: digits }).format(value)
}

export function fmtVolume(value) {
  if (!value) return '—'
  return new Intl.NumberFormat('fr-BE', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

export function fmtDateTime(iso) {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleString('fr-BE', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export const TYPE_STYLES = {
  ACTION: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  ETF: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
  TURBO: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  WARRANT: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
  CRYPTO: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
  INDICE: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  AUTRE: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
}

export const changeColor = (v) => (v > 0 ? 'text-bull' : v < 0 ? 'text-bear' : 'text-muted')

// Couleur d'un score /10 : vert ≥ 7,5 · orange ≥ 5 · rouge sinon
export const scoreColor = (s) => (s == null ? 'text-muted' : s >= 7.5 ? 'text-bull' : s >= 5 ? 'text-warn' : 'text-bear')
export const scoreBg = (s) => (s == null ? 'bg-line' : s >= 7.5 ? 'bg-bull' : s >= 5 ? 'bg-warn' : 'bg-bear')
export const fmtScore = (s) => (s == null ? '–' : new Intl.NumberFormat('fr-BE', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(s))
