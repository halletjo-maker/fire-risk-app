import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { FlaskConical, Play } from 'lucide-react'
import { api } from '../lib/api'
import { useWatchlists } from '../lib/watchlists'
import { changeColor, fmtPct } from '../lib/format'
import Modal from './Modal'
import { Spinner } from './ui'

const PortfolioChart = lazy(() => import('./PortfolioChart'))
const pct = (v) => (v == null ? '—' : fmtPct(v))
const num = (v) => (v == null ? '—' : new Intl.NumberFormat('fr-BE', { maximumFractionDigits: 1 }).format(v))

function Row({ label, s, strong }) {
  return (
    <tr className={strong ? 'font-semibold' : ''}>
      <td className="py-1.5 pr-2">{label}</td>
      <td className={`py-1.5 text-right ${changeColor(s?.cagr_pct)}`}>{pct(s?.cagr_pct)}</td>
      <td className="py-1.5 text-right text-bear">{pct(s?.max_drawdown_pct)}</td>
      <td className="py-1.5 text-right">{s?.exposure_pct != null ? `${num(s.exposure_pct)} %` : '—'}</td>
    </tr>
  )
}

function Results({ r }) {
  const rules = r.variants.rules?.stats || {}
  const bench = r.benchmark?.stats || {}
  const history = Object.entries(r.variants.rules?.curve || {}).map(([day, v]) => ({
    day, value_eur: v, benchmark_eur: r.benchmark?.curve?.[day] ?? null,
  }))
  const years = Object.keys(rules.yearly || {})
  const beat = rules.cagr_pct != null && bench.cagr_pct != null && rules.cagr_pct > bench.cagr_pct
  const safer = rules.max_drawdown_pct != null && bench.max_drawdown_pct != null && rules.max_drawdown_pct > bench.max_drawdown_pct
  const start = r.start ? new Date(`${r.start}T12:00:00`).toLocaleDateString('fr-BE', { month: 'long', year: 'numeric' }) : ''
  return (
    <div className="space-y-4">
      <p className={`rounded-lg border px-3 py-2 text-sm ${beat ? 'border-bull/40 bg-bull/10 text-bull' : 'border-warn/40 bg-warn/10 text-warn'}`}>
        Depuis {start}, sur {r.tested} titre(s) de « {r.params?.list} » : les règles ont rapporté <b>{pct(rules.cagr_pct)} par an</b> contre{' '}
        <b>{pct(bench.cagr_pct)}</b> pour le MSCI World{safer ? ', avec une pire chute plus faible' : ''}.
        {!beat && ' La méthode a fait moins bien que le simple ETF sur cette période.'}
        {rules.exposure_pct != null && rules.exposure_pct < 50 && ` Elle n'a été investie qu'à ${num(rules.exposure_pct)} % en moyenne : l'argent est souvent resté en liquidités.`}
      </p>
      {history.length > 2 && (
        <Suspense fallback={<div className="flex h-48 items-center justify-center"><Spinner /></div>}>
          <PortfolioChart history={history} initial={r.capital} benchLabel="ETF MSCI World" />
        </Suspense>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-xs text-muted">
            <tr><th className="pb-1 text-left font-medium">Stratégie</th><th className="pb-1 text-right font-medium">Par an</th>
              <th className="pb-1 text-right font-medium">Pire chute</th><th className="pb-1 text-right font-medium">Investi</th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {Object.entries(r.variants).map(([k, v]) => <Row key={k} label={v.label} s={v.stats} strong={k === 'rules'} />)}
            <Row label="ETF MSCI World (acheté et gardé)" s={{ ...bench, exposure_pct: 100 }} />
            <Row label="Tous les titres de la liste, gardés" s={{ ...r.equal_weight?.stats, exposure_pct: 100 }} />
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">
        Règles actuelles : {rules.trades ?? 0} ventes, {rules.win_rate_pct ?? '—'} % gagnantes, résultat moyen {pct(rules.avg_trade_pct)} par opération.
      </p>
      {years.length > 0 && (
        <details className="rounded-lg bg-bg px-3 py-2 text-sm">
          <summary className="cursor-pointer select-none text-xs font-semibold uppercase tracking-wider text-muted">Année par année</summary>
          <table className="mt-2 w-full">
            <thead className="text-xs text-muted"><tr><th className="text-left font-medium">Année</th><th className="text-right font-medium">Règles</th><th className="text-right font-medium">MSCI World</th></tr></thead>
            <tbody>
              {years.map((y) => (
                <tr key={y}><td className="py-0.5">{y}</td>
                  <td className={`text-right ${changeColor(rules.yearly[y])}`}>{pct(rules.yearly[y])}</td>
                  <td className={`text-right ${changeColor(bench.yearly?.[y])}`}>{pct(bench.yearly?.[y])}</td></tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
      <div className="rounded-lg border border-line p-3 text-xs leading-relaxed text-muted">
        <p className="font-semibold text-gray-200">À lire avec prudence</p>
        <ul className="mt-1 list-disc space-y-1 pl-4">
          <li>Seule l'analyse technique est rejouée : les fondamentaux et l'actualité du passé ne sont pas disponibles.</li>
          <li>La liste est celle d'aujourd'hui : les sociétés disparues ou rachetées manquent (biais du survivant), ce qui embellit surtout « Tous les titres de la liste ».</li>
          <li>Rendements en devise locale, sans effet de change ni impôts ; achats et ventes au cours de clôture.</li>
          <li>Les performances passées ne préjugent pas des performances futures.</li>
        </ul>
      </div>
    </div>
  )
}

// Tester les règles de l'outil sur 5 ou 10 ans d'historique
export default function BacktestModal({ onClose }) {
  const wl = useWatchlists()
  const [watchlistId, setWatchlistId] = useState(wl.selectedId || wl.watchlists[0]?.id || '')
  const [years, setYears] = useState(10)
  const [bt, setBt] = useState(undefined)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const timer = useRef(null)

  const poll = () => api.backtest().then((r) => {
    setBt(r.backtest)
    if (r.backtest?.status === 'running') timer.current = setTimeout(poll, 3000)
  }).catch((e) => setError(e.message))
  useEffect(() => { poll(); return () => clearTimeout(timer.current) }, [])

  const launch = async () => {
    setBusy(true)
    setError(null)
    try { setBt((await api.runBacktest({ watchlist_id: Number(watchlistId), years })).backtest); clearTimeout(timer.current); timer.current = setTimeout(poll, 3000) }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const running = bt?.status === 'running'
  const selected = wl.watchlists.find((w) => w.id === Number(watchlistId))

  return (
    <Modal title="Tester la méthode sur le passé" onClose={onClose}>
      <div className="mt-2 space-y-4">
        <p className="text-sm text-muted">
          Les règles des portefeuilles fictifs (score, garde-fou MM200, zone d'achat, stop-loss, objectifs, filtre de marché)
          sont rejouées semaine après semaine sur l'historique d'une liste, avec 10 000 € virtuels, puis comparées au MSCI World.
        </p>
        <div className="grid grid-cols-3 gap-2">
          <label className="col-span-2 text-sm font-medium">Liste
            <select className="input mt-1" value={watchlistId} onChange={(e) => setWatchlistId(e.target.value)} disabled={running}>
              {wl.watchlists.map((w) => <option key={w.id} value={w.id}>{w.name} ({w.item_count})</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">Période
            <select className="input mt-1" value={years} onChange={(e) => setYears(Number(e.target.value))} disabled={running}>
              <option value={5}>5 ans</option><option value={10}>10 ans</option>
            </select>
          </label>
        </div>
        {selected?.item_count > 150 && <p className="text-xs text-muted">Liste longue : un échantillon régulier de 150 titres sera testé.</p>}
        <button className="btn-primary w-full" onClick={launch} disabled={busy || running || !watchlistId}>
          {running ? <Spinner className="h-4 w-4" /> : <Play className="h-4 w-4" />} {running ? 'Test en cours…' : 'Lancer le test'}
        </button>
        {error && <p className="text-sm text-bear" role="alert">{error}</p>}
        {running && (
          <div>
            <div className="h-2 overflow-hidden rounded-full bg-bg" role="progressbar" aria-valuenow={bt.progress} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-full rounded-full bg-bull transition-all" style={{ width: `${bt.progress}%` }} />
            </div>
            <p className="mt-1 text-xs text-muted">{bt.progress} % · compte 1 à 2 minutes par tranche de 10 titres. Tu peux fermer cette fenêtre : le test continue.</p>
          </div>
        )}
        {bt === undefined && <div className="flex justify-center py-6"><Spinner /></div>}
        {bt?.status === 'error' && <p className="text-sm text-bear">Le test a échoué : {bt.result?.error}</p>}
        {bt?.status === 'done' && bt.result?.variants && <Results r={bt.result} />}
        {bt === null && (
          <p className="flex gap-2 rounded-lg border border-dashed border-line p-3 text-sm text-muted">
            <FlaskConical className="h-4 w-4 shrink-0 text-bull" /> Choisis une liste et lance le test : le résultat reste affiché ici.
          </p>
        )}
      </div>
    </Modal>
  )
}
