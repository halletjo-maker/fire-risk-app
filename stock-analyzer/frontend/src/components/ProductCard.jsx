import { ArrowDownRight, ArrowUpRight, CheckCircle2, Clock, Database, XCircle } from 'lucide-react'
import { changeColor, fmtDateTime, fmtNumber, fmtPct, fmtPrice, fmtVolume } from '../lib/format'
import TypeBadge from './TypeBadge'

function Stat({ label, children, className = '' }) {
  return (
    <div className={`rounded-lg bg-bg px-3 py-2 ${className}`}>
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 break-words text-sm font-medium">{children}</p>
    </div>
  )
}

function barrierColor(pct) {
  if (pct == null) return ''
  if (pct < 5) return 'text-bear'
  if (pct < 15) return 'text-warn'
  return 'text-bull'
}

function DerivativeDetails({ d, currency }) {
  const sens = d.direction === 'CALL' ? 'Call (haussier)' : d.direction === 'PUT' ? 'Put (baissier)' : '—'
  return (
    <div className="mt-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Caractéristiques du produit</h3>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat label="Sous-jacent">{d.underlying || '—'}{d.spot != null && <span className="text-muted"> · {fmtNumber(d.spot)}</span>}</Stat>
        <Stat label="Sens">{sens}</Stat>
        <Stat label="Émetteur">{d.issuer || '—'}</Stat>
        <Stat label="Barrière désactivante">{d.barrier != null ? fmtPrice(d.barrier, currency) : '—'}</Stat>
        <Stat label="Distance à la barrière">
          <span className={barrierColor(d.barrier_distance_pct)}>
            {d.barrier_distance_pct != null ? fmtPct(d.barrier_distance_pct, { sign: false }) : '—'}
          </span>
        </Stat>
        <Stat label="Levier">{d.leverage != null ? `× ${fmtNumber(d.leverage)}` : '—'}</Stat>
        <Stat label="Parité">{d.parity != null ? fmtNumber(d.parity) : '—'}</Stat>
        <Stat label="Échéance">{d.maturity || '—'}</Stat>
        {d.nature && <Stat label="Nature" className="col-span-2 sm:col-span-1">{d.nature}</Stat>}
      </div>
    </div>
  )
}

export default function ProductCard({ result }) {
  const { product: p, quote: q, derivative, sources = [], source } = result
  const up = q.change_pct > 0
  const Arrow = up ? ArrowUpRight : ArrowDownRight
  const when = fmtDateTime(q.time) || fmtDateTime(result.fetched_at)

  return (
    <section className="card p-4 sm:p-5" aria-label={`Fiche ${p.name}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <TypeBadge type={p.type} label={p.type_label} />
            <span className="truncate text-xs text-muted">
              {[p.symbol, p.isin, p.exchange].filter(Boolean).join(' · ')}
            </span>
          </div>
          <h2 className="mt-1.5 text-lg font-bold leading-tight sm:text-xl">{p.name}</h2>
          {derivative && (
            <p className="mt-0.5 text-sm text-muted">
              {[p.type_label, derivative.direction === 'CALL' ? 'Call' : derivative.direction === 'PUT' ? 'Put' : null]
                .filter(Boolean).join(' ')}
              {derivative.underlying && <> sur <span className="text-gray-100">{derivative.underlying}</span></>}
              {derivative.issuer && <> · {derivative.issuer.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())}</>}
            </p>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-x-4 gap-y-1">
        <p className="text-3xl font-bold tracking-tight">{fmtPrice(q.price, p.currency)}</p>
        {q.change_pct != null && (
          <p className={`flex items-center gap-1 pb-1 text-base font-semibold ${changeColor(q.change_pct)}`}>
            {q.change_pct !== 0 && <Arrow className="h-4 w-4" />}
            {fmtPct(q.change_pct)}
            {q.change != null && <span className="font-normal opacity-80">({q.change > 0 ? '+' : ''}{fmtNumber(q.change, 3)})</span>}
          </p>
        )}
      </div>
      <p className="mt-1 text-xs text-muted">Variation du jour</p>

      <div className="mt-4 grid grid-cols-3 gap-2">
        <Stat label="Volume">{fmtVolume(q.volume)}</Stat>
        <Stat label="Clôture veille">{q.prev_close != null ? fmtNumber(q.prev_close, 3) : '—'}</Stat>
        <Stat label="Devise">{p.currency || '—'}</Stat>
      </div>

      {derivative && <DerivativeDetails d={derivative} currency={p.currency} />}

      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-line pt-3 text-xs text-muted">
        <span className="flex items-center gap-1"><Database className="h-3.5 w-3.5" /> Source :</span>
        {sources.map((s) => (
          <span
            key={s.name}
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 ${s.ok ? 'border-bull/40 text-bull' : 'border-line text-muted line-through'}`}
            title={s.ok ? 'Source utilisée' : 'Source indisponible, suivante essayée'}
          >
            {s.ok ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />} {s.name}
          </span>
        ))}
        {!sources.length && source && <span>{source}</span>}
        {when && <span className="ml-auto flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {when}</span>}
      </div>
    </section>
  )
}
