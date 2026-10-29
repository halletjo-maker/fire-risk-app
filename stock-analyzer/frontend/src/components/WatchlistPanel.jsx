import { useState } from 'react'
import { DragDropContext, Draggable, Droppable } from '@hello-pangea/dnd'
import { Bell, GripVertical, RefreshCw, Settings, X } from 'lucide-react'
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

function ItemRow({ item, index, onOpen, onRemove, onAlerts }) {
  const sig = SIGNAL[item.last_signal]
  return (
    <Draggable draggableId={String(item.id)} index={index}>
      {(provided, snapshot) => (
        <li
          ref={provided.innerRef}
          {...provided.draggableProps}
          className={`group flex items-center gap-1 rounded-lg ${snapshot.isDragging ? 'bg-panel2 shadow-2xl ring-1 ring-bull/40' : ''}`}
        >
          <span {...provided.dragHandleProps} className="cursor-grab touch-none p-1.5 text-muted active:cursor-grabbing" aria-label={`Déplacer ${item.name}`}>
            <GripVertical className="h-4 w-4" />
          </span>
          <button onClick={() => onOpen(item)} className="flex min-w-0 flex-1 items-center gap-2 py-2.5 text-left" title={`Analyser ${item.name}`}>
            <span className="w-5 shrink-0 text-center text-sm" title={sig?.label || 'Score en cours de calcul'} aria-label={sig?.label || 'Score en cours de calcul'}>
              {sig ? sig.dot : <Spinner className="h-3 w-3" />}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{item.name}</span>
              <span className="flex items-center gap-1.5 truncate text-xs text-muted">
                {item.symbol}
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
        </li>
      )}
    </Draggable>
  )
}

export default function WatchlistPanel() {
  const wl = useWatchlists()
  const watchlist = wl.watchlists.find((w) => w.id === wl.selectedId) || null
  const state = watchlist ? wl.items[watchlist.id] : null
  const list = state?.list || []
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

      {list.length > 0 && (
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
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span className="flex gap-3"><span>🟢 Achat</span><span>🟡 Neutre</span><span>🔴 Vente</span></span>
        {lastRefresh && <span>Mis à jour {since(lastRefresh)} · auto 15 min</span>}
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
