import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import Sidebar from './Sidebar'
import MobileHeader from './MobileHeader'
import MainArea from './MainArea'
import ProfileModal from './ProfileModal'

const selKey = (email) => `ab_selected_watchlist:${email}`

export default function AppLayout({ user, onLogout }) {
  const [watchlists, setWatchlists] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(() => {
    try { return Number(localStorage.getItem(selKey(user.email))) || null } catch { return null }
  })
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)

  const load = useCallback(async () => {
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

  useEffect(() => { load() }, [load])

  // Si la watchlist mémorisée n'existe plus, on prend la première.
  useEffect(() => {
    if (loading) return
    if (!watchlists.some((w) => w.id === selectedId)) setSelectedId(watchlists[0]?.id ?? null)
  }, [watchlists, selectedId, loading])

  useEffect(() => {
    try {
      if (selectedId) localStorage.setItem(selKey(user.email), String(selectedId))
    } catch { /* ignore */ }
  }, [selectedId, user.email])

  const select = (id) => { setSelectedId(id); setDrawerOpen(false) }

  const create = async (name, color) => {
    const { watchlist } = await api.createWatchlist(name, color)
    setWatchlists((list) => [...list, watchlist])
    setSelectedId(watchlist.id)
  }

  const selected = watchlists.find((w) => w.id === selectedId) || null
  const sidebarProps = { user, watchlists, loading, error, selectedId, onSelect: select, onCreate: create, onLogout,
    onProfile: () => { setDrawerOpen(false); setProfileOpen(true) } }

  return (
    <div className="flex h-full">
      {/* PC : sidebar fixe */}
      <aside className="hidden w-72 shrink-0 border-r border-line bg-panel md:flex">
        <Sidebar {...sidebarProps} />
      </aside>

      {/* Mobile : tiroir ouvert par le menu hamburger */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/60" onClick={() => setDrawerOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-[85%] max-w-xs border-r border-line bg-panel">
            <Sidebar {...sidebarProps} onClose={() => setDrawerOpen(false)} />
          </aside>
        </div>
      )}

      {profileOpen && <ProfileModal onClose={() => setProfileOpen(false)} onLogout={onLogout} />}

      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader
          watchlists={watchlists}
          selectedId={selectedId}
          onSelect={select}
          onMenu={() => setDrawerOpen(true)}
        />
        <main className="flex-1 overflow-y-auto">
          <MainArea watchlist={selected} />
        </main>
      </div>
    </div>
  )
}
