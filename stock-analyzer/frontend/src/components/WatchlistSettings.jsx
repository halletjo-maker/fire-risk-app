import { useState } from 'react'
import { Copy, Trash2 } from 'lucide-react'
import { WATCHLIST_COLORS } from '../lib/api'
import { useWatchlists } from '../lib/watchlists'
import Modal from './Modal'
import ConfirmDialog from './ConfirmDialog'

export default function WatchlistSettings({ watchlist, onClose }) {
  const wl = useWatchlists()
  const [name, setName] = useState(watchlist.name)
  const [color, setColor] = useState(watchlist.color)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      const patch = {}
      if (name.trim() !== watchlist.name) patch.name = name.trim()
      if (color !== watchlist.color) patch.color = color
      if (Object.keys(patch).length) await wl.update(watchlist.id, patch)
      onClose()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  const duplicate = async () => {
    setBusy(true)
    try { await wl.duplicate(watchlist.id); onClose() } catch (err) { setError(err.message); setBusy(false) }
  }

  if (confirmDelete) {
    const n = watchlist.item_count
    return (
      <ConfirmDialog
        title="Supprimer la watchlist"
        message={`Supprimer la watchlist ${watchlist.name} et ses ${n} produit${n > 1 ? 's' : ''} ?`}
        detail="Les alertes configurées sur ces produits seront aussi supprimées. Cette action est irréversible."
        confirmLabel="Supprimer"
        onConfirm={() => wl.remove(watchlist.id)}
        onClose={() => { setConfirmDelete(false); onClose() }}
      />
    )
  }

  return (
    <Modal title="Paramètres de la watchlist" onClose={onClose}>
      <form onSubmit={save} className="mt-4">
        <label htmlFor="wl-name" className="text-sm font-medium">Nom</label>
        <input id="wl-name" className="input mt-1.5" maxLength={50} value={name}
          onChange={(e) => { setName(e.target.value); setError(null) }} />
        <p className="mt-4 text-sm font-medium">Couleur</p>
        <div className="mt-2 flex flex-wrap gap-2" role="radiogroup" aria-label="Couleur">
          {WATCHLIST_COLORS.map((c) => (
            <button key={c} type="button" role="radio" aria-checked={color === c} aria-label={`Couleur ${c}`}
              onClick={() => setColor(c)}
              className={`h-8 w-8 rounded-full border-2 transition ${color === c ? 'border-white' : 'border-transparent'}`}
              style={{ background: c }} />
          ))}
        </div>
        {error && <p className="mt-3 text-sm text-bear">{error}</p>}
        <button type="submit" className="btn-primary mt-5 w-full" disabled={busy || !name.trim()}>Enregistrer</button>
      </form>
      <div className="mt-5 space-y-2 border-t border-line pt-4">
        <button className="btn-ghost w-full justify-center border border-line" onClick={duplicate} disabled={busy}>
          <Copy className="h-4 w-4" /> Dupliquer la watchlist
        </button>
        <button
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-bear/50 px-4 py-2.5 text-sm font-semibold text-bear transition hover:bg-bear/10"
          onClick={() => setConfirmDelete(true)}
          disabled={busy}
        >
          <Trash2 className="h-4 w-4" /> Supprimer la watchlist
        </button>
      </div>
    </Modal>
  )
}
