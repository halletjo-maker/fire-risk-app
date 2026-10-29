import { lazy, Suspense } from 'react'
import { Database, Info } from 'lucide-react'
import { fmtNumber, fmtPct, fmtPrice } from '../lib/format'
import { Spinner } from './ui'
import { Criterion, Notes, ScoreHeader } from './ScoreParts'
// Graphique chargé à la demande (Recharts est volumineux)
const TechnicalChart = lazy(() => import('./TechnicalChart'))

const MM100_STYLE = {
  'AU-DESSUS': { icon: '✅', cls: 'border-bull/40 bg-bull/10 text-bull', label: 'AU-DESSUS de la MM100' },
  'EN-DESSOUS': { icon: '❌', cls: 'border-bear/40 bg-bear/10 text-bear', label: 'EN DESSOUS de la MM100' },
  CROISEMENT: { icon: '⚡', cls: 'border-warn/40 bg-warn/10 text-warn', label: 'CROISEMENT de la MM100' },
}

function Mm100Banner({ mm, currency }) {
  const st = MM100_STYLE[mm.status]
  const cross = mm.cross
  const plain = cross
    ? cross.direction === 'HAUSSIER'
      ? 'Le prix vient de repasser au-dessus de sa moyenne des 100 derniers jours : la tendance de fond pourrait redevenir haussière.'
      : 'Le prix vient de passer sous sa moyenne des 100 derniers jours : la tendance de fond se dégrade.'
    : mm.above
      ? `Le prix est ${fmtPct(mm.distance_pct, { sign: false })} au-dessus de sa moyenne des 100 derniers jours : tendance de fond haussière.`
      : `Le prix est ${fmtPct(Math.abs(mm.distance_pct), { sign: false })} sous sa moyenne des 100 derniers jours : tendance de fond baissière.`
  return (
    <div className={`mt-4 rounded-xl border p-3 ${st.cls}`}>
      <p className="text-[11px] font-semibold uppercase tracking-wider opacity-80">★ Critère principal</p>
      <p className="mt-0.5 text-base font-bold">
        {st.icon} {st.label}
        {cross && <span className="font-semibold"> ({cross.direction === 'HAUSSIER' ? 'à la hausse' : 'à la baisse'})</span>}
      </p>
      <div className="mt-1 flex flex-wrap gap-x-4 text-sm">
        <span>Écart : <b>{fmtPct(mm.distance_pct)}</b></span>
        <span>MM100 : <b>{fmtPrice(mm.value, currency)}</b></span>
        {mm.slope_pct != null && <span>Pente : <b>{mm.slope_pct > 0 ? '↗ montante' : '↘ descendante'}</b></span>}
      </div>
      <p className="mt-1.5 text-xs text-gray-300">{plain}</p>
    </div>
  )
}

function Levels({ levels, currency }) {
  if (!levels || (levels.support == null && levels.resistance == null)) return null
  return (
    <div className="mt-3 grid grid-cols-2 gap-2">
      <div className="rounded-lg bg-bg px-3 py-2">
        <p className="text-[11px] uppercase tracking-wide text-muted">Support</p>
        <p className="text-sm font-medium">{levels.support != null ? fmtPrice(levels.support, currency) : '—'}</p>
        {levels.support_distance_pct != null && <p className="text-xs text-muted">{fmtPct(levels.support_distance_pct)}</p>}
      </div>
      <div className="rounded-lg bg-bg px-3 py-2">
        <p className="text-[11px] uppercase tracking-wide text-muted">Résistance</p>
        <p className="text-sm font-medium">{levels.resistance != null ? fmtPrice(levels.resistance, currency) : '—'}</p>
        {levels.resistance_distance_pct != null && <p className="text-xs text-muted">{fmtPct(levels.resistance_distance_pct)}</p>}
      </div>
    </div>
  )
}

export default function TechnicalCard({ data, loading, error }) {
  if (loading) {
    return (
      <section className="card flex items-center gap-3 p-4 text-sm text-muted">
        <Spinner className="h-5 w-5" /> Analyse technique en cours (MM100, RSI, MACD…)
      </section>
    )
  }
  if (error) return <section className="card p-4 text-sm text-bear">Analyse technique indisponible : {error}</section>
  if (!data) return null
  const t = data
  if (!t.applicable) {
    return (
      <section className="card p-4">
        <h2 className="font-semibold">Analyse technique</h2>
        <p className="mt-2 flex gap-2 text-sm text-muted"><Info className="mt-0.5 h-4 w-4 shrink-0" /> {t.notes?.[0]}</p>
      </section>
    )
  }
  return (
    <section className="card min-w-0 p-4 sm:p-5" aria-label="Analyse technique">
      <ScoreHeader
        title="Analyse technique"
        subtitle="Score technique sur 10 · poids 45 % du score global"
        score={t.score}
        verdict={t.verdict}
      />
      {t.inverse && t.underlying_score != null && (
        <p className="mt-2 text-xs text-muted">
          Score du sous-jacent : {fmtNumber(t.underlying_score, 1)}/10 → inversé pour un turbo put.
        </p>
      )}
      <Notes notes={t.notes} />
      {t.mm100 && <Mm100Banner mm={t.mm100} currency={t.currency} />}
      <Levels levels={t.levels} currency={t.currency} />
      {t.chart?.length > 0 && (
        <Suspense fallback={<div className="mt-4 flex h-60 items-center justify-center"><Spinner /></div>}>
          <TechnicalChart data={t.chart} support={t.levels?.support} resistance={t.levels?.resistance} />
        </Suspense>
      )}
      <ul className="mt-3 divide-y divide-line border-t border-line">
        {t.criteria.map((c) => <Criterion key={c.key} c={c} />)}
      </ul>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-line pt-3 text-xs text-muted">
        <span className="flex items-center gap-1"><Database className="h-3.5 w-3.5" /> Sources :</span>
        {t.sources.map((s) => <span key={s.name} className={s.ok ? 'text-bull' : 'line-through'}>{s.name}</span>)}
        {t.analysed?.name && <span className="ml-auto">Analysé : {t.analysed.symbol || t.analysed.name}</span>}
      </div>
    </section>
  )
}
