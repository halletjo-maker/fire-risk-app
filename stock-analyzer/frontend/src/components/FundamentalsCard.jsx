import { useState } from 'react'
import { ChevronDown, Database, Info } from 'lucide-react'
import { Spinner } from './ui'
import { Criterion, Notes, ScoreHeader } from './ScoreParts'

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
      <ScoreHeader
        title="Analyse fondamentale"
        subtitle="Score fondamental sur 10 · poids 35 % du score global"
        score={f.score}
        verdict={f.verdict}
      />
      <Notes notes={f.notes} />

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
