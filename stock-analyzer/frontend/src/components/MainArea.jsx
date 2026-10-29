import { useRef, useState } from 'react'
import { api } from '../lib/api'
import { changeColor, fmtPct } from '../lib/format'
import { ColorDot, Spinner } from './ui'
import BackendStatus from './BackendStatus'
import SearchBar from './SearchBar'
import ProductCard from './ProductCard'
import TypeBadge from './TypeBadge'
import FundamentalsCard from './FundamentalsCard'
import TechnicalCard from './TechnicalCard'
import SentimentCard from './SentimentCard'
import DecisionPanel from './DecisionPanel'
import ReportCard from './ReportCard'

function WatchlistPanel({ watchlist }) {
  return (
    <section className="card p-4">
      <div className="flex items-center gap-2">
        {watchlist && <ColorDot color={watchlist.color} />}
        <h2 className="font-semibold">{watchlist ? watchlist.name : 'Aucune watchlist sélectionnée'}</h2>
      </div>
      <p className="mt-3 rounded-lg border border-dashed border-line p-4 text-center text-sm text-muted">
        {watchlist
          ? 'Aucun produit. L\'ajout depuis la recherche arrive avec le Module 8.'
          : 'Crée une watchlist depuis le menu pour commencer.'}
      </p>
      <div className="mt-3 flex justify-center gap-4 text-xs text-muted">
        <span>🟢 Achat</span><span>🟡 Neutre</span><span>🔴 Vente</span>
      </div>
    </section>
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

export default function MainArea({ watchlist }) {
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

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 p-3 xs:p-4 md:p-6">
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
              onPick={(a) => { document.querySelector('main')?.scrollTo({ top: 0, behavior: 'smooth' }); analyze(a.symbol, { id: a.id }) }}
            />
          )}
          {result && <Alternatives items={result.alternatives} query={result.query} onPick={(c) => analyze(result.query, c)} />}
        </div>
        <div className="min-w-0 space-y-4">
          <WatchlistPanel watchlist={watchlist} />
          <BackendStatus />
        </div>
      </div>
      <p className="pb-4 text-center text-[11px] text-muted">
        Informations fournies à titre indicatif — ne constituent pas un conseil en investissement (MiFID II).
      </p>
    </div>
  )
}
