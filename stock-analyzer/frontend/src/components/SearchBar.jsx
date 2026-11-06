import { useEffect, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'
import { api } from '../lib/api'
import { changeColor, fmtPct } from '../lib/format'
import { Spinner } from './ui'
import TypeBadge from './TypeBadge'

const KIND_LABELS = { isin: 'Code ISIN', ticker: 'Ticker', nom: 'Nom / mot-clé' }

// Champ unique : nom, ticker, ISIN ou mot-clé, avec propositions pendant la saisie.
export default function SearchBar({ onAnalyze, busy }) {
  const [q, setQ] = useState('')
  const [suggest, setSuggest] = useState(null) // { query_kind, candidates }
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const boxRef = useRef(null)
  const inputRef = useRef(null)

  // Propositions avec un délai (on n'interroge pas le serveur à chaque lettre)
  useEffect(() => {
    const query = q.trim()
    if (query.length < 2) { setSuggest(null); setLoading(false); return }
    const ctrl = new AbortController()
    const t = setTimeout(async () => {
      setLoading(true)
      try {
        setSuggest(await api.search(query, ctrl.signal))
        setActive(-1)
      } catch (e) {
        if (e.name !== 'AbortError') setSuggest({ query, candidates: [], error: e.message })
      } finally {
        if (!ctrl.signal.aborted) setLoading(false)
      }
    }, 400)
    return () => { clearTimeout(t); ctrl.abort() }
  }, [q])

  // Fermer la liste quand on touche ailleurs
  useEffect(() => {
    const close = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])

  const norm = (v) => v.trim().split(/\s+/).join(' ').toLowerCase()
  // Les propositions affichées correspondent-elles bien au texte actuel ?
  const fresh = !!suggest && norm(suggest.query || '') === norm(q)
  const candidates = fresh ? suggest.candidates || [] : []

  const choose = (c) => {
    setOpen(false)
    inputRef.current?.blur()
    onAnalyze(q.trim(), c)
  }

  const submit = (e) => {
    e.preventDefault()
    if (!q.trim()) return
    if (fresh && active >= 0 && candidates[active]) return choose(candidates[active])
    setOpen(false)
    inputRef.current?.blur()
    onAnalyze(q.trim(), null)
  }

  const onKeyDown = (e) => {
    if (!open || !candidates.length) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => (i + 1) % candidates.length) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => (i <= 0 ? candidates.length - 1 : i - 1)) }
    else if (e.key === 'Escape') setOpen(false)
  }

  const showList = open && q.trim().length >= 2 && (loading || suggest)

  return (
    <div ref={boxRef} className="relative">
      <form onSubmit={submit} role="search">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input
          ref={inputRef}
          className="input py-3 pl-10 pr-28"
          placeholder="Nom, ticker ou ISIN (ex. ServiceNow)"
          value={q}
          onChange={(e) => { setQ(e.target.value); setActive(-1); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          enterKeyHint="search"
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          aria-label="Rechercher un produit"
          aria-expanded={!!showList}
          aria-controls="search-suggestions"
        />
        {q && (
          <button
            type="button"
            className="absolute right-[5.5rem] top-1/2 -translate-y-1/2 p-1.5 text-muted hover:text-gray-100"
            onClick={() => { setQ(''); setSuggest(null); inputRef.current?.focus() }}
            aria-label="Effacer"
          >
            <X className="h-4 w-4" />
          </button>
        )}
        <button
          type="submit"
          className="btn-primary absolute right-1.5 top-1/2 -translate-y-1/2 px-3 py-1.5 text-sm"
          disabled={busy || !q.trim()}
        >
          {busy ? <Spinner className="h-4 w-4" /> : 'Analyser'}
        </button>
      </form>

      {showList && (
        <div
          id="search-suggestions"
          className="absolute inset-x-0 top-full z-30 mt-1 max-h-[60vh] overflow-y-auto rounded-xl border border-line bg-panel shadow-2xl"
        >
          <div className="flex items-center justify-between border-b border-line px-3 py-2 text-xs text-muted">
            <span>{fresh && suggest.query_kind ? `Détecté : ${KIND_LABELS[suggest.query_kind]}` : 'Recherche…'}</span>
            {loading && <Spinner className="h-3.5 w-3.5" />}
          </div>
          {fresh && suggest.error && <p className="px-3 py-3 text-sm text-bear">{suggest.error}</p>}
          {!loading && fresh && !suggest.error && candidates.length === 0 && (
            <p className="px-3 py-3 text-sm text-muted">Aucun produit trouvé.</p>
          )}
          <ul role="listbox">
            {candidates.map((c, i) => (
              <li key={c.id} role="option" aria-selected={i === active}>
                <button
                  type="button"
                  onClick={() => choose(c)}
                  onMouseEnter={() => setActive(i)}
                  className={`flex w-full items-center gap-3 px-3 py-2.5 text-left transition ${i === active ? 'bg-panel2' : ''}`}
                >
                  <TypeBadge type={c.type} label={c.type_label} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm">{c.name}</span>
                    <span className="block truncate text-xs text-muted">
                      {[c.symbol, c.isin, c.exchange].filter(Boolean).join(' · ') || c.source}
                    </span>
                  </span>
                  {c.change_pct != null && (
                    <span className={`shrink-0 text-xs font-medium ${changeColor(c.change_pct)}`}>{fmtPct(c.change_pct)}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
