import { useEffect, useRef, useState } from 'react'
import { Briefcase, ChevronDown, Plus, Receipt, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { changeColor, fmtPct, fmtPrice } from '../lib/format'
import Modal from './Modal'
import ConfirmDialog from './ConfirmDialog'
import { Spinner } from './ui'

const EUR = new Intl.NumberFormat('fr-BE', { style: 'currency', currency: 'EUR' })
const eur = (v) => (v == null ? '—' : EUR.format(v))
const signed = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${EUR.format(v)}`)
const qtyFmt = (v) => new Intl.NumberFormat('fr-BE', { maximumFractionDigits: 6 }).format(v)
const dayFmt = (d) => new Date(`${d}T12:00:00`).toLocaleDateString('fr-BE', { day: 'numeric', month: 'short', year: 'numeric' })
const today = () => new Date().toISOString().slice(0, 10)

// Bilan fiscal de l'année : plus-values réalisées face à la franchise
function TaxCard({ years }) {
  const [showAll, setShowAll] = useState(false)
  const year = new Date().getFullYear()
  const cur = years.find((y) => y.year === year) || years[years.length - 1]
  if (!cur) return null
  const used = Math.max(0, Math.min(1, cur.net / cur.franchise))
  const others = years.filter((y) => y !== cur && y.sales > 0)
  return (
    <div className="rounded-lg border border-line p-3">
      <p className="flex items-center gap-1.5 text-sm font-semibold"><Receipt className="h-4 w-4" /> Taxe sur les plus-values {cur.year}</p>
      <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
        <div><p className="text-xs text-muted">Plus-values réalisées</p><p className="font-semibold text-bull">{eur(cur.gains)}</p></div>
        <div><p className="text-xs text-muted">Moins-values</p><p className="font-semibold text-bear">{eur(cur.losses)}</p></div>
      </div>
      <div className="mt-3">
        <div className="flex justify-between text-xs text-muted">
          <span>Net {eur(cur.net)}</span><span>Franchise {eur(cur.franchise)}{cur.carry > 0 ? ` (dont ${eur(cur.carry)} reportés)` : ''}</span>
        </div>
        <div className="mt-1 h-2 overflow-hidden rounded-full bg-bg" role="progressbar" aria-valuenow={Math.round(used * 100)} aria-valuemin={0} aria-valuemax={100}>
          <div className={`h-full rounded-full ${cur.taxable > 0 ? 'bg-bear' : 'bg-bull'}`} style={{ width: `${used * 100}%` }} />
        </div>
        <p className="mt-1.5 text-sm">
          {cur.taxable > 0
            ? <>Taxe estimée : <b className="text-bear">{eur(cur.tax)}</b> (10 % de {eur(cur.taxable)})</>
            : <>Encore <b className="text-bull">{eur(cur.franchise_left)}</b> de plus-values sans taxe cette année.</>}
        </p>
      </div>
      {others.length > 0 && (
        <button className="mt-2 text-xs text-muted underline-offset-2 hover:underline" onClick={() => setShowAll(!showAll)}>
          {showAll ? 'Masquer' : 'Voir'} les autres années
        </button>
      )}
      {showAll && others.map((y) => (
        <p key={y.year} className="mt-1 text-xs text-muted">{y.year} : net {eur(y.net)} · taxe estimée {eur(y.tax)}</p>
      ))}
      <p className="mt-2 text-[11px] leading-relaxed text-muted">
        Estimation selon les règles connues en 2026 : FIFO, valeur au 31/12/2025 pour les titres plus anciens, frais non
        déductibles. Ton courtier belge (Saxo) retient en principe 10 % à chaque vente sans tenir compte de la franchise :
        le trop-payé se récupère via ta déclaration. À vérifier avec le SPF Finances ou un comptable.
      </p>
    </div>
  )
}

function RefEditor({ position, onSaved }) {
  const [value, setValue] = useState(position.ref_price != null ? String(Math.round(position.ref_price * 100) / 100).replace('.', ',') : '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const save = async () => {
    setBusy(true)
    setError(null)
    try { onSaved(await api.setHoldingRef({ product_id: position.product_id, ref_price: Number(String(value).replace(',', '.')), currency: position.currency })) }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return (
    <div className="mt-2 rounded-md bg-bg p-2 text-xs">
      <p className={position.ref_missing ? 'text-warn' : 'text-muted'}>
        {qtyFmt(position.pre2026_qty)} titre(s) achetés avant 2026 : la taxe part de leur cours au 31/12/2025
        {position.ref_missing ? ' (introuvable automatiquement : indique-le).' : '.'}
      </p>
      <div className="mt-1.5 flex gap-2">
        <input className="input py-1.5 text-sm" inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)}
          aria-label="Cours au 31/12/2025" placeholder={`Cours au 31/12/2025 (${position.currency})`} />
        <button className="btn-ghost shrink-0 border border-line text-xs" onClick={save} disabled={busy || !value}>{busy ? '…' : 'Enregistrer'}</button>
      </div>
      {error && <p className="mt-1 text-bear">{error}</p>}
    </div>
  )
}

function Position({ p, onSell, onChanged }) {
  const [open, setOpen] = useState(false)
  const near = p.price && p.stop_price && p.price <= p.stop_price * 1.03
  return (
    <li className="py-2.5">
      <button className="w-full text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="flex items-center justify-between gap-2">
          <span className="min-w-0 truncate text-sm font-medium">{p.name}</span>
          <span className={`shrink-0 text-sm font-semibold ${changeColor(p.pnl_eur)}`}>{p.pnl_pct != null ? fmtPct(p.pnl_pct) : '—'}</span>
        </span>
        <span className="flex justify-between gap-2 text-xs text-muted">
          <span>{qtyFmt(p.qty)} × {fmtPrice(p.price, p.currency)} · {eur(p.value_eur)}</span>
          <span className={changeColor(p.pnl_eur)}>{signed(p.pnl_eur)}</span>
        </span>
        {(p.stop_price || p.sell_price) && (
          <span className="mt-0.5 block text-[11px]">
            {p.stop_price && <span className={near ? 'font-semibold text-bear' : 'text-bear'}>{near ? '⚠️ ' : ''}Stop {fmtPrice(p.stop_price, p.currency)}</span>}
            {p.stop_price && p.sell_price && <span className="text-muted"> · </span>}
            {p.sell_price && <span className="text-warn">Objectif {fmtPrice(p.sell_price, p.currency)}</span>}
            <ChevronDown className={`ml-1 inline h-3 w-3 text-muted transition ${open ? 'rotate-180' : ''}`} />
          </span>
        )}
      </button>
      {open && (
        <div className="mt-2 space-y-1 text-xs text-muted">
          <p>Prix de revient moyen : {fmtPrice(p.avg_price, p.currency)} · investi {eur(p.cost_eur)} · frais {eur(p.fees_eur)}</p>
          <p>Plus-value imposable si tu vendais tout aujourd'hui : <b className={changeColor(p.tax_gain_eur)}>{signed(p.tax_gain_eur)}</b></p>
          {p.realized_eur !== 0 && <p>Déjà réalisé sur ce titre : {signed(p.realized_eur)}</p>}
          {p.pre2026_qty > 0 && <RefEditor position={p} onSaved={onChanged} />}
          <button className="btn-ghost mt-1 border border-line text-xs" onClick={() => onSell(p)}>Encoder une vente</button>
        </div>
      )}
    </li>
  )
}

// Encodage d'un achat (recherche du titre) ou d'une vente (parmi les positions)
function TxForm({ positions, preset, onDone, onCancel }) {
  const [kind, setKind] = useState(preset ? 'SELL' : 'BUY')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [product, setProduct] = useState(preset ? { id: preset.product_id, symbol: preset.symbol, name: preset.name, currency: preset.currency } : null)
  const [form, setForm] = useState({ day: today(), qty: preset ? String(preset.qty) : '', price: '', fees: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const timer = useRef(null)

  useEffect(() => {
    if (kind !== 'BUY' || product || query.trim().length < 2) { setResults([]); return undefined }
    clearTimeout(timer.current)
    const ctrl = new AbortController()
    timer.current = setTimeout(() => api.search(query.trim(), ctrl.signal).then((r) => setResults(r.candidates || [])).catch(() => {}), 300)
    return () => { clearTimeout(timer.current); ctrl.abort() }
  }, [query, kind, product])

  const pick = async (c) => {
    setResults([])
    setProduct({ id: c.id, symbol: c.symbol, name: c.name, currency: null })
    try {
      const q = await api.quote(c.id)
      setProduct({ id: c.id, symbol: q.product.symbol || c.symbol, name: q.product.name || c.name, currency: q.product.currency || 'EUR' })
      if (q.quote?.price) setForm((f) => ({ ...f, price: String(q.quote.price) }))
    } catch { setProduct((p) => ({ ...p, currency: 'EUR' })) }
  }
  const num = (v) => Number(String(v).replace(',', '.'))
  const submit = async (e) => {
    e.preventDefault()
    if (!product?.id) return setError('Choisis un titre.')
    setBusy(true)
    setError(null)
    try {
      const r = await api.addHoldingTx({
        product_id: product.id, symbol: product.symbol, name: product.name, currency: product.currency || 'EUR',
        kind, day: form.day, qty: num(form.qty), price: num(form.price), fees_eur: form.fees ? num(form.fees) : 0,
      })
      onDone(r)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-line p-3">
      <div className="grid grid-cols-2 gap-1 rounded-lg bg-bg p-1 text-sm" role="radiogroup" aria-label="Type d'opération">
        {[['BUY', 'Achat'], ['SELL', 'Vente']].map(([k, l]) => (
          <button key={k} type="button" role="radio" aria-checked={kind === k} disabled={!!preset}
            className={`rounded-md py-1.5 ${kind === k ? 'bg-panel font-semibold text-gray-100' : 'text-muted'}`}
            onClick={() => { setKind(k); setProduct(null); setQuery('') }}>{l}</button>
        ))}
      </div>
      {kind === 'BUY' && !product && (
        <div>
          <label className="block text-sm font-medium" htmlFor="h-search">Titre</label>
          <input id="h-search" className="input mt-1" placeholder="Nom, ticker ou ISIN" value={query} onChange={(e) => setQuery(e.target.value)} autoComplete="off" />
          {results.length > 0 && (
            <ul className="mt-1 max-h-48 overflow-y-auto rounded-lg border border-line">
              {results.map((c) => (
                <li key={c.id}><button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-panel2" onClick={() => pick(c)}>
                  {c.name} <span className="text-xs text-muted">{c.symbol} · {c.exchange}</span>
                </button></li>
              ))}
            </ul>
          )}
        </div>
      )}
      {kind === 'SELL' && !product && (
        <div>
          <label className="block text-sm font-medium" htmlFor="h-pos">Titre vendu</label>
          <select id="h-pos" className="input mt-1" defaultValue="" onChange={(e) => {
            const p = positions.find((x) => x.product_id === e.target.value)
            if (p) { setProduct({ id: p.product_id, symbol: p.symbol, name: p.name, currency: p.currency }); setForm((f) => ({ ...f, qty: String(p.qty), price: p.price ? String(p.price) : '' })) }
          }}>
            <option value="" disabled>Choisir…</option>
            {positions.map((p) => <option key={p.product_id} value={p.product_id}>{p.name} ({qtyFmt(p.qty)})</option>)}
          </select>
        </div>
      )}
      {product && (
        <p className="flex items-center justify-between gap-2 rounded-md bg-bg px-3 py-2 text-sm">
          <span className="min-w-0 truncate"><b>{product.name}</b> <span className="text-xs text-muted">{product.symbol} · {product.currency || '…'}</span></span>
          {!preset && <button type="button" className="shrink-0 text-xs text-muted underline" onClick={() => setProduct(null)}>changer</button>}
        </p>
      )}
      <div className="grid grid-cols-2 gap-2">
        <label className="text-sm font-medium">Date<input type="date" className="input mt-1" value={form.day} max={today()} onChange={set('day')} required /></label>
        <label className="text-sm font-medium">Quantité<input className="input mt-1" inputMode="decimal" value={form.qty} onChange={set('qty')} required /></label>
        <label className="text-sm font-medium">Prix unitaire {product?.currency ? `(${product.currency})` : ''}<input className="input mt-1" inputMode="decimal" value={form.price} onChange={set('price')} required /></label>
        <label className="text-sm font-medium">Frais en € <span className="font-normal text-muted">(courtage + TOB)</span><input className="input mt-1" inputMode="decimal" value={form.fees} onChange={set('fees')} placeholder="0" /></label>
      </div>
      {product?.currency && product.currency !== 'EUR' && <p className="text-xs text-muted">Conversion en euros au cours de change de cette date, automatiquement.</p>}
      {error && <p className="text-sm text-bear" role="alert">{error}</p>}
      <div className="flex gap-2">
        <button type="button" className="btn-ghost flex-1 justify-center border border-line" onClick={onCancel}>Annuler</button>
        <button type="submit" className="btn-primary flex-1" disabled={busy || !product?.currency}>{busy ? 'Enregistrement…' : 'Enregistrer'}</button>
      </div>
    </form>
  )
}

// Mes vraies positions : saisie manuelle, suivi, taxe sur les plus-values (privé)
export default function HoldingsModal({ onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [adding, setAdding] = useState(null) // null | 'new' | position (vente)
  const [removing, setRemoving] = useState(null)
  const [showTx, setShowTx] = useState(false)

  const load = () => api.holdings().then(setData).catch((e) => setError(e.message))
  useEffect(() => {
    load()
    const t = setInterval(load, 60 * 1000)
    return () => clearInterval(t)
  }, [])

  const t = data?.totals
  return (
    <Modal title="Mes positions" onClose={onClose}>
      {error && <p className="mt-3 text-sm text-bear">{error}</p>}
      {!data && !error && <div className="flex justify-center py-10"><Spinner /></div>}
      {data && (
        <div className="mt-3 space-y-4">
          <p className="text-xs text-muted">Tes vrais placements, encodés à la main. Visible par toi seul ; rien n'est relié à ton compte Saxo.</p>
          {data.positions.length > 0 && (
            <div className="rounded-lg border border-line p-3">
              <p className="text-xs text-muted">Valeur actuelle</p>
              <p className="text-2xl font-bold">{eur(t.value_eur)}</p>
              <p className={`text-sm font-semibold ${changeColor(t.pnl_eur)}`}>{signed(t.pnl_eur)} (frais compris) · investi {eur(t.cost_eur)}</p>
              {t.missing_quotes > 0 && <p className="mt-1 text-xs text-muted">Cours en cours de mise à jour pour {t.missing_quotes} titre(s)…</p>}
            </div>
          )}
          {data.years.length > 0 && <TaxCard years={data.years} />}
          {data.problems.map((m) => <p key={m} className="rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">{m}</p>)}

          {adding ? (
            <TxForm positions={data.positions} preset={adding === 'new' ? null : adding}
              onCancel={() => setAdding(null)} onDone={(r) => { setData(r); setAdding(null) }} />
          ) : (
            <button className="btn-primary w-full" onClick={() => setAdding('new')}><Plus className="h-4 w-4" /> Encoder un achat ou une vente</button>
          )}

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Lignes ({data.positions.length})</h3>
            {data.positions.length === 0 ? (
              <p className="mt-2 rounded-lg border border-dashed border-line p-3 text-sm text-muted">
                <Briefcase className="mb-1 h-4 w-4 text-bull" />
                Encode tes achats (date, quantité, prix, frais) depuis tes avis d'exécution Saxo. L'outil suit ensuite la
                valeur, le stop-loss et l'objectif de chaque ligne, te prévient s'ils approchent, et estime ta taxe sur les plus-values.
              </p>
            ) : (
              <ul className="divide-y divide-line">
                {data.positions.map((p) => <Position key={p.product_id} p={p} onSell={setAdding} onChanged={setData} />)}
              </ul>
            )}
          </div>

          {data.transactions.length > 0 && (
            <div>
              <button className="flex w-full items-center justify-between text-xs font-semibold uppercase tracking-wider text-muted" onClick={() => setShowTx(!showTx)}>
                Opérations ({data.transactions.length}) <ChevronDown className={`h-4 w-4 transition ${showTx ? 'rotate-180' : ''}`} />
              </button>
              {showTx && (
                <ul className="mt-2 divide-y divide-line">
                  {data.transactions.map((x) => {
                    const gain = data.realized.filter((r) => r.tx_id === x.id).reduce((a, r) => a + r.gain, 0)
                    return (
                      <li key={x.id} className="flex items-center gap-2 py-2 text-sm">
                        <span className="min-w-0 flex-1">
                          <span className="block truncate"><b className={x.kind === 'BUY' ? 'text-bull' : 'text-warn'}>{x.kind === 'BUY' ? 'Achat' : 'Vente'}</b> {x.name}</span>
                          <span className="block text-xs text-muted">
                            {dayFmt(x.day)} · {qtyFmt(x.qty)} × {fmtPrice(x.price, x.currency)}{x.fees_eur ? ` · frais ${eur(x.fees_eur)}` : ''}
                            {x.kind === 'SELL' && x.day >= '2026-01-01' ? ` · plus-value fiscale ${signed(gain)}` : ''}
                          </span>
                        </span>
                        <button className="shrink-0 rounded-md p-2 text-muted hover:bg-bear/10 hover:text-bear" onClick={() => setRemoving(x)} aria-label="Supprimer l'opération">
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          )}
          <p className="text-[11px] text-muted">
            Alertes (mail et notification) quand une ligne approche de son stop-loss ou atteint son objectif. Rien n'est vendu
            automatiquement. Pas un conseil en investissement ni un conseil fiscal.
          </p>
        </div>
      )}
      {removing && (
        <ConfirmDialog
          title="Supprimer l'opération"
          message={`Supprimer ${removing.kind === 'BUY' ? "l'achat" : 'la vente'} de ${removing.name} du ${dayFmt(removing.day)} ?`}
          confirmLabel="Supprimer"
          onConfirm={async () => { setData(await api.deleteHoldingTx(removing.id)) }}
          onClose={() => setRemoving(null)}
        />
      )}
    </Modal>
  )
}
