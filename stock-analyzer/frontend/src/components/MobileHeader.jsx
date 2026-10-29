import { Menu } from 'lucide-react'
import { Logo } from './ui'
import WatchlistSelector from './WatchlistSelector'

export default function MobileHeader({ watchlists, selectedId, onSelect, onMenu }) {
  return (
    <header className="sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-bg/95 px-3 py-2 backdrop-blur md:hidden">
      <button className="btn-ghost p-2" onClick={onMenu} aria-label="Ouvrir le menu">
        <Menu className="h-5 w-5" />
      </button>
      <Logo compact />
      <div className="min-w-0 flex-1">
        <WatchlistSelector watchlists={watchlists} selectedId={selectedId} onSelect={onSelect} />
      </div>
    </header>
  )
}
