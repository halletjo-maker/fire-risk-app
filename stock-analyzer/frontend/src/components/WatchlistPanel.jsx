import { useEffect, useMemo, useState } from 'react'
import { DragDropContext, Draggable, Droppable } from '@hello-pangea/dnd'
import { Bell, GripVertical, Info, RefreshCw, Search, Settings, X } from 'lucide-react'
import { useWatchlists } from '../lib/watchlists'
import { changeColor, fmtPct, fmtPrice, fmtScore, scoreColor } from '../lib/format'
import { ColorDot, Spinner } from './ui'
import ConfirmDialog from './ConfirmDialog'
import WatchlistSettings from './WatchlistSettings'
import AlertSettings from './AlertSettings'

export const SIGNAL = {
  ACHAT: { dot: '🟢', label: 'Signal achat' },
  VENTE: { dot: '🔴', label: 'Signal vente' },
  NEUTRE: { dot: '🟡', label: 'Neutre' },
}

function since(sqlDate) {
  if (!sqlDate) return null
  const d = new Date(sqlDate.replace(' ', 'T') + 'Z')
  const min = Math.round((Date.now() - d.getTime()) / 60000)
  if (min < 1) return "à l'instant"
  if (min < 60) return `il y a ${min} min`
  return d.toLocaleString('fr-BE', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

// Contenu d'une ligne (commun aux watchlists classiques et aux listes larges)
function RowBody({ item, onOpen, onRemove, onAlerts, handle }) {
  const sig = SIGNAL[item.last_signal]
  return (
    <>
      {handle}
      <button onClick={() => onOpen(item)} className="min-w-0 flex-1 py-2.5 text-left" title={`Analyser ${item.name}`}>
        <span className="flex items-center gap-2">
          <span className="w-5 shrink-0 text-center text-sm" title={sig?.label || 'Score en cours de calcul'} aria-label={sig?.label || 'Score en cours de calcul'}>
            {sig ? sig.dot : <Spinner className="h-3 w-3" />}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{item.name}</span>
            <span className="flex items-center gap-1.5 truncate text-xs text-muted">
              {item.symbol}{item.ipo_year && <span className="text-muted/80">· IPO {item.ipo_year}</span>}
            </span>
          </span>
          <span className="shrink-0 text-right">
            <span className="block text-sm">{fmtPrice(item.last_price)}</span>
            <span className={`block text-xs ${changeColor(item.last_change_pct)}`}>{fmtPct(item.last_change_pct)}</span>
          </span>
          <span className={`w-11 shrink-0 text-right text-sm font-bold ${scoreColor(item.last_score)}`}>
            {item.last_score != null ? fmtScore(item.last_score) : '–'}
            <span className="block text-[10px] font-normal text-muted">/10</span>
          </span>
        </span>
        {item.buy_price != null && (
          <span className="mt-1 block pl-7 text-[11px]" title={[item.buy_note, item.sell_note].filter(Boolean).join(' · ')}>
            <span className="whitespace-nowrap text-bull">Achat {item.buy_kind} {fmtPrice(item.buy_price)}</span>
            <span className="text-muted"> · </span>
            <span className="whitespace-nowrap text-warn">Vente {fmtPrice(item.sell_price)}</span>
          </span>
        )}
      </button>
      <button
        onClick={() => onAlerts(item)}
        className={`shrink-0 rounded-md p-1.5 transition hover:bg-panel2 ${item.alert_count > 0 ? 'text-warn' : 'text-muted'}`}
        aria-label={`Alertes mail pour ${item.name}${item.alert_count ? ` (${item.alert_count} active${item.alert_count > 1 ? 's' : ''})` : ''}`}
        title="Alertes mail"
      >
        <Bell className={`h-4 w-4 ${item.alert_count > 0 ? 'fill-warn' : ''}`} />
      </button>
      <button
        onClick={() => onRemove(item)}
        className="shrink-0 rounded-md p-1.5 text-muted transition hover:bg-bear/10 hover:text-bear md:opacity-0 md:focus:opacity-100 md:group-hover:opacity-100"
        aria-label={`Retirer ${item.name}`}
        title="Retirer de la watchlist"
      >
        <X className="h-4 w-4" />
      </button>
    </>
  )
}

function ItemRow({ item, index, ...actions }) {
  return (
    <Draggable draggableId={String(item.id)} index={index}>
      {(provided, snapshot) => (
        <li
          ref={provided.innerRef}
          {...provided.draggableProps}
          className={`group flex items-center gap-1 rounded-lg ${snapshot.isDragging ? 'bg-panel2 shadow-2xl ring-1 ring-bull/40' : ''}`}
        >
          <RowBody
            item={item}
            {...actions}
            handle={(
              <span {...provided.dragHandleProps} className="cursor-grab touch-none p-1.5 text-muted active:cursor-grabbing" aria-label={`Déplacer ${item.name}`}>
                <GripVertical className="h-4 w-4" />
              </span>
            )}
          />
        </li>
      )}
    </Draggable>
  )
}

// Liste large (ex. IPO 10 ans, 500 sociétés) : recherche, filtres, tri, affichage par tranches
const SORTS = {
  rank: { label: 'Capitalisation', fn: (a, b) => a.position - b.position },
  score: { label: 'Score', fn: (a, b) => (b.last_score ?? -1) - (a.last_score ?? -1) },
  change: { label: 'Variation du jour', fn: (a, b) => (b.last_change_pct ?? -999) - (a.last_change_pct ?? -999) },
  ipo: { label: 'IPO la plus récente', fn: (a, b) => (b.ipo_year ?? 0) - (a.ipo_year ?? 0) || a.position - b.position },
  name: { label: 'Nom', fn: (a, b) => a.name.localeCompare(b.name, 'fr') },
}
const PAGE = 50

function ScreenList({ list, actions }) {
  const [query, setQuery] = useState('')
  const [signal, setSignal] = useState('ALL')
  const [sort, setSort] = useState('score')
  const [shown, setShown] = useState(PAGE)

  const counts = useMemo(() => {
    const c = { ALL: list.length, ACHAT: 0, NEUTRE: 0, VENTE: 0 }
    list.forEach((i) => { if (c[i.last_signal] != null) c[i.last_signal] += 1 })
    return c
  }, [list])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return list
      .filter((i) => signal === 'ALL' || i.last_signal === signal)
      .filter((i) => !q || i.name.toLowerCase().includes(q) || i.symbol.toLowerCase().includes(q))
      .sort(SORTS[sort].fn)
  }, [list, query, signal, sort])

  useEffect(() => setShown(PAGE), [query, signal, sort])

  const chips = [['ALL', 'Tous'], ['ACHAT', '🟢 Achat'], ['NEUTRE', '🟡 Neutre'], ['VENTE', '🔴 Vente']]
  return (
    <>
      <div className="mt-3 space-y-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <input
            className="input pl-9"
            placeholder={`Filtrer les ${list.length} sociétés (nom ou ticker)`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Filtrer la liste"
          />
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filtrer par signal">
          {chips.map(([k, label]) => (
            <button
              key={k}
              onClick={() => setSignal(k)}
              aria-pressed={signal === k}
              className={`rounded-full border px-2.5 py-1 text-xs transition ${signal === k ? 'border-bull/60 bg-bull/10 text-gray-100' : 'border-line text-muted hover:text-gray-100'}`}
            >
              {label} <span className="text-muted">{counts[k]}</span>
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-xs text-muted">
          Trier par
          <select className="input w-auto py-1.5 text-xs" value={sort} onChange={(e) => setSort(e.target.value)}>
            {Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </label>
      </div>
      {filtered.length === 0 && <p className="mt-3 text-center text-sm text-muted">Aucune société ne correspond.</p>}
      <ul className="mt-2 divide-y divide-line">
        {filtered.slice(0, shown).map((item) => (
          <li key={item.id} className="group flex items-center gap-1 rounded-lg">
            <RowBody item={item} {...actions} />
          </li>
        ))}
      </ul>
      {filtered.length > shown && (
        <button className="btn-ghost mt-2 w-full justify-center border border-line" onClick={() => setShown((n) => n + PAGE)}>
          Afficher {Math.min(PAGE, filtered.length - shown)} de plus ({filtered.length - shown} restantes)
        </button>
      )}
    </>
  )
}

export default function WatchlistPanel() {
  const wl = useWatchlists()
  const watchlist = wl.watchlists.find((w) => w.id === wl.selectedId) || null
  const state = watchlist ? wl.items[watchlist.id] : null
  const list = state?.list || []
  const isScreen = watchlist?.kind?.startsWith('screen:')
  const [settings, setSettings] = useState(false)
  const [removing, setRemoving] = useState(null)
  const [alertsFor, setAlertsFor] = useState(null)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const onDragEnd = async ({ source, destination }) => {
    if (!destination || destination.index === source.index) return
    const next = [...list]
    const [moved] = next.splice(source.index, 1)
    next.splice(destination.index, 0, moved)
    try { await wl.reorder(watchlist.id, next) } catch (e) { setError(e.message) }
  }

  const refresh = async () => {
    setRefreshing(true)
    try { await wl.refreshNow(watchlist.id) } catch (e) { setError(e.message) }
    setTimeout(() => setRefreshing(false), 1500)
  }

  const lastRefresh = list.map((i) => i.last_refresh_at).filter(Boolean).sort().pop()

  return (
    <section className="card p-4" aria-label="Watchlist">
      <div className="flex items-center gap-2">
        {watchlist && <ColorDot color={watchlist.color} className="h-3 w-3" />}
        <h2 className="min-w-0 flex-1 truncate font-semibold">{watchlist ? watchlist.name : 'Aucune watchlist sélectionnée'}</h2>
        {watchlist && (
          <>
            <button className="btn-ghost p-1.5" onClick={refresh} aria-label="Rafraîchir maintenant" title="Rafraîchir maintenant" disabled={refreshing}>
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
            <button className="btn-ghost p-1.5" onClick={() => setSettings(true)} aria-label="Paramètres de la watchlist" title="Paramètres">
              <Settings className="h-4 w-4" />
            </button>
          </>
        )}
      </div>

      {!watchlist && (
        <p className="mt-3 rounded-lg border border-dashed border-line p-4 text-center text-sm text-muted">
          Crée une watchlist depuis le menu pour commencer.
        </p>
      )}
      {watchlist && state?.loading && !list.length && <div className="flex justify-center py-6"><Spinner /></div>}
      {watchlist && !state?.loading && !list.length && (
        <p className="mt-3 rounded-lg border border-dashed border-line p-4 text-center text-sm text-muted">
          Aucun produit. Recherche un produit puis touche « Ajouter à une watchlist ».
        </p>
      )}

      {isScreen && (
        <p className="mt-3 flex gap-2 rounded-lg bg-bg px-3 py-2 text-xs text-muted">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Les plus grosses sociétés introduites en Bourse aux USA depuis 10 ans (source Nasdaq). Mise à jour
            1×/jour après la clôture américaine, <b>score technique</b> uniquement : touche une société pour son
            analyse complète. Composition revue chaque semaine.
          </span>
        </p>
      )}
      {isScreen && list.length > 0 && (
        <ScreenList list={list} actions={{ onOpen: wl.analyze, onRemove: setRemoving, onAlerts: setAlertsFor }} />
      )}
      {!isScreen && list.length > 0 && (
        <DragDropContext onDragEnd={onDragEnd}>
          <Droppable droppableId={`wl-${watchlist.id}`}>
            {(provided) => (
              <ul ref={provided.innerRef} {...provided.droppableProps} className="mt-2 divide-y divide-line">
                {list.map((item, i) => (
                  <ItemRow key={item.id} item={item} index={i} onOpen={wl.analyze} onRemove={setRemoving} onAlerts={setAlertsFor} />
                ))}
                {provided.placeholder}
              </ul>
            )}
          </Droppable>
        </DragDropContext>
      )}

      {error && <p className="mt-2 text-xs text-bear">{error}</p>}
      {list.some((i) => i.buy_price != null) && (
        <details className="mt-3 rounded-lg bg-bg px-3 py-2 text-xs text-muted">
          <summary className="cursor-pointer select-none">Comment lire « Achat » et « Vente » ?</summary>
          <ul className="mt-2 space-y-1">
            <li><span className="text-bull">Achat ≤</span> : tendance haussière, achat sur repli vers la MM100 ou le support.</li>
            <li><span className="text-bull">Achat ≈</span> : le cours est déjà dans la zone d'achat.</li>
            <li><span className="text-bull">Achat ≥</span> : tendance baissière, attendre que le cours repasse au-dessus de la MM100.</li>
            <li><span className="text-warn">Vente</span> : objectif de prise de bénéfice (prochaine résistance, ou estimation selon la volatilité).</li>
            <li>Niveaux recalculés toutes les 15 min. Indicatifs : pas un conseil en investissement.</li>
          </ul>
        </details>
      )}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span className="flex gap-3"><span>🟢 Achat</span><span>🟡 Neutre</span><span>🔴 Vente</span></span>
        {lastRefresh && <span>Mis à jour {since(lastRefresh)} · {isScreen ? 'auto 1×/jour' : 'auto 15 min'}</span>}
      </div>

      {alertsFor && (
        <AlertSettings item={alertsFor} onClose={() => setAlertsFor(null)} onSaved={() => wl.loadItems(watchlist.id, { silent: true })} />
      )}
      {settings && watchlist && <WatchlistSettings watchlist={watchlist} onClose={() => setSettings(false)} />}
      {removing && (
        <ConfirmDialog
          title="Retirer le produit"
          message={`Retirer ${removing.name} de la watchlist ${watchlist.name} ?`}
          detail={`${removing.alert_count > 0 ? `Les ${removing.alert_count} alerte(s) configurée(s) sur ce produit seront supprimées. ` : ''}Le produit pourra être réajouté via la recherche.`}
          confirmLabel="Retirer"
          onConfirm={() => wl.removeItem(watchlist.id, removing.id)}
          onClose={() => setRemoving(null)}
        />
      )}
    </section>
  )
}
