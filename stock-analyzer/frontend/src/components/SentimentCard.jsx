import { CalendarClock, Database, ExternalLink, Info } from 'lucide-react'
import { Spinner } from './ui'
import { Notes, ScoreHeader } from './ScoreParts'

const DOT = { positif: '🟢', neutre: '🟡', negatif: '🔴' }
const LABEL = { positif: 'Positif', neutre: 'Neutre', negatif: 'Négatif' }

function ago(hours) {
  if (hours == null) return null
  if (hours < 1) return `il y a ${Math.max(1, Math.round(hours * 60))} min`
  if (hours < 24) return `il y a ${Math.round(hours)} h`
  return `il y a ${Math.round(hours / 24)} j`
}

function SplitBar({ counts }) {
  const total = counts.positif + counts.neutre + counts.negatif
  if (!total) return null
  const seg = [['positif', 'bg-bull'], ['neutre', 'bg-warn'], ['negatif', 'bg-bear']]
  return (
    <div className="mt-4">
      <div className="flex h-2 gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
        {seg.map(([k, cls]) => counts[k] > 0 && (
          <div key={k} className={`${cls} h-full`} style={{ width: `${(counts[k] / total) * 100}%` }} />
        ))}
      </div>
      <p className="mt-1.5 flex flex-wrap gap-x-3 text-xs text-muted">
        {seg.map(([k]) => <span key={k}>{DOT[k]} {counts[k]} {LABEL[k].toLowerCase()}{counts[k] > 1 ? 's' : ''}</span>)}
        <span>sur {total} titre{total > 1 ? 's' : ''}</span>
      </p>
    </div>
  )
}

function Events({ events }) {
  if (!events?.length) return null
  return (
    <div className="mt-4 rounded-lg border border-line bg-bg p-3">
      <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
        <CalendarClock className="h-3.5 w-3.5" /> Événements à venir
      </p>
      <ul className="mt-1.5 space-y-1 text-sm">
        {events.map((e) => (
          <li key={e.type} className="flex justify-between gap-3">
            <span>{e.type === 'Earnings Date' ? '💰' : '💶'} {e.label}</span>
            <span className={`shrink-0 ${e.days <= 2 ? 'font-semibold text-warn' : 'text-muted'}`}>
              {new Date(e.date).toLocaleDateString('fr-BE', { day: 'numeric', month: 'short' })}
              {' · '}{e.days === 0 ? "aujourd'hui" : `dans ${e.days} j`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function NewsItem({ item }) {
  return (
    <li className="py-3">
      <div className="flex gap-2">
        <span className="shrink-0 text-sm" title={`Sentiment ${LABEL[item.sentiment].toLowerCase()}`} aria-label={`Sentiment ${LABEL[item.sentiment].toLowerCase()}`}>
          {DOT[item.sentiment]}
        </span>
        <div className="min-w-0">
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm leading-snug hover:text-bull hover:underline"
          >
            {item.title}
            <ExternalLink className="ml-1 inline h-3 w-3 align-baseline text-muted" />
          </a>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
            <span>{item.source}</span>
            {item.age_hours != null && <span>· {ago(item.age_hours)}</span>}
            <span className="rounded border border-line px-1 text-[10px] uppercase">{item.lang}</span>
            {item.tags?.map((t) => (
              <span key={t} className="rounded bg-panel2 px-1.5 py-0.5 text-[10px] text-gray-300">{t}</span>
            ))}
          </p>
          {item.keywords?.length > 0 && (
            <p className="mt-1 text-[11px] text-muted">Mots repérés : « {item.keywords.join(' », « ')} »</p>
          )}
        </div>
      </div>
    </li>
  )
}

export default function SentimentCard({ data, loading, error }) {
  if (loading) {
    return (
      <section className="card flex items-center gap-3 p-4 text-sm text-muted">
        <Spinner className="h-5 w-5" /> Lecture des actualités des dernières 72 h…
      </section>
    )
  }
  if (error) return <section className="card p-4 text-sm text-bear">Actualités indisponibles : {error}</section>
  if (!data) return null
  const s = data
  if (!s.applicable) {
    return (
      <section className="card p-4">
        <h2 className="font-semibold">Actualités et sentiment</h2>
        <p className="mt-2 flex gap-2 text-sm text-muted"><Info className="mt-0.5 h-4 w-4 shrink-0" /> {s.notes?.[0]}</p>
      </section>
    )
  }
  return (
    <section className="card min-w-0 p-4 sm:p-5" aria-label="Actualités et sentiment">
      <ScoreHeader
        title="Actualités et sentiment"
        subtitle={`Score sentiment sur 10 · poids 20 % · « ${s.term} » · 72 h`}
        score={s.score}
        verdict={s.verdict}
      />
      {s.inverse && s.underlying_score != null && (
        <p className="mt-2 text-xs text-muted">Sentiment sur {s.term} : {String(s.underlying_score).replace('.', ',')}/10 → inversé pour un turbo put.</p>
      )}
      <Notes notes={s.notes} />
      <SplitBar counts={s.counts} />
      <Events events={s.events} />
      {s.items.length > 0 && (
        <ul className="mt-2 divide-y divide-line">
          {s.items.map((i) => <NewsItem key={i.url || i.title} item={i} />)}
        </ul>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-line pt-3 text-xs text-muted">
        <span className="flex items-center gap-1"><Database className="h-3.5 w-3.5" /> Sources :</span>
        {s.sources.map((x) => <span key={x.name} className={x.ok ? 'text-bull' : 'line-through'}>{x.name}</span>)}
      </div>
      <p className="mt-2 text-[11px] text-muted">
        Sentiment estimé automatiquement à partir des titres (lexique financier français et anglais) : à confirmer en lisant les articles.
      </p>
    </section>
  )
}
