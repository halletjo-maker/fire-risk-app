import { ChevronDown } from 'lucide-react'
import { ColorDot } from './ui'

// Sélecteur de watchlist affiché en haut de l'écran sur mobile.
export default function WatchlistSelector({ watchlists, selectedId, onSelect }) {
  const selected = watchlists.find((w) => w.id === selectedId)
  return (
    <label className="relative flex items-center gap-2 rounded-lg border border-line bg-panel px-3 py-2">
      <span className="sr-only">Watchlist active</span>
      <ColorDot color={selected?.color || '#30363D'} />
      <select
        className="w-full min-w-0 appearance-none truncate bg-transparent pr-6 text-sm focus:outline-none"
        value={selectedId ?? ''}
        onChange={(e) => onSelect(Number(e.target.value))}
        disabled={watchlists.length === 0}
      >
        {watchlists.length === 0 && <option value="">Aucune watchlist</option>}
        {watchlists.map((w) => (
          <option key={w.id} value={w.id} className="bg-panel">
            {w.name} ({w.item_count})
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 h-4 w-4 text-muted" />
    </label>
  )
}
