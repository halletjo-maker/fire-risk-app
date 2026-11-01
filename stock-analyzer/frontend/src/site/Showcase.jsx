import { lazy, Suspense, useEffect, useState } from 'react'
import { BookOpen, PauseCircle } from 'lucide-react'
import SiteLayout, { Link } from './SiteLayout'
import { api } from '../lib/api'
import { changeColor, fmtPct } from '../lib/format'
import { Spinner } from '../components/ui'

const PortfolioChart = lazy(() => import('../components/PortfolioChart'))
const EUR = new Intl.NumberFormat('fr-BE', { style: 'currency', currency: 'EUR' })
const day = (sql) => (sql ? new Date(`${sql.slice(0, 10)}T12:00:00`).toLocaleDateString('fr-BE', { day: 'numeric', month: 'long', year: 'numeric' }) : '—')
const num = (v) => (v == null ? '—' : v.toLocaleString('fr-BE', { maximumFractionDigits: 1 }))
const short = (sql) => (sql ? new Date(`${sql.slice(0, 10)}T12:00:00`).toLocaleDateString('fr-BE', { day: 'numeric', month: 'short' }) : '—')

function Figure({ label, value, sub, className = '' }) {
  return (
    <div className="card p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${className}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
    </div>
  )
}

// Portefeuille témoin : un portefeuille fictif choisi par l'administrateur, montré tel quel (gains comme pertes)
export default function Showcase() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    document.title = 'Portefeuille témoin — MM100'
    api.publicPortfolio().then(setData).catch((e) => setError(e.message))
  }, [])

  const last = data?.history?.filter((h) => h.benchmark_eur != null).at(-1)
  const benchPct = last ? (last.benchmark_eur / data.initial_cash - 1) * 100 : null

  return (
    <SiteLayout>
      <main className="mx-auto max-w-4xl px-4 py-8">
        <p className="text-xs font-semibold uppercase tracking-wider text-bull">La méthode à l'épreuve</p>
        <h1 className="mt-1 text-2xl font-bold sm:text-3xl">Le portefeuille témoin</h1>
        <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-gray-300">
          Un capital virtuel géré seul par les règles de l'outil, sans intervention humaine, et comparé jour après jour à la
          même somme placée dans un ETF MSCI World. Tout est montré tel quel, les bonnes comme les mauvaises périodes.
        </p>

        {error && <p className="mt-8 card p-5 text-sm text-muted">{error}</p>}
        {!data && !error && <div className="flex justify-center py-16"><Spinner /></div>}
        {data && (
          <>
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <Figure label={`Depuis le ${day(data.started)}`} value={fmtPct(data.pnl_pct)} className={changeColor(data.pnl_pct)}
                sub={`${EUR.format(data.initial_cash)} → ${EUR.format(data.value)}`} />
              <Figure label={`${data.benchmark_label} sur la même période`} value={benchPct == null ? '—' : fmtPct(benchPct)}
                className={benchPct == null ? '' : changeColor(benchPct)} sub="le repère à battre" />
              <Figure label="Ventes gagnantes" value={data.stats.closed ? `${data.stats.wins}/${data.stats.closed}` : '—'}
                sub={`${data.positions.length} ligne${data.positions.length > 1 ? 's' : ''} ouverte${data.positions.length > 1 ? 's' : ''} · liquidités ${num(data.cash_pct)} %`} />
            </div>

            {data.note && (
              <p className="mt-4 flex gap-2 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
                <PauseCircle className="mt-0.5 h-4 w-4 shrink-0" /> {data.note}
              </p>
            )}

            <section className="mt-6 card p-4">
              <h2 className="text-sm font-semibold">Évolution comparée</h2>
              {data.history.length >= 2 ? (
                <Suspense fallback={<div className="flex h-48 items-center justify-center"><Spinner /></div>}>
                  <div className="mt-2"><PortfolioChart history={data.history} initial={data.initial_cash} benchLabel={data.benchmark_label} /></div>
                </Suspense>
              ) : <p className="mt-2 text-sm text-muted">La courbe apparaîtra après quelques jours de simulation.</p>}
            </section>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <section className="card p-4">
                <h2 className="text-sm font-semibold">Lignes en portefeuille</h2>
                {data.positions.length === 0 ? <p className="mt-2 text-sm text-muted">Aucune ligne : le programme attend un signal d'achat.</p> : (
                  <ul className="mt-2 divide-y divide-line">
                    {data.positions.map((p) => (
                      <li key={p.symbol + p.entry_at} className="flex items-center justify-between gap-3 py-2 text-sm">
                        <span className="min-w-0">
                          <span className="block truncate font-medium">{p.name}</span>
                          <span className="block text-xs text-muted">{p.symbol} · {num(p.weight_pct)} % · depuis le {short(p.entry_at)}</span>
                        </span>
                        <span className={`shrink-0 font-semibold ${changeColor(p.pnl_pct)}`}>{fmtPct(p.pnl_pct)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              <section className="card p-4">
                <h2 className="text-sm font-semibold">Dernières ventes</h2>
                {data.trades.length === 0 ? <p className="mt-2 text-sm text-muted">Pas encore de vente.</p> : (
                  <ul className="mt-2 divide-y divide-line">
                    {data.trades.map((t) => (
                      <li key={t.symbol + t.exit_at} className="flex items-center justify-between gap-3 py-2 text-sm">
                        <span className="min-w-0">
                          <span className="block truncate font-medium">{t.name}</span>
                          <span className="block text-xs text-muted">{short(t.entry_at)} → {short(t.exit_at)} · {t.exit_reason}</span>
                        </span>
                        <span className={`shrink-0 font-semibold ${changeColor(t.pnl_pct)}`}>{fmtPct(t.pnl_pct)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>

            <section className="mt-6 card p-4 text-sm leading-relaxed text-gray-300">
              <h2 className="font-semibold text-gray-100">Les règles suivies</h2>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                <li>Achat d'un produit de la liste « {data.list || 'suivie'} » quand il obtient le signal 🟢 ACHAT et se trouve dans sa zone d'achat.</li>
                <li>Au plus {data.max_positions} lignes d'environ 10 % chacune ; frais simulés à chaque opération.</li>
                <li>Vente à l'objectif, au stop-loss (qui monte avec le cours pour protéger les gains), ou quand le signal passe à 🔴 VENTE.</li>
                <li>Pas de nouvel achat quand le marché mondial passe sous sa moyenne 100 jours.</li>
              </ul>
              <Link href="/apprendre/diversifier-gerer-risque" className="mt-3 inline-flex items-center gap-1.5 text-bull hover:underline">
                <BookOpen className="h-4 w-4" /> Comprendre la gestion du risque
              </Link>
            </section>
            <p className="mt-4 text-xs text-muted">
              Simulation sur les derniers cours connus, sans argent réel et avant impôts. Les performances passées ne préjugent pas
              des performances futures. Ce n'est pas un conseil en investissement.
            </p>
          </>
        )}
      </main>
    </SiteLayout>
  )
}
