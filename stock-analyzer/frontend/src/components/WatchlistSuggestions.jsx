import { useEffect, useRef, useState } from 'react'
import { ChevronRight, Lightbulb, RefreshCw } from 'lucide-react'
import { api } from '../lib/api'
import { useWatchlists } from '../lib/watchlists'
import { changeColor, fmtPct, fmtPrice, fmtScore, scoreColor } from '../lib/format'
import { Spinner } from './ui'
import TypeBadge from './TypeBadge'

const POLL_MS = 4000
const MAX_WAIT_MS = 3 * 60 * 1000

function Suggestion({ s, onPick }) {
  return (
    <li>
      <button
        onClick={() => onPick(s)}
        className="flex w-full items-center gap-3 rounded-lg border border-line bg-bg p-3 text-left transition hover:border-bull/60"
      >
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2">
            <TypeBadge type={s.type} />
            <span className="truncate text-sm font-medium">{s.name}</span>
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {s.symbol} · {fmtPrice(s.price, s.currency)}
            {s.change_pct != null && <span className={`ml-1 ${changeColor(s.change_pct)}`}>{fmtPct(s.change_pct)}</span>}
            {s.technical_score != null && <> · technique <span className={scoreColor(s.technical_score)}>{fmtScore(s.technical_score)}/10</span></>}
          </p>
          <p className="mt-1 text-xs text-gray-300">{s.reason}</p>
        </div>
        <ChevronRight className="h-4 w-4 shrink-0 text-muted" aria-label="Analyser" />
      </button>
    </li>
  )
}

export default function WatchlistSuggestions() {
  const wl = useWatchlists()
  const watchlist = wl.watchlists.find((w) => w.id === wl.selectedId) || null
  const list = (watchlist && wl.items[watchlist.id]?.list) || []
  // Recalcul quand la composition de la watchlist change
  const signature = list.map((i) => i.product_id).filter(Boolean).sort().join(',')
  const [state, setState] = useState({ status: 'idle' })
  const timer = useRef(null)

  const load = (id, startedAt = Date.now()) => {
    clearTimeout(timer.current)
    api.watchlistSuggestions(id)
      .then((r) => {
        if (r.status === 'pending') {
          if (Date.now() - startedAt > MAX_WAIT_MS) {
            setState({ status: 'ready', items: [], message: 'La recherche prend plus de temps que prévu. Réessaie dans quelques minutes.' })
          } else {
            setState({ status: 'pending' })
            timer.current = setTimeout(() => load(id, startedAt), POLL_MS)
          }
        } else {
          setState(r)
        }
      })
      .catch((e) => setState({ status: 'error', message: e.message }))
  }

  useEffect(() => {
    if (!watchlist) return undefined
    setState({ status: 'pending' })
    load(watchlist.id)
    return () => clearTimeout(timer.current)
  }, [watchlist?.id, signature])

  if (!watchlist) return null

  return (
    <section className="card p-4" aria-label="Suggestions d'achat">
      <div className="flex items-center gap-2">
        <Lightbulb className="h-4 w-4 text-warn" />
        <h2 className="min-w-0 flex-1 font-semibold">Suggestions d'achat</h2>
        {state.status !== 'pending' && list.length > 0 && (
          <button className="btn-ghost p-1.5" onClick={() => { setState({ status: 'pending' }); load(watchlist.id) }}
            aria-label="Actualiser les suggestions" title="Actualiser">
            <RefreshCw className="h-4 w-4" />
          </button>
        )}
      </div>
      <p className="mt-1 text-xs text-muted">Produits proches de ceux de « {watchlist.name} », en tendance favorable.</p>

      {state.status === 'pending' && (
        <p className="mt-3 flex items-center gap-2 text-sm text-muted">
          <Spinner className="h-4 w-4" /> Recherche de produits similaires… (jusqu'à 1 minute)
        </p>
      )}
      {state.status === 'error' && <p className="mt-3 text-sm text-bear">{state.message}</p>}
      {state.status === 'ready' && (
        <>
          {state.items?.length > 0 && (
            <ul className="mt-3 space-y-2">
              {state.items.map((s) => (
                <Suggestion key={s.symbol} s={s} onPick={(x) => wl.analyze({ symbol: x.symbol, product_id: x.id })} />
              ))}
            </ul>
          )}
          {state.message && <p className="mt-3 text-sm text-muted">{state.message}</p>}
          {state.items?.length > 0 && (
            <p className="mt-3 text-[11px] text-muted">
              Pistes à étudier : touche un produit pour voir son analyse complète avant toute décision. Pas un conseil en investissement.
            </p>
          )}
        </>
      )}
    </section>
  )
}
