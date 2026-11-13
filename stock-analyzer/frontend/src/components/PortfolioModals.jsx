import { lazy, Suspense, useEffect, useState } from 'react'
import { Globe2, PauseCircle, ShieldCheck, Trash2, Wallet } from 'lucide-react'
import { api } from '../lib/api'
import { useWatchlists } from '../lib/watchlists'
import { changeColor, fmtPct, fmtPrice } from '../lib/format'
import Modal from './Modal'
import ConfirmDialog from './ConfirmDialog'
import { Spinner } from './ui'

// Prévient la liste du menu qu'un portefeuille a changé
const PortfolioChart = lazy(() => import('./PortfolioChart'))

export const PORTFOLIOS_CHANGED = 'ab:portfolios-changed'
export const notifyPortfolios = () => window.dispatchEvent(new Event(PORTFOLIOS_CHANGED))

const EUR = new Intl.NumberFormat('fr-BE', { style: 'currency', currency: 'EUR' })
const eur = (v) => (v == null ? '—' : EUR.format(v))
const fmtDay = (sql) => {
  if (!sql) return '—'
  const d = new Date(sql.replace(' ', 'T') + (sql.length > 10 ? 'Z' : ''))
  return d.toLocaleString('fr-BE', { day: 'numeric', month: 'short', ...(sql.length > 10 ? { hour: '2-digit', minute: '2-digit' } : {}) })
}

export function NewPortfolioModal({ onClose, onCreated }) {
  const wl = useWatchlists()
  const [watchlistId, setWatchlistId] = useState(wl.selectedId || wl.watchlists[0]?.id || '')
  const [capital, setCapital] = useState(5000)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const body = watchlistId === 'all' ? { universe: 'all' }
        : watchlistId === 'turbo' ? { product: 'turbo' } : { watchlist_id: Number(watchlistId) }
      const { portfolio } = await api.createPortfolio({ ...body, capital: Number(capital) })
      notifyPortfolios()
      onCreated(portfolio.id)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <Modal title="Nouveau portefeuille fictif" onClose={onClose}>
      <form onSubmit={submit} className="mt-3 space-y-4">
        <p className="text-sm text-muted">
          Le programme achète et vend seul, avec de l'argent virtuel, dans la liste choisie. Aucun ordre réel n'est passé.
        </p>
        <label className="block text-sm font-medium">
          Où acheter
          <select className="input mt-2" value={watchlistId} required onChange={(e) => {
            setWatchlistId(e.target.value)
            if (e.target.value === 'turbo' && Number(capital) === 5000) setCapital(1000)
          }}>
            <option value="all">🌍 Opportunités : toutes les listes larges + opportunités du jour</option>
            <option value="turbo">⚡ Turbos Call (levier 2) sur les actions de Monde 500</option>
            {wl.watchlists.map((w) => <option key={w.id} value={w.id}>{w.name} ({w.item_count})</option>)}
          </select>
          {watchlistId === 'all' && (
            <span className="mt-1 block text-xs font-normal text-muted">
              Le programme choisit parmi plus de 1 000 titres : Monde 500 + cryptos, IPO 5 et 10 ans, et ~150 opportunités
              du jour (plus échangées, plus fortes hausses, croissance sous-évaluée…). Les listes manquantes sont ajoutées
              automatiquement à ton menu.
            </span>
          )}
          {watchlistId === 'turbo' && (
            <span className="mt-1 block text-xs font-normal text-warn">
              Turbos Call open-end (sans date limite), levier 2, 5 lignes au plus. Le levier double les gains… et les pertes :
              si l'action perd 50 %, le turbo est désactivé et ne vaut plus rien. Test sur 10 ans : ≈ +20 % par an, mais
              une pire chute de −41 % (biais : sociétés qui ont réussi, marché surtout haussier).
            </span>
          )}
        </label>
        <label className="block text-sm font-medium">
          Capital de départ (€)
          <input className="input mt-2" type="number" min="500" max="1000000" step="100" value={capital}
            onChange={(e) => setCapital(e.target.value)} required />
        </label>
        <Rules turbo={watchlistId === 'turbo'} />
        {error && <p className="text-sm text-bear" role="alert">{error}</p>}
        <button type="submit" className="btn-primary w-full" disabled={busy || !watchlistId}>
          {busy ? 'Création…' : <><Wallet className="h-4 w-4" /> Lancer la simulation</>}
        </button>
      </form>
    </Modal>
  )
}

function TurboRules() {
  return (
    <details className="rounded-lg bg-bg px-3 py-2 text-xs text-muted">
      <summary className="cursor-pointer select-none">Règles du portefeuille turbos</summary>
      <ul className="mt-2 list-disc space-y-1 pl-4">
        <li><b className="text-gray-200">Produit</b> : turbo Call open-end (sans date limite), levier 2 à l'achat. La barrière est à la moitié du cours de l'action : si l'action la touche, le turbo est désactivé et ne vaut plus rien.</li>
        <li><b className="text-gray-200">Achat</b> : actions de la liste Monde 500 au signal 🟢 ACHAT, au-dessus de leur moyenne 200 jours, meilleur score d'abord ; jusqu'à 5 lignes d'environ 20 % du portefeuille.</li>
        <li><b className="text-gray-200">Vente</b> : action 15 % sous son plus haut depuis l'achat (le turbo perd alors environ 30 %), tendance de fond baissière (sous une moyenne 200 jours qui baisse), ou barrière touchée.</li>
        <li><b className="text-gray-200">Filtre de marché</b> : aucun nouvel achat quand l'ETF MSCI World est sous sa MM100. Les ventes continuent.</li>
        <li><b className="text-gray-200">Pas de Put</b> : dans le test sur 10 ans, ajouter des turbos Put (même seulement sur les indices) faisait passer le résultat de ≈ +20 % à ≈ +8 % par an, avec une pire chute de −65 %.</li>
        <li><b className="text-gray-200">Frais</b> : 1 € par ordre (turbos Saxo), TOB 0,35 %, écart achat/vente de l'émetteur estimé à 0,25 %, coût de financement estimé à 3 % par an (la barrière monte un peu chaque jour).</li>
        <li>Simplifications : turbo calculé à partir du cours de l'action (parité 1, quantités fractionnées) ; les vrais turbos varient selon l'émetteur, et leur cours suit l'action en direct, nuit comprise pour les actions américaines.</li>
      </ul>
    </details>
  )
}

function Rules({ turbo = false }) {
  if (turbo) return <TurboRules />
  return (
    <details className="rounded-lg bg-bg px-3 py-2 text-xs text-muted">
      <summary className="cursor-pointer select-none">Règles du programme</summary>
      <ul className="mt-2 list-disc space-y-1 pl-4">
        <li><b className="text-gray-200">Achat</b> : produits au signal 🟢 ACHAT dont le cours est au-dessus de sa moyenne 200 jours, tout de suite (sans attendre de repli), meilleur score d'abord.</li>
        <li><b className="text-gray-200">Répartition</b> : jusqu'à 10 lignes d'environ 10 % du portefeuille, en actions entières (cryptos : quantités fractionnées).</li>
        <li><b className="text-gray-200">🔁 Rachats</b> : la société a réduit son nombre d'actions d'au moins 1 % par an sur 3 ans (elle rachète ses propres actions).</li>
        <li><b className="text-gray-200">Vente</b> : stop suiveur touché (15 % sous le plus haut atteint depuis l'achat : il monte avec le cours et protège les gains), ou tendance de fond baissière (cours sous une moyenne 200 jours qui baisse). Pas d'objectif de vente : on laisse courir les gains.</li>
        <li><b className="text-gray-200">Pourquoi ces règles</b> : retenues en novembre 2026 après un test sur 10 ans et ~100 grandes actions (menu → Tester la méthode sur le passé).</li>
        <li>Pas de rachat d'un titre vendu depuis moins de 5 jours.</li>
        <li><b className="text-gray-200">Filtre de marché</b> : aucun nouvel achat quand l'ETF MSCI World est sous sa MM100 (marché mondial baissier). Les ventes continuent.</li>
        <li>Frais réels Saxo (niveau Bronze) : courtage 0,08 % (minimum 2 € sur Euronext, 1 $ aux États-Unis…), change 0,25 % pour une devise, plus la TOB (0,35 % actions, 0,12 % ETF). Cours en dollars convertis en euros.</li>
        <li>Décisions prises à chaque mise à jour des cours : 15 min, toutes les 30 min selon les Bourses ouvertes pour la liste Monde, 1×/jour pour les listes IPO.</li>
        <li>Simplification : la simulation ignore les lots minimums (100 actions au Japon et à Hong Kong).</li>
      </ul>
    </details>
  )
}

function Stat({ label, value, className = '' }) {
  return (
    <div className="rounded-lg bg-bg p-2.5">
      <p className="text-[11px] text-muted">{label}</p>
      <p className={`text-sm font-semibold ${className}`}>{value}</p>
    </div>
  )
}

export function PortfolioModal({ id, onClose }) {
  const wl = useWatchlists()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [removing, setRemoving] = useState(false)

  const load = () => api.portfolio(id).then((r) => setData(r.portfolio)).catch((e) => setError(e.message))
  useEffect(() => {
    load()
    const t = setInterval(load, 60 * 1000)
    return () => clearInterval(t)
  }, [id])

  const p = data
  return (
    <Modal title={p ? p.name : 'Portefeuille fictif'} onClose={onClose}>
      {error && <p className="mt-3 text-sm text-bear">{error}</p>}
      {!p && !error && <div className="flex justify-center py-10"><Spinner /></div>}
      {p && (
        <div className="mt-3 space-y-4">
          <div className="rounded-lg border border-line p-3">
            <p className="text-xs text-muted">Valeur du portefeuille</p>
            <p className="text-2xl font-bold">{eur(p.value)}</p>
            <p className={`text-sm font-semibold ${changeColor(p.pnl_eur)}`}>
              {p.pnl_eur >= 0 ? '+' : ''}{eur(p.pnl_eur)} ({fmtPct(p.pnl_pct)}) depuis le {fmtDay(p.created_at)}
            </p>
            <p className="mt-1 text-xs text-muted">
              Capital de départ {eur(p.initial_cash)} · watchlist {p.watchlist ? `« ${p.watchlist.name} »` : 'supprimée'}
            </p>
          </div>
          {p.note && (
            <p className="flex gap-2 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn" role="status">
              <PauseCircle className="mt-0.5 h-4 w-4 shrink-0" /> {p.note}
            </p>
          )}
          {!p.note && p.regime?.available && (
            <p className="flex gap-2 text-xs text-muted">
              <ShieldCheck className="h-4 w-4 shrink-0 text-bull" />
              Filtre de marché : {p.regime.label} au-dessus de sa MM100 ({fmtPct(p.regime.distance_pct)}), achats autorisés.
            </p>
          )}

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Évolution vs {p.benchmark_label}</h3>
            {p.history.length >= 2 ? (
              <Suspense fallback={<div className="flex h-48 items-center justify-center"><Spinner /></div>}>
                <div className="mt-2"><PortfolioChart history={p.history} initial={p.initial_cash} benchLabel={p.benchmark_label} /></div>
              </Suspense>
            ) : (
              <p className="mt-2 rounded-lg border border-dashed border-line p-3 text-sm text-muted">
                La courbe apparaîtra dès le 2e jour de simulation : une valeur est enregistrée chaque jour, comparée à la
                même somme placée dans un {p.benchmark_label}.
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Liquidités" value={eur(p.cash)} />
            <Stat label="Investi" value={eur(p.invested)} />
            <Stat label="Gains réalisés" value={eur(p.stats.realized_eur)} className={changeColor(p.stats.realized_eur)} />
            <Stat label="Frais payés" value={eur(p.fees_paid)} />
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
              Lignes en portefeuille ({p.open_count}/{p.max_positions})
            </h3>
            {p.positions.length === 0 && (
              <p className="mt-2 rounded-lg border border-dashed border-line p-3 text-sm text-muted">
                Aucune ligne pour l'instant : le programme attend un produit au signal 🟢 ACHAT au-dessus de sa moyenne 200 jours.
                {p.last_run_at ? ` Dernière vérification : ${fmtDay(p.last_run_at)}.` : ' Première vérification en cours…'}
              </p>
            )}
            <ul className="mt-2 divide-y divide-line">
              {p.positions.map((x) => (
                <li key={x.id} className="py-2.5">
                  <button className="w-full text-left" onClick={() => { wl.analyze({ symbol: x.symbol, product_id: x.product_id }); onClose() }}>
                    <span className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate text-sm font-medium">
                        {x.name}
                        {x.buyback && <span className="ml-1.5 rounded-full bg-[#3987e5]/15 px-1.5 py-0.5 text-[10px] font-semibold text-[#7fb2f0]" title="Le nombre d'actions baisse depuis 3 ans : la société rachète ses actions">🔁 Rachats</span>}
                      </span>
                      <span className={`shrink-0 text-sm font-semibold ${changeColor(x.pnl_eur)}`}>{fmtPct(x.pnl_pct)}</span>
                    </span>
                    <span className="flex justify-between gap-2 text-xs text-muted">
                      {x.barrier != null ? (
                        <span>⚡ Turbo Call · {x.symbol} {fmtPrice(x.under_entry, x.currency)} → {fmtPrice(x.under_last ?? x.under_entry, x.currency)}</span>
                      ) : (
                        <span>{x.symbol} · {x.qty} × {fmtPrice(x.entry_price, x.currency)} → {fmtPrice(x.last_price, x.currency)}</span>
                      )}
                      <span className={changeColor(x.pnl_eur)}>{x.pnl_eur >= 0 ? '+' : ''}{eur(x.pnl_eur)}</span>
                    </span>
                    <span className="mt-0.5 block text-[11px]">
                      <span className="text-bear">Stop {fmtPrice(x.stop, x.currency)}</span>
                      <span className="text-muted"> · </span>
                      {x.barrier != null
                        ? <span className="text-warn">Barrière {fmtPrice(x.barrier, x.currency)}</span>
                        : <span className="text-warn">Objectif {fmtPrice(x.target, x.currency)}</span>}
                      <span className="text-muted"> · acheté le {fmtDay(x.entry_at)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {p.trades.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
                Ventes ({p.stats.wins} gagnante{p.stats.wins > 1 ? 's' : ''} sur {p.stats.closed})
              </h3>
              <ul className="mt-2 divide-y divide-line">
                {p.trades.map((t) => (
                  <li key={t.id} className="py-2 text-sm">
                    <span className="flex justify-between gap-2">
                      <span className="min-w-0 truncate">{t.name}</span>
                      <span className={`shrink-0 font-semibold ${changeColor(t.pnl_eur)}`}>
                        {t.pnl_eur >= 0 ? '+' : ''}{eur(t.pnl_eur)} ({fmtPct(t.pnl_pct)})
                      </span>
                    </span>
                    <span className="block text-xs text-muted">
                      {t.symbol} · {fmtDay(t.entry_at)} → {fmtDay(t.exit_at)} · {t.exit_reason}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <Rules turbo={p.product === 'turbo'} />
          {p.can_publish && (
            <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-line p-3 text-sm">
              <input type="checkbox" className="mt-1 h-4 w-4 accent-[#00FF88]" checked={!!p.is_public}
                onChange={async (e) => {
                  const next = e.target.checked
                  setData({ ...p, is_public: next })
                  try { await api.setPortfolioPublic(id, next) } catch { setData({ ...p }) }
                }} />
              <span>
                <span className="flex items-center gap-1.5 font-medium"><Globe2 className="h-4 w-4" /> Montrer sur le site public</span>
                <span className="block text-xs text-muted">
                  Devient le « portefeuille témoin » de la page <a href="/portefeuille-temoin" target="_blank" rel="noreferrer" className="text-bull underline">/portefeuille-temoin</a> :
                  performance, lignes et ventes, sans ton nom ni ton adresse. Un seul portefeuille à la fois.
                </span>
              </span>
            </label>
          )}
          <p className="text-[11px] text-muted">
            Simulation sur les derniers cours connus, sans ordre réel. Les résultats passés ne préjugent pas des résultats
            futurs. Pas un conseil en investissement.
          </p>
          <button className="btn-ghost w-full justify-center border border-bear/40 text-bear" onClick={() => setRemoving(true)}>
            <Trash2 className="h-4 w-4" /> Supprimer ce portefeuille
          </button>
        </div>
      )}
      {removing && (
        <ConfirmDialog
          title="Supprimer le portefeuille"
          message={`Supprimer « ${p.name} » ?`}
          detail="La simulation et tout son historique seront effacés. Tes watchlists ne sont pas touchées."
          confirmLabel="Supprimer"
          onConfirm={async () => { await api.deletePortfolio(id); notifyPortfolios(); onClose() }}
          onClose={() => setRemoving(false)}
        />
      )}
    </Modal>
  )
}
