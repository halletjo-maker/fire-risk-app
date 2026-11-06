import { useEffect, useRef, useState } from 'react'
import { Check, ListPlus, Plus } from 'lucide-react'
import { WATCHLIST_COLORS } from '../lib/api'
import { useWatchlists } from '../lib/watchlists'
import { ColorDot } from './ui'

export default function AddToWatchlist({ product }) {
  const wl = useWatchlists()
  const [open, setOpen] = useState(false)
  const [msg, setMsg] = useState(null)
  const [newName, setNewName] = useState('')
  const ref = useRef(null)

  useEffect(() => {
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])

  // Watchlists (déjà chargées) qui contiennent ce produit
  const inList = (id) => (wl.items[id]?.list || []).some((i) => i.product_id === product.id)

  const add = async (w) => {
    try {
      await wl.addItem(w.id, product)
      setMsg({ ok: true, text: `Ajouté à ${w.name}` })
      wl.select(w.id)
    } catch (e) {
      setMsg({ ok: false, text: e.message })
    }
    setOpen(false)
    setTimeout(() => setMsg(null), 3500)
  }

  const createAndAdd = async (e) => {
    e.preventDefault()
    if (!newName.trim()) return
    try {
      const w = await wl.create(newName.trim(), WATCHLIST_COLORS[wl.watchlists.length % WATCHLIST_COLORS.length])
      setNewName('')
      await add(w)
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button className="btn-ghost border border-line py-1.5" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <ListPlus className="h-4 w-4" /> <span className="hidden sm:inline">Ajouter à une watchlist</span><span className="sm:hidden">Watchlist</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full z-30 mt-1 w-64 rounded-xl border border-line bg-panel p-1.5 shadow-2xl" role="menu">
          {wl.watchlists.map((w) => {
            const already = inList(w.id)
            return (
              <button key={w.id} role="menuitem" disabled={already} onClick={() => add(w)}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-panel2 disabled:opacity-60">
                <ColorDot color={w.color} />
                <span className="flex-1 truncate">{w.name}</span>
                {already ? <Check className="h-4 w-4 text-bull" aria-label="Déjà présent" /> : <Plus className="h-4 w-4 text-muted" />}
              </button>
            )
          })}
          <form onSubmit={createAndAdd} className="mt-1 flex gap-1 border-t border-line pt-1.5">
            <input className="input py-1.5 text-sm" placeholder="Nouvelle watchlist…" maxLength={50}
              value={newName} onChange={(e) => setNewName(e.target.value)} aria-label="Nom de la nouvelle watchlist" />
            <button type="submit" className="btn-primary px-2.5 py-1.5" disabled={!newName.trim()} aria-label="Créer et ajouter">
              <Plus className="h-4 w-4" />
            </button>
          </form>
        </div>
      )}
      {msg && (
        <p className={`absolute right-0 top-full z-20 mt-1 whitespace-nowrap rounded-lg border px-2.5 py-1 text-xs ${msg.ok ? 'border-bull/40 bg-panel text-bull' : 'border-bear/40 bg-panel text-bear'}`} role="status">
          {msg.text}
        </p>
      )}
    </div>
  )
}
