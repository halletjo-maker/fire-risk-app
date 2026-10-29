import { useEffect, useRef, useState } from 'react'
import { api, DEMO } from '../lib/api'
import { changeColor, fmtPct } from '../lib/format'
import { Spinner } from './ui'
import { useWatchlists } from '../lib/watchlists'
import WatchlistPanel from './WatchlistPanel'
import BackendStatus from './BackendStatus'
import SearchBar from './SearchBar'
import ProductCard from './ProductCard'
import TypeBadge from './TypeBadge'
import FundamentalsCard from './FundamentalsCard'
import TechnicalCard from './TechnicalCard'
import SentimentCard from './SentimentCard'
import DecisionPanel from './DecisionPanel'
import ReportCard from './ReportCard'

function DemoBanner({ onPick }) {
  const data = window.__DEMO_DATA__ || { products: {} }
  const at = data.recorded_at
  const day = at ? new Date(at.slice(0, 10)).toLocaleDateString('fr-BE', { day: 'numeric', month: 'long' }) : ''
  const short = (n) => n.split(/,| - | \(|\bUCITS\b/)[0].replace(/\s+(SA|NV|N\.V\.|S\.A\.|PLC|Inc\.?|SE)$/i, '').trim()
  const items = Object.entries(data.products).map(([id, p]) => ({
    id, symbol: p.analyze.product.symbol, name: short(p.analyze.product.name), type: p.analyze.product.type_label,
  }))
  return (
    <details className="rounded-xl border border-warn/40 bg-warn/5 px-3 py-2 text-xs text-warn">
      <summary className="cursor-pointer select-none">
        <b>Démo</b> · données réelles du {day}, cours figés · <span className="underline">voir les {items.length} produits</span>
      </summary>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {items.map((i) => (
          <button key={i.id} onClick={() => onPick({ symbol: i.symbol || i.name, product_id: i.id })}
            className="rounded-full border border-line bg-panel px-2 py-1 text-[11px] text-gray-200 hover:border-bull/60">
            {i.name} <span className="text-muted">· {i.type}</span>
          </button>
        ))}
      </div>
    </details>
  )
}

function Alternatives({ items, query, onPick }) {
  if (!items?.length) return null
  return (
    <section className="card p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Autres résultats pour « {query} »</h3>
      <ul className="mt-2 divide-y divide-line">
        {items.map((c) => (
          <li key={c.id}>
            <button onClick={() => onPick(c)} className="flex w-full items-center gap-3 py-2 text-left hover:text-bull">
              <TypeBadge type={c.type} label={c.type_label} />
              <span className="min-w-0 flex-1 truncate text-sm">{c.name}</span>
              <span className="shrink-0 text-xs text-muted">{c.symbol || c.isin}</span>
              {c.change_pct != null && <span className={`shrink-0 text-xs ${changeColor(c.change_pct)}`}>{fmtPct(c.change_pct)}</span>}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function MainArea() {
  const wl = useWatchlists()
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const empty = { data: null, loading: false, error: null }
  const [fund, setFund] = useState(empty)
  const [tech, setTech] = useState(empty)
  const [senti, setSenti] = useState(empty)
  const [decision, setDecision] = useState(empty)
  const [report, setReport] = useState(empty)
  const latest = useRef(0)

  // Charge une analyse ; ignore la réponse si une recherche plus récente a été lancée
  const load = async (setter, call, pick, run) => {
    setter({ data: null, loading: true, error: null })
    try {
      const r = await call()
      if (latest.current === run) setter({ data: pick(r), loading: false, error: null })
    } catch (e) {
      if (latest.current === run) setter({ data: null, loading: false, error: e.message })
    }
  }

  const loadAll = async (p, run) => {
    setDecision({ data: null, loading: true, error: null })
    setReport({ data: null, loading: true, error: null })
    await Promise.allSettled([
      load(setFund, () => api.fundamentals(p.id, p.isin), (r) => r.fundamentals, run),
      load(setTech, () => api.technical(p.id, p.isin), (r) => r.technical, run),
      load(setSenti, () => api.sentiment(p.id, p.isin), (r) => r.sentiment, run),
    ])
    // les trois analyses sont en cache côté serveur : la décision est immédiate
    await load(setDecision, () => api.decision(p.id, p.isin), (r) => r.decision, run)
    await load(setReport, () => api.report(p.id, p.isin), (r) => r, run)
  }

  const analyze = async (query, candidate) => {
    const run = ++latest.current
    setBusy(true)
    setError(null)
    try {
      const r = await api.analyze(query, candidate?.id, candidate?.isin)
      if (latest.current !== run) return  // une recherche plus récente a été lancée
      if (r.status === 'ok') {
        setResult(r)
        loadAll(r.product, run)
      } else setError(r.message)
    } catch (e) {
      if (latest.current === run) setError(e.message)
    } finally {
      if (latest.current === run) setBusy(false)
    }
  }

  // Lien « Voir l'analyse complète » d'un mail d'alerte : /?analyse=yf:NOW
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const id = params.get('analyse')
    if (!id) return
    window.history.replaceState(null, '', window.location.pathname)
    analyze(id.replace(/^(yf|bo):/, '').split('/').filter(Boolean).pop() || id, { id })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Analyse demandée depuis une watchlist, la barre latérale ou une alternative
  useEffect(() => {
    const req = wl.analysisRequest
    if (!req) return
    document.querySelector('main')?.scrollTo({ top: 0, behavior: 'smooth' })
    analyze(req.query, { id: req.id, isin: req.isin })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wl.analysisRequest])

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 p-3 xs:p-4 md:p-6">
      {DEMO && <DemoBanner onPick={wl.analyze} />}
      <SearchBar onAnalyze={analyze} busy={busy} />
      {error && (
        <div className="card border-bear/40 p-4 text-sm text-bear" role="alert">{error}</div>
      )}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="min-w-0 space-y-4 lg:col-span-2">
          {busy && !result && (
            <div className="card flex items-center justify-center gap-3 p-8 text-sm text-muted">
              <Spinner className="h-5 w-5" /> Recherche du produit et des cours…
            </div>
          )}
          {result && (
            <div className={busy ? 'pointer-events-none opacity-60 transition' : 'transition'}>
              <ProductCard result={result} />
            </div>
          )}
          <DecisionPanel
            product={result?.product}
            decision={decision.data}
            loading={decision.loading}
            scores={{
              // undefined = en cours · null = non applicable / indisponible
              fundamental: fund.loading ? undefined : fund.data?.score ?? null,
              technical: tech.loading ? undefined : tech.data?.score ?? null,
              sentiment: senti.loading ? undefined : senti.data?.score ?? null,
            }}
          />
          {result && <TechnicalCard {...tech} />}
          {result && <FundamentalsCard {...fund} />}
          {result && <SentimentCard {...senti} />}
          {result && (
            <ReportCard
              {...report}
              onPick={(a) => wl.analyze({ symbol: a.symbol, product_id: a.id })}
            />
          )}
          {result && <Alternatives items={result.alternatives} query={result.query} onPick={(c) => analyze(result.query, c)} />}
        </div>
        {/* Sur mobile, sans analyse en cours, la watchlist passe en premier */}
        <div className={`min-w-0 space-y-4 ${result ? '' : 'order-first lg:order-none'}`}>
          <WatchlistPanel />
          <BackendStatus />
        </div>
      </div>
      <p className="pb-4 text-center text-[11px] text-muted">
        Informations fournies à titre indicatif — ne constituent pas un conseil en investissement (MiFID II).
      </p>
    </div>
  )
}
