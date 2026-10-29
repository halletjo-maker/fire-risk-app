import { useState } from 'react'
import { Search, TrendingDown, TrendingUp } from 'lucide-react'
import { api } from '../lib/api'
import { ColorDot, Spinner } from './ui'
import BackendStatus from './BackendStatus'

function SearchBar({ onResult }) {
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!q.trim()) return
    setBusy(true)
    try {
      onResult(await api.analyze(q.trim()))
    } catch (err) {
      onResult({ query: q.trim(), status: 'error', message: err.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
      <input
        className="input py-3 pl-10 pr-28"
        placeholder="Nom, ticker, ISIN… ex. ServiceNow, NOW, US81762P1021"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        enterKeyHint="search"
      />
      <button type="submit" className="btn-primary absolute right-1.5 top-1/2 -translate-y-1/2 px-3 py-1.5 text-sm" disabled={busy}>
        {busy ? <Spinner className="h-4 w-4" /> : 'Analyser'}
      </button>
    </form>
  )
}

const TABS = [
  { id: 'achat', label: 'ACHAT', icon: TrendingUp, active: 'border-bull text-bull', },
  { id: 'vente', label: 'VENTE', icon: TrendingDown, active: 'border-bear text-bear' },
]

function DecisionTabs({ result }) {
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
        {result ? (
          <div className="space-y-2 text-sm">
            <p>
              Recherche : <span className="font-mono font-semibold">{result.query}</span>
            </p>
            <p className={result.status === 'error' ? 'text-bear' : 'text-warn'}>{result.message}</p>
          </div>
        ) : (
          <div className="py-6 text-center text-sm text-muted">
            <p className="text-base text-gray-100">
              {tab === 'achat' ? 'Analyse à l\'achat' : 'Analyse à la vente'}
            </p>
            <p className="mt-1">
              Lance une recherche pour obtenir le score global /10, la position vs MM100,
              les stop-loss proposés et le rapport justificatif.
            </p>
          </div>
        )}
        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          {[['Fondamental', '35 %'], ['Technique', '45 %'], ['Sentiment', '20 %']].map(([k, w]) => (
            <div key={k} className="rounded-lg bg-bg p-3">
              <p className="text-[11px] uppercase tracking-wide text-muted">{k}</p>
              <p className="mt-1 text-lg font-bold text-gray-500">–/10</p>
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

export default function MainArea({ watchlist }) {
  const [result, setResult] = useState(null)
  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 p-3 xs:p-4 md:p-6">
      <SearchBar onResult={setResult} />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2"><DecisionTabs result={result} /></div>
        <div className="space-y-4">
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
