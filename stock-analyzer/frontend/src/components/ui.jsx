export function Spinner({ className = 'h-6 w-6' }) {
  return (
    <span
      className={`inline-block animate-spin rounded-full border-2 border-line border-t-bull ${className}`}
      role="status"
      aria-label="Chargement"
    />
  )
}

export function Logo({ compact = false }) {
  return (
    <div className="flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="h-8 w-8 shrink-0" aria-hidden="true">
        <rect width="32" height="32" rx="7" fill="#161B22" stroke="#30363D" />
        <path d="M5 22l7-7 5 4 10-10" fill="none" stroke="#00FF88" strokeWidth="3"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {!compact && <span className="font-bold tracking-tight">Analyse Boursière</span>}
    </div>
  )
}

export function ColorDot({ color, className = 'h-2.5 w-2.5' }) {
  return <span className={`inline-block shrink-0 rounded-full ${className}`} style={{ background: color }} />
}
