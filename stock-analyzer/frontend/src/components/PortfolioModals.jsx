import { useEffect, useState } from 'react'
import { Trash2, Wallet } from 'lucide-react'
import { api } from '../lib/api'
import { useWatchlists } from '../lib/watchlists'
import { changeColor, fmtPct, fmtPrice } from '../lib/format'
import Modal from './Modal'
import ConfirmDialog from './ConfirmDialog'
import { Spinner } from './ui'

// Prévient la liste du menu qu'un portefeuille a changé
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
      const { portfolio } = await api.createPortfolio({ watchlist_id: Number(watchlistId), capital: Number(capital) })
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
          Le programme achète et vend seul, avec de l'argent virtuel, dans la watchlist choisie. Aucun ordre réel n'est passé.
        </p>
        <label className="block text-sm font-medium">
          Watchlist où acheter
          <select className="input mt-2" value={watchlistId} onChange={(e) => setWatchlistId(e.target.value)} required>
            {wl.watchlists.map((w) => <option key={w.id} value={w.id}>{w.name} ({w.item_count})</option>)}
          </select>
        </label>
        <label className="block text-sm font-medium">
          Capital de départ (€)
          <input className="input mt-2" type="number" min="500" max="1000000" step="100" value={capital}
            onChange={(e) => setCapital(e.target.value)} required />
        </label>
        <Rules />
        {error && <p className="text-sm text-bear" role="alert">{error}</p>}
        <button type="submit" className="btn-primary w-full" disabled={busy || !watchlistId}>
          {busy ? 'Création…' : <><Wallet className="h-4 w-4" /> Lancer la simulation</>}
        </button>
      </form>
    </Modal>
  )
}

function Rules() {
  return (
    <details className="rounded-lg bg-bg px-3 py-2 text-xs text-muted">
      <summary className="cursor-pointer select-none">Règles du programme</summary>
      <ul className="mt-2 list-disc space-y-1 pl-4">
        <li><b className="text-gray-200">Achat</b> : produits au signal 🟢 ACHAT dont le cours est dans la zone d'achat affichée, meilleur score d'abord.</li>
        <li><b className="text-gray-200">Répartition</b> : jusqu'à 10 lignes d'environ 10 % du portefeuille, en actions entières (cryptos : quantités fractionnées).</li>
        <li><b className="text-gray-200">Vente</b> : objectif atteint, stop-loss touché (le stop monte avec le cours pour protéger les gains), ou signal passé à 🔴 VENTE.</li>
        <li>Pas de rachat d'un titre vendu depuis moins de 5 jours.</li>
        <li>Frais estimés : 0,1 % par ordre (1 € minimum). Cours en dollars convertis en euros.</li>
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
                Aucune ligne pour l'instant : le programme attend un produit au signal 🟢 ACHAT dans sa zone d'achat.
                {p.last_run_at ? ` Dernière vérification : ${fmtDay(p.last_run_at)}.` : ' Première vérification en cours…'}
              </p>
            )}
            <ul className="mt-2 divide-y divide-line">
              {p.positions.map((x) => (
                <li key={x.id} className="py-2.5">
                  <button className="w-full text-left" onClick={() => { wl.analyze({ symbol: x.symbol, product_id: x.product_id }); onClose() }}>
                    <span className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate text-sm font-medium">{x.name}</span>
                      <span className={`shrink-0 text-sm font-semibold ${changeColor(x.pnl_eur)}`}>{fmtPct(x.pnl_pct)}</span>
                    </span>
                    <span className="flex justify-between gap-2 text-xs text-muted">
                      <span>{x.symbol} · {x.qty} × {fmtPrice(x.entry_price, x.currency)} → {fmtPrice(x.last_price, x.currency)}</span>
                      <span className={changeColor(x.pnl_eur)}>{x.pnl_eur >= 0 ? '+' : ''}{eur(x.pnl_eur)}</span>
                    </span>
                    <span className="mt-0.5 block text-[11px]">
                      <span className="text-bear">Stop {fmtPrice(x.stop, x.currency)}</span>
                      <span className="text-muted"> · </span>
                      <span className="text-warn">Objectif {fmtPrice(x.target, x.currency)}</span>
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

          <Rules />
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
