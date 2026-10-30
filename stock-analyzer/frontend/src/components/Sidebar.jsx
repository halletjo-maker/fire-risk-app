import { useState } from 'react'
import { ChevronDown, LogOut, Plus, Settings, UserPlus, X } from 'lucide-react'
import { WATCHLIST_COLORS } from '../lib/api'
import { useWatchlists } from '../lib/watchlists'
import { fmtScore, scoreColor } from '../lib/format'
import { ColorDot, Logo, Spinner } from './ui'
import WatchlistSettings from './WatchlistSettings'
import { SIGNAL } from './WatchlistPanel'

function NewWatchlistForm({ onCreate, onDone }) {
  const [name, setName] = useState('')
  const [color, setColor] = useState(WATCHLIST_COLORS[0])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return setError('Donne un nom à la watchlist')
    setBusy(true)
    try {
      await onCreate(name.trim(), color)
      onDone()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="mx-3 mb-3 rounded-lg border border-line bg-bg p-3">
      <input
        className="input py-2 text-sm"
        placeholder="Ex. Tech US, Long terme…"
        maxLength={50}
        autoFocus
        value={name}
        onChange={(e) => { setName(e.target.value); setError(null) }}
      />
      <div className="mt-3 flex flex-wrap gap-2" role="radiogroup" aria-label="Couleur">
        {WATCHLIST_COLORS.map((c) => (
          <button
            key={c}
            type="button"
            role="radio"
            aria-checked={color === c}
            aria-label={`Couleur ${c}`}
            onClick={() => setColor(c)}
            className={`h-7 w-7 rounded-full border-2 transition ${color === c ? 'border-white' : 'border-transparent'}`}
            style={{ background: c }}
          />
        ))}
      </div>
      {error && <p className="mt-2 text-xs text-bear">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button type="submit" className="btn-primary flex-1 py-2 text-sm" disabled={busy}>Créer</button>
        <button type="button" className="btn-ghost" onClick={onDone}>Annuler</button>
      </div>
    </form>
  )
}

// Produits d'une watchlist, dépliés sous son nom (menu déroulant)
function WatchlistItems({ id, onOpen }) {
  const wl = useWatchlists()
  const state = wl.items[id]
  if (!state || (state.loading && !state.list.length)) return <div className="py-2 pl-9"><Spinner className="h-4 w-4" /></div>
  if (!state.list.length) return <p className="py-1.5 pl-9 text-xs text-muted">Aucun produit</p>
  return (
    <ul className="pb-1 pl-6">
      {state.list.map((i) => (
        <li key={i.id}>
          <button onClick={() => onOpen(i)} className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs text-muted hover:bg-panel2 hover:text-gray-100">
            <span className="w-4 text-center">{SIGNAL[i.last_signal]?.dot || '⚪'}</span>
            <span className="min-w-0 flex-1 truncate">{i.name}</span>
            <span className={`shrink-0 font-semibold ${scoreColor(i.last_score)}`}>{i.last_score != null ? fmtScore(i.last_score) : '–'}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}

export default function Sidebar({ user, onLogout, onProfile, onInvite, onClose, onNavigate }) {
  const wl = useWatchlists()
  const { watchlists, loading, error, selectedId } = wl
  const [creating, setCreating] = useState(false)
  const [expanded, setExpanded] = useState(() => new Set(selectedId ? [selectedId] : []))
  const [settingsFor, setSettingsFor] = useState(null)
  const onCreate = wl.create

  const toggle = (id) => {
    setExpanded((s) => {
      const n = new Set(s)
      if (n.has(id)) n.delete(id)
      else { n.add(id); if (!wl.items[id]) wl.loadItems(id) }
      return n
    })
  }
  const select = (id) => {
    wl.select(id)
    setExpanded((s) => new Set(s).add(id))
    onNavigate?.()
  }
  const openItem = (item) => { wl.analyze(item); onNavigate?.() }

  return (
    <div className="flex h-full w-full flex-col">
      <div className="flex items-center justify-between px-4 py-4">
        <Logo />
        {onClose && (
          <button className="btn-ghost p-2" onClick={onClose} aria-label="Fermer le menu">
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      <div className="flex items-center justify-between px-4 pb-2 pt-2">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">Mes watchlists</h2>
        <button
          className="btn-ghost p-1.5"
          onClick={() => setCreating((v) => !v)}
          aria-label="Nouvelle watchlist"
          title="Nouvelle watchlist"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {creating && <NewWatchlistForm onCreate={onCreate} onDone={() => setCreating(false)} />}

      <nav className="flex-1 overflow-y-auto px-2">
        {loading && <div className="flex justify-center py-6"><Spinner className="h-5 w-5" /></div>}
        {error && <p className="px-2 text-sm text-bear">{error}</p>}
        {!loading && !error && watchlists.length === 0 && !creating && (
          <div className="mx-2 rounded-lg border border-dashed border-line p-4 text-center text-sm text-muted">
            Aucune watchlist pour l'instant.
            <button className="mt-3 w-full text-bull hover:underline" onClick={() => setCreating(true)}>
              + Créer ma première watchlist
            </button>
          </div>
        )}
        <ul className="space-y-0.5">
          {watchlists.map((w) => {
            const open = expanded.has(w.id)
            return (
              <li key={w.id}>
                <div className={`group flex items-center rounded-lg transition ${w.id === selectedId ? 'bg-panel2 text-gray-100' : 'text-muted hover:bg-panel2/60 hover:text-gray-100'}`}>
                  <button className="p-2 pl-2.5" onClick={() => toggle(w.id)} aria-expanded={open} aria-label={`${open ? 'Replier' : 'Déplier'} ${w.name}`}>
                    <ChevronDown className={`h-3.5 w-3.5 transition ${open ? '' : '-rotate-90'}`} />
                  </button>
                  <button onClick={() => select(w.id)} className="flex min-w-0 flex-1 items-center gap-2.5 py-2.5 pr-1 text-left text-sm">
                    <ColorDot color={w.color} />
                    <span className="flex-1 truncate">{w.name}</span>
                    <span className="rounded bg-bg px-1.5 py-0.5 text-xs text-muted">{w.item_count}</span>
                  </button>
                  <button className="p-2 text-muted opacity-100 hover:text-gray-100 md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100"
                    onClick={() => setSettingsFor(w)} aria-label={`Paramètres de ${w.name}`} title="Paramètres">
                    <Settings className="h-3.5 w-3.5" />
                  </button>
                </div>
                {open && <WatchlistItems id={w.id} onOpen={openItem} />}
              </li>
            )
          })}
        </ul>
      </nav>

      {/* Profil : mail actif + changement d'utilisateur */}
      <div className="border-t border-line p-3">
        {user.is_admin && (
          <button className="btn-ghost mb-2 w-full justify-center border border-line" onClick={onInvite}>
            <UserPlus className="h-4 w-4" /> Inviter un ami
          </button>
        )}
        <button
          onClick={onProfile}
          className="flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left transition hover:bg-panel2"
          title="Voir mon profil"
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-bull/15 font-semibold text-bull">
            {user.email[0].toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="text-xs text-muted">Connecté en tant que</p>
            <p className="truncate text-sm" title={user.email}>{user.email}</p>
          </div>
        </button>
        <button className="btn-ghost mt-2 w-full justify-center" onClick={onLogout}>
          <LogOut className="h-4 w-4" /> Se déconnecter
        </button>
      </div>
      {settingsFor && <WatchlistSettings watchlist={watchlists.find((w) => w.id === settingsFor.id) || settingsFor} onClose={() => setSettingsFor(null)} />}
    </div>
  )
}
