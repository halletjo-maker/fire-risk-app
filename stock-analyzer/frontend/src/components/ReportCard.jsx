import { useState } from 'react'
import { Check, ChevronRight, CircleAlert, Copy, FileText, Scale, Star } from 'lucide-react'
import { changeColor, fmtPct, fmtPrice, fmtScore, scoreColor } from '../lib/format'
import { Spinner } from './ui'
import TypeBadge from './TypeBadge'

function Section({ title, children }) {
  return (
    <div className="border-t border-line pt-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">{title}</h3>
      {children}
    </div>
  )
}

function PointList({ items, positive }) {
  if (!items.length) return <p className="text-sm text-muted">Aucun point marquant.</p>
  const Icon = positive ? Check : CircleAlert
  return (
    <ul className="space-y-2">
      {items.map((i) => (
        <li key={i.area + i.label} className="flex gap-2 text-sm">
          <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${positive ? 'text-bull' : 'text-bear'}`} aria-hidden="true" />
          <div className="min-w-0">
            <p>
              {i.label} <span className="text-muted">· {i.area}</span>{' '}
              <span className={`font-semibold ${scoreColor(i.score)}`}>{fmtScore(i.score)}/10</span>
            </p>
            <p className="break-words text-xs text-muted">{i.display} — {i.comment}</p>
          </div>
        </li>
      ))}
    </ul>
  )
}

function StopLoss({ sl }) {
  return (
    <>
      <div className="overflow-hidden rounded-lg border border-line">
        <table className="w-full text-sm">
          <thead className="bg-bg text-left text-xs text-muted">
            <tr><th className="px-3 py-2 font-medium">Niveau</th><th className="px-3 py-2 text-right font-medium">Prix du stop</th><th className="px-3 py-2 text-right font-medium">Écart</th></tr>
          </thead>
          <tbody>
            {sl.levels.map((lv) => (
              <tr key={lv.key} className={`border-t border-line ${lv.recommended ? 'bg-bull/5' : ''}`}>
                <td className="px-3 py-2">
                  <span className="flex items-center gap-1.5">
                    {lv.recommended && <Star className="h-3.5 w-3.5 shrink-0 fill-bull text-bull" aria-label="Conseillé" />}
                    <span className={lv.recommended ? 'font-semibold text-bull' : ''}>{lv.label}</span>
                  </span>
                  {lv.detail && <span className="block text-xs text-muted">{lv.detail}</span>}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right font-medium">{fmtPrice(lv.price, sl.currency)}</td>
                <td className="whitespace-nowrap px-3 py-2 text-right text-bear">{fmtPct(lv.distance_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sl.reason && <p className="mt-2 text-sm"><Star className="mr-1 inline h-3.5 w-3.5 fill-bull text-bull" />{sl.reason}</p>}
      {sl.notes?.map((n) => <p key={n} className="mt-1 text-xs text-warn">⚠️ {n}</p>)}
    </>
  )
}

function Alternative({ a, onPick }) {
  return (
    <li>
      <button
        onClick={() => onPick(a)}
        className="flex w-full items-center gap-3 rounded-lg border border-line bg-bg p-3 text-left transition hover:border-bull/60"
      >
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{a.title}</p>
          <p className="mt-0.5 flex items-center gap-2">
            <TypeBadge type={a.type} />
            <span className="truncate text-sm font-medium">{a.name}</span>
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {a.symbol} · {fmtPrice(a.price, a.currency)}
            {a.change_pct != null && <span className={`ml-1 ${changeColor(a.change_pct)}`}>{fmtPct(a.change_pct)}</span>}
            {a.technical_score != null && <> · technique <span className={scoreColor(a.technical_score)}>{fmtScore(a.technical_score)}/10</span></>}
          </p>
          <p className="mt-1 text-xs text-gray-300">{a.reason}</p>
        </div>
        <ChevronRight className="h-4 w-4 shrink-0 text-muted" aria-label="Analyser" />
      </button>
    </li>
  )
}

function asText(r) {
  const p = r.product
  const lines = [
    `RAPPORT — ${p.name} (${p.symbol || p.isin || ''})`,
    `Score global : ${fmtScore(r.decision.score)}/10 — ${r.decision.buy.icon} ${r.decision.buy.label}`,
    '', ...r.summary, '',
    'FORCES', ...r.strengths.map((i) => `+ ${i.label} (${fmtScore(i.score)}/10) : ${i.display}`),
    'FAIBLESSES', ...r.weaknesses.map((i) => `- ${i.label} (${fmtScore(i.score)}/10) : ${i.display}`),
    '', 'POSITION VS MM100', r.mm100,
    '', 'STOP-LOSS', ...r.stop_loss.levels.map((lv) => `${lv.recommended ? '★ ' : '  '}${lv.label} : ${fmtPrice(lv.price, r.stop_loss.currency)} (${fmtPct(lv.distance_pct)})`),
    '', 'ALTERNATIVES', ...r.alternatives.map((a) => `• ${a.title} : ${a.name} (${a.symbol}) — ${a.reason}`),
    '', `Sources : ${r.sources.map((s) => s.name).join(', ')}`,
    `Généré le ${new Date(r.generated_at).toLocaleString('fr-BE')}`,
    '', r.disclaimer,
  ]
  return lines.join('\n')
}

export default function ReportCard({ data, loading, error, onPick }) {
  const [copied, setCopied] = useState(false)

  if (loading) {
    return (
      <section className="card flex items-center gap-3 p-4 text-sm text-muted">
        <Spinner className="h-5 w-5" /> Rédaction du rapport (stop-loss, alternatives…)
      </section>
    )
  }
  if (error) return <section className="card p-4 text-sm text-bear">Rapport indisponible : {error}</section>
  if (!data) return null
  if (!data.available) return <section className="card p-4 text-sm text-muted">{data.message}</section>
  const r = data

  const copy = async () => {
    const text = asText(r)
    if (navigator.share && /Mobi|Android|iPhone/i.test(navigator.userAgent)) {
      try { await navigator.share({ title: `Rapport ${r.product.name}`, text }); return } catch (e) {
        if (e?.name === 'AbortError') return // partage annulé par l'utilisateur
      }
    }
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* presse-papiers refusé */ }
  }

  return (
    <section className="card min-w-0 space-y-4 p-4 sm:p-5" aria-label="Rapport justificatif">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 font-semibold"><FileText className="h-5 w-5" /> Rapport justificatif</h2>
          <p className="text-xs text-muted">
            Généré le {new Date(r.generated_at).toLocaleString('fr-BE', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}
          </p>
        </div>
        <button className="btn-ghost shrink-0 border border-line" onClick={copy}>
          {copied ? <><Check className="h-4 w-4 text-bull" /> Copié</> : <><Copy className="h-4 w-4" /> Partager</>}
        </button>
      </div>

      <div className="rounded-lg bg-bg p-3">
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted">Résumé exécutif</h3>
        <p className="text-sm leading-relaxed">{r.summary.join(' ')}</p>
      </div>

      <Section title="Forces">
        <PointList items={r.strengths} positive />
      </Section>
      <Section title="Faiblesses">
        <PointList items={r.weaknesses} positive={false} />
      </Section>

      <Section title="★ Position vs MM100">
        <p className="text-sm leading-relaxed">{r.mm100}</p>
      </Section>

      <Section title="Stop-loss proposés">
        <StopLoss sl={r.stop_loss} />
      </Section>

      {r.alternatives.length > 0 && (
        <Section title="3 alternatives">
          <ul className="space-y-2">
            {r.alternatives.map((a) => <Alternative key={a.role} a={a} onPick={onPick} />)}
          </ul>
        </Section>
      )}

      <Section title="Sources utilisées">
        <p className="text-sm">{r.sources.map((s) => s.name).join(' · ')}</p>
        <p className="mt-1 text-xs text-muted">
          Horodatage : {new Date(r.generated_at).toLocaleString('fr-BE')} (heure de Bruxelles)
        </p>
      </Section>

      <div className="rounded-lg border border-line bg-bg p-3">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
          <Scale className="h-3.5 w-3.5" /> Avertissement légal — MiFID II
        </h3>
        <p className="mt-1 text-[11px] leading-relaxed text-muted">{r.disclaimer}</p>
      </div>
    </section>
  )
}
