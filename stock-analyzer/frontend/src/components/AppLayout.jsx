import { useState } from 'react'
import { WatchlistProvider } from '../lib/watchlists'
import Sidebar from './Sidebar'
import MobileHeader from './MobileHeader'
import MainArea from './MainArea'
import ProfileModal from './ProfileModal'
import InviteModal from './InviteModal'
import { NewPortfolioModal, PortfolioModal } from './PortfolioModals'

export default function AppLayout({ user, onLogout }) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [inviteOpen, setInviteOpen] = useState(false)
  const [portfolioId, setPortfolioId] = useState(null)
  const [newPortfolio, setNewPortfolio] = useState(false)
  const sidebarProps = {
    user,
    onLogout,
    onProfile: () => { setDrawerOpen(false); setProfileOpen(true) },
    onInvite: () => { setDrawerOpen(false); setInviteOpen(true) },
    onPortfolio: (id) => { setDrawerOpen(false); setPortfolioId(id) },
    onNewPortfolio: () => { setDrawerOpen(false); setNewPortfolio(true) },
    onNavigate: () => setDrawerOpen(false),
  }

  return (
    <WatchlistProvider email={user.email}>
      <div className="flex h-full">
        {/* PC : sidebar fixe */}
        <aside className="hidden w-72 shrink-0 border-r border-line bg-panel md:flex">
          <Sidebar {...sidebarProps} />
        </aside>

        {/* Mobile : tiroir ouvert par le menu hamburger */}
        {drawerOpen && (
          <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Menu">
            <div className="absolute inset-0 bg-black/60" onClick={() => setDrawerOpen(false)} />
            <aside className="absolute inset-y-0 left-0 flex w-[85%] max-w-xs border-r border-line bg-panel">
              <Sidebar {...sidebarProps} onClose={() => setDrawerOpen(false)} />
            </aside>
          </div>
        )}

        {profileOpen && <ProfileModal onClose={() => setProfileOpen(false)} onLogout={onLogout} />}
        {inviteOpen && <InviteModal onClose={() => setInviteOpen(false)} />}
        {newPortfolio && <NewPortfolioModal onClose={() => setNewPortfolio(false)} onCreated={(id) => { setNewPortfolio(false); setPortfolioId(id) }} />}
        {portfolioId && <PortfolioModal id={portfolioId} onClose={() => setPortfolioId(null)} />}

        <div className="flex min-w-0 flex-1 flex-col">
          <MobileHeader onMenu={() => setDrawerOpen(true)} />
          <main className="flex-1 overflow-y-auto">
            <MainArea />
          </main>
        </div>
      </div>
    </WatchlistProvider>
  )
}
