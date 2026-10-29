import { useState } from 'react'
import { AlertTriangle, ChevronDown, Database, Info } from 'lucide-react'
import { fmtScore, scoreBg, scoreColor } from '../lib/format'
import { Spinner } from './ui'

function ScoreRing({ score }) {
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

function Criterion({ c }) {
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

const VERDICT_STYLE = {
  Solide: 'border-bull/40 bg-bull/10 text-bull',
  Correct: 'border-warn/40 bg-warn/10 text-warn',
  Fragile: 'border-bear/40 bg-bear/10 text-bear',
}

export default function FundamentalsCard({ data, loading, error }) {
  const [showInfo, setShowInfo] = useState(true)

  if (loading) {
    return (
      <section className="card flex items-center gap-3 p-4 text-sm text-muted">
        <Spinner className="h-5 w-5" /> Analyse fondamentale en cours (bilans, consensus des analystes…)
      </section>
    )
  }
  if (error) return <section className="card p-4 text-sm text-bear">Analyse fondamentale indisponible : {error}</section>
  if (!data) return null

  const f = data
  if (!f.applicable) {
    return (
      <section className="card p-4">
        <h2 className="font-semibold">Analyse fondamentale</h2>
        <p className="mt-2 flex gap-2 text-sm text-muted"><Info className="mt-0.5 h-4 w-4 shrink-0" /> {f.notes?.[0]}</p>
      </section>
    )
  }

  return (
    <section className="card min-w-0 p-4 sm:p-5" aria-label="Analyse fondamentale">
      <div className="flex items-center gap-4">
        <ScoreRing score={f.score} />
        <div className="min-w-0">
          <h2 className="font-semibold">Analyse fondamentale</h2>
          <p className="text-sm text-muted">Score fondamental sur 10 · poids 35 % du score global</p>
          {f.verdict && (
            <span className={`mt-1 inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${VERDICT_STYLE[f.verdict]}`}>
              {f.verdict}
            </span>
          )}
        </div>
      </div>

      {f.notes?.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {f.notes.map((n) => (
            <p key={n} className="flex gap-2 rounded-lg border border-warn/30 bg-warn/5 px-3 py-2 text-xs text-warn">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {n}
            </p>
          ))}
        </div>
      )}

      <ul className="mt-2 divide-y divide-line">
        {f.criteria.map((c) => <Criterion key={c.key} c={c} />)}
      </ul>

      {f.info?.length > 0 && (
        <div className="mt-2 border-t border-line pt-3">
          <button
            className="flex w-full items-center justify-between text-xs font-semibold uppercase tracking-wider text-muted"
            onClick={() => setShowInfo((v) => !v)}
            aria-expanded={showInfo}
          >
            Informations complémentaires
            <ChevronDown className={`h-4 w-4 transition ${showInfo ? 'rotate-180' : ''}`} />
          </button>
          {showInfo && (
            <dl className="mt-2 grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-2">
              {f.info.map((i) => (
                <div key={i.label} className="flex justify-between gap-3">
                  <dt className="shrink-0 text-muted">{i.label}</dt>
                  <dd className="min-w-0 break-words text-right">{i.display}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-line pt-3 text-xs text-muted">
        <span className="flex items-center gap-1"><Database className="h-3.5 w-3.5" /> Sources :</span>
        {f.sources.map((s) => (
          <span key={s.name} className={s.ok ? 'text-bull' : 'line-through'}>{s.name}</span>
        ))}
        {f.coverage < 1 && <span className="ml-auto">Données : {Math.round(f.coverage * 100)} %</span>}
      </div>
    </section>
  )
}
