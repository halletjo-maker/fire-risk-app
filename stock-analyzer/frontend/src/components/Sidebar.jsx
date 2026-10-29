import { useState } from 'react'
import { LogOut, Plus, X } from 'lucide-react'
import { WATCHLIST_COLORS } from '../lib/api'
import { ColorDot, Logo, Spinner } from './ui'

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

export default function Sidebar({ user, watchlists, loading, error, selectedId, onSelect, onCreate, onLogout, onClose }) {
  const [creating, setCreating] = useState(false)

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
        <ul className="space-y-1">
          {watchlists.map((w) => (
            <li key={w.id}>
              <button
                onClick={() => onSelect(w.id)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition
                  ${w.id === selectedId ? 'bg-panel2 text-gray-100' : 'text-muted hover:bg-panel2/60 hover:text-gray-100'}`}
              >
                <ColorDot color={w.color} />
                <span className="flex-1 truncate">{w.name}</span>
                <span className="rounded bg-bg px-1.5 py-0.5 text-xs text-muted">{w.item_count}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Profil : mail actif + changement d'utilisateur */}
      <div className="border-t border-line p-3">
        <div className="flex items-center gap-3 px-2 py-1">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-bull/15 font-semibold text-bull">
            {user.email[0].toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="text-xs text-muted">Connecté en tant que</p>
            <p className="truncate text-sm" title={user.email}>{user.email}</p>
          </div>
        </div>
        <button className="btn-ghost mt-2 w-full justify-center" onClick={onLogout}>
          <LogOut className="h-4 w-4" /> Changer d'utilisateur
        </button>
      </div>
    </div>
  )
}
