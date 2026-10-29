import { AlertTriangle } from 'lucide-react'
import { fmtScore, scoreBg, scoreColor } from '../lib/format'

export function ScoreRing({ score }) {
  const r = 26
  const c = 2 * Math.PI * r
  const filled = score == null ? 0 : (score / 10) * c
  return (
    <div className="relative h-16 w-16 shrink-0" aria-label={`Score ${fmtScore(score)} sur 10`}>
      <svg viewBox="0 0 64 64" className="h-16 w-16 -rotate-90">
        <circle cx="32" cy="32" r={r} fill="none" stroke="#30363D" strokeWidth="6" />
        <circle
          cx="32" cy="32" r={r} fill="none" strokeWidth="6" strokeLinecap="round"
          className={scoreColor(score).replace('text-', 'stroke-')}
          strokeDasharray={`${filled} ${c}`}
        />
      </svg>
      <span className={`absolute inset-0 flex items-center justify-center text-lg font-bold ${scoreColor(score)}`}>
        {fmtScore(score)}
      </span>
    </div>
  )
}

export function Criterion({ c }) {
  return (
    <li className="py-2.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm">{c.label}</span>
        <span className={`shrink-0 text-sm font-semibold ${scoreColor(c.score)}`}>
          {c.score == null ? '—' : `${fmtScore(c.score)}/10`}
        </span>
      </div>
      <div className="mt-1 flex items-center gap-2">
        <div className="h-1.5 min-w-[30%] flex-1 overflow-hidden rounded-full bg-bg">
          <div className={`h-full rounded-full ${scoreBg(c.score)}`} style={{ width: `${(c.score ?? 0) * 10}%` }} />
        </div>
        <span className="min-w-0 max-w-[65%] break-words text-right text-xs text-gray-300">{c.display}</span>
      </div>
      {c.comment && <p className="mt-1 text-xs text-muted">{c.comment}</p>}
    </li>
  )
}

export const VERDICT_STYLE = {
  Solide: 'border-bull/40 bg-bull/10 text-bull',
  Correct: 'border-warn/40 bg-warn/10 text-warn',
  Fragile: 'border-bear/40 bg-bear/10 text-bear',
}

export function ScoreHeader({ title, subtitle, score, verdict }) {
  return (
    <div className="flex items-center gap-4">
      <ScoreRing score={score} />
      <div className="min-w-0">
        <h2 className="font-semibold">{title}</h2>
        <p className="text-sm text-muted">{subtitle}</p>
        {verdict && (
          <span className={`mt-1 inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${VERDICT_STYLE[verdict]}`}>
            {verdict}
          </span>
        )}
      </div>
    </div>
  )
}

export function Notes({ notes }) {
  if (!notes?.length) return null
  return (
    <div className="mt-3 space-y-1.5">
      {notes.map((n) => (
        <p key={n} className="flex gap-2 rounded-lg border border-warn/30 bg-warn/5 px-3 py-2 text-xs text-warn">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {n}
        </p>
      ))}
    </div>
  )
}
