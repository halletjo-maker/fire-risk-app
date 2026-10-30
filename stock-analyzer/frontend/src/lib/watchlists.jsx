// État partagé des watchlists (barre latérale, panneau, fiche produit, sélecteur mobile).
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'

const REFRESH_MS = 15 * 60 * 1000 // même rythme que le serveur
const Ctx = createContext(null)
export const useWatchlists = () => useContext(Ctx)

const selKey = (email) => `ab_selected_watchlist:${email}`

export function WatchlistProvider({ email, children }) {
  const [watchlists, setWatchlists] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [items, setItems] = useState({}) // { [id]: { list, loading, error, at } }
  const [selectedId, setSelectedId] = useState(() => {
    try { return Number(localStorage.getItem(selKey(email))) || null } catch { return null }
  })
  const [analysisRequest, setAnalysisRequest] = useState(null)
  const itemsRef = useRef(items)
  itemsRef.current = items

  const reload = useCallback(async () => {
    try {
      const { watchlists } = await api.watchlists()
      setWatchlists(watchlists)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadItems = useCallback(async (id, { silent = false } = {}) => {
    if (!id) return
    if (!silent) setItems((m) => ({ ...m, [id]: { ...(m[id] || { list: [] }), loading: true, error: null } }))
    try {
      const r = await api.watchlistItems(id)
      setItems((m) => ({ ...m, [id]: { list: r.items, loading: false, error: null, at: Date.now() } }))
      setWatchlists((wl) => wl.map((w) => (w.id === id ? { ...w, item_count: r.items.length } : w)))
    } catch (e) {
      setItems((m) => ({ ...m, [id]: { ...(m[id] || { list: [] }), loading: false, error: e.message } }))
    }
  }, [])

  useEffect(() => { reload() }, [reload])

  // Watchlist mémorisée qui n'existe plus → la première
  useEffect(() => {
    if (loading) return
    if (!watchlists.some((w) => w.id === selectedId)) setSelectedId(watchlists[0]?.id ?? null)
  }, [watchlists, selectedId, loading])

  useEffect(() => {
    try { if (selectedId) localStorage.setItem(selKey(email), String(selectedId)) } catch { /* ignore */ }
    if (selectedId && !itemsRef.current[selectedId]) loadItems(selectedId)
  }, [selectedId, email, loadItems])

  // Rafraîchissement automatique toutes les 15 minutes (et au retour sur l'app)
  useEffect(() => {
    const tick = () => Object.keys(itemsRef.current).forEach((id) => loadItems(Number(id), { silent: true }))
    const timer = setInterval(tick, REFRESH_MS)
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return
      const stale = Object.entries(itemsRef.current).some(([, v]) => Date.now() - (v.at || 0) > REFRESH_MS)
      if (stale) tick()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', onVisible) }
  }, [loadItems])

  // Après un ajout, le score est calculé côté serveur (souvent 10 à 40 s) :
  // on relit la liste toutes les 5 s jusqu'à ce que tous les produits soient notés (2 min max).
  const polling = useRef({})
  const pollSoon = useCallback((id) => {
    if (polling.current[id]) return
    polling.current[id] = true
    let tries = 0
    const tick = async () => {
      tries += 1
      await loadItems(id, { silent: true })
      const pending = (itemsRef.current[id]?.list || []).some((i) => !i.last_refresh_at)
      if (pending && tries < 24) setTimeout(tick, 5000)
      else polling.current[id] = false
    }
    setTimeout(tick, 5000)
  }, [loadItems])

  const actions = useMemo(() => ({
    select: setSelectedId,
    reload,
    loadItems,
    createIpo: async () => {
      const { watchlist } = await api.createIpoWatchlist()
      setWatchlists((l) => [...l, watchlist])
      setSelectedId(watchlist.id)
      await loadItems(watchlist.id)
      pollSoon(watchlist.id) // scores calculés en arrière-plan (≈ 1 min pour 500 sociétés)
      return watchlist
    },
    create: async (name, color) => {
      const { watchlist } = await api.createWatchlist(name, color)
      setWatchlists((l) => [...l, watchlist])
      setItems((m) => ({ ...m, [watchlist.id]: { list: [], loading: false, at: Date.now() } }))
      setSelectedId(watchlist.id)
      return watchlist
    },
    update: async (id, patch) => {
      const { watchlist } = await api.updateWatchlist(id, patch)
      setWatchlists((l) => l.map((w) => (w.id === id ? watchlist : w)))
    },
    remove: async (id) => {
      const r = await api.deleteWatchlist(id)
      setWatchlists((l) => l.filter((w) => w.id !== id))
      setItems((m) => { const n = { ...m }; delete n[id]; return n })
      return r.deleted
    },
    duplicate: async (id) => {
      const { watchlist } = await api.duplicateWatchlist(id)
      setWatchlists((l) => [...l, watchlist])
      setSelectedId(watchlist.id)
      loadItems(watchlist.id)
      return watchlist
    },
    addItem: async (id, product) => {
      const { item } = await api.addItem(id, product.id, product.isin)
      setItems((m) => ({ ...m, [id]: { list: [...(m[id]?.list || []), item], loading: false, at: Date.now() } }))
      setWatchlists((l) => l.map((w) => (w.id === id ? { ...w, item_count: w.item_count + 1 } : w)))
      pollSoon(id)
      return item
    },
    removeItem: async (id, itemId) => {
      const r = await api.removeItem(id, itemId)
      setItems((m) => ({ ...m, [id]: { ...m[id], list: (m[id]?.list || []).filter((i) => i.id !== itemId) } }))
      setWatchlists((l) => l.map((w) => (w.id === id ? { ...w, item_count: Math.max(0, w.item_count - 1) } : w)))
      return r.deleted
    },
    reorder: async (id, list) => {
      const previous = itemsRef.current[id]
      setItems((m) => ({ ...m, [id]: { ...m[id], list } })) // affichage immédiat
      try {
        await api.reorderItems(id, list.map((i) => i.id))
      } catch (e) {
        setItems((m) => ({ ...m, [id]: previous }))
        throw e
      }
    },
    refreshNow: async (id) => {
      await api.refreshWatchlist(id)
      pollSoon(id)
    },
    // Demande d'analyse d'un produit depuis n'importe quel écran (traitée par la zone principale)
    analyze: (item) => setAnalysisRequest({ query: item.symbol || item.name, id: item.product_id || item.id, isin: item.isin, at: Date.now() }),
  }), [reload, loadItems, pollSoon])

  const value = { watchlists, loading, error, items, selectedId, analysisRequest, ...actions }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
