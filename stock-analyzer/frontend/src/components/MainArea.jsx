import { useRef, useState } from 'react'
import { TrendingDown, TrendingUp } from 'lucide-react'
import { api } from '../lib/api'
import { changeColor, fmtPct, fmtScore, scoreColor } from '../lib/format'
import { ColorDot, Spinner } from './ui'
import BackendStatus from './BackendStatus'
import SearchBar from './SearchBar'
import ProductCard from './ProductCard'
import TypeBadge from './TypeBadge'
import FundamentalsCard from './FundamentalsCard'
import TechnicalCard from './TechnicalCard'
import SentimentCard from './SentimentCard'

const TABS = [
  { id: 'achat', label: 'ACHAT', icon: TrendingUp, active: 'border-bull text-bull', },
  { id: 'vente', label: 'VENTE', icon: TrendingDown, active: 'border-bear text-bear' },
]

function DecisionTabs({ product, scores = {} }) {
  const [tab, setTab] = useState('achat')
  return (
    <section className="card overflow-hidden">
      <div className="flex border-b border-line" role="tablist">
        {TABS.map(({ id, label, icon: Icon, active }) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`flex flex-1 items-center justify-center gap-2 border-b-2 py-3 text-sm font-semibold tracking-wide transition
              ${tab === id ? active + ' bg-panel2' : 'border-transparent text-muted hover:text-gray-100'}`}
          >
            <Icon className="h-4 w-4" /> {label}
          </button>
        ))}
      </div>
      <div className="p-4 sm:p-6" role="tabpanel">
        <div className="py-4 text-center text-sm text-muted">
          <p className="text-base text-gray-100">
            {tab === 'achat' ? "Analyse à l'achat" : 'Analyse à la vente'}
            {product && <span className="text-muted"> · {product.name}</span>}
          </p>
          <p className="mt-1">
            {product
              ? 'Scores technique et fondamental ci-dessous. Score global, stop-loss et rapport : Modules 6 et 7.'
              : 'Lance une recherche pour obtenir le score global /10, la position vs MM100, les stop-loss proposés et le rapport justificatif.'}
          </p>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          {[['Fondamental', '35 %', 'fundamental'], ['Technique', '45 %', 'technical'], ['Sentiment', '20 %', 'sentiment']].map(([k, w, key]) => (
            <div key={k} className="rounded-lg bg-bg p-3">
              <p className="text-[11px] uppercase tracking-wide text-muted">{k}</p>
              <p className={`mt-1 text-lg font-bold ${scores[key] != null ? scoreColor(scores[key]) : 'text-gray-500'}`}>{fmtScore(scores[key])}/10</p>
              <p className="text-[11px] text-muted">poids {w}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

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
  const [fund, setFund] = useState({ data: null, loading: false, error: null })
  const [tech, setTech] = useState({ data: null, loading: false, error: null })
  const [senti, setSenti] = useState({ data: null, loading: false, error: null })
  const latest = useRef(0)

  const loadFundamentals = async (product, run) => {
    setFund({ data: null, loading: true, error: null })
    try {
      const r = await api.fundamentals(product.id, product.isin)
      if (latest.current === run) setFund({ data: r.fundamentals, loading: false, error: null })
    } catch (e) {
      if (latest.current === run) setFund({ data: null, loading: false, error: e.message })
    }
  }

  const loadSentiment = async (product, run) => {
    setSenti({ data: null, loading: true, error: null })
    try {
      const r = await api.sentiment(product.id, product.isin)
      if (latest.current === run) setSenti({ data: r.sentiment, loading: false, error: null })
    } catch (e) {
      if (latest.current === run) setSenti({ data: null, loading: false, error: e.message })
    }
  }

  const loadTechnical = async (product, run) => {
    setTech({ data: null, loading: true, error: null })
    try {
      const r = await api.technical(product.id, product.isin)
      if (latest.current === run) setTech({ data: r.technical, loading: false, error: null })
    } catch (e) {
      if (latest.current === run) setTech({ data: null, loading: false, error: e.message })
    }
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
        loadFundamentals(r.product, run)
        loadTechnical(r.product, run)
        loadSentiment(r.product, run)
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
          <DecisionTabs product={result?.product} scores={{ fundamental: fund.data?.score, technical: tech.data?.score, sentiment: senti.data?.score }} />
          {result && <TechnicalCard {...tech} />}
          {result && <FundamentalsCard {...fund} />}
          {result && <SentimentCard {...senti} />}
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
