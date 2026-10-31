import { useState } from 'react'
import { AlertOctagon, Check, CircleAlert, Minus, TrendingDown, TrendingUp } from 'lucide-react'
import { fmtScore, scoreColor } from '../lib/format'
import { Spinner } from './ui'
import { Notes } from './ScoreParts'

// Couleurs des trois composantes : palette catégorielle validée (fond sombre, daltonisme)
const PART_COLOR = { fundamental: '#3987e5', technical: '#d95926', sentiment: '#9085e9' }
const PARTS = [['fundamental', 'Fondamental', '35 %'], ['technical', 'Technique', '45 %'], ['sentiment', 'Sentiment', '20 %']]

const LEVEL_STYLE = {
  FAVORABLE: 'border-bull/50 bg-bull/10 text-bull',
  PRUDENCE: 'border-warn/50 bg-warn/10 text-warn',
  DEFAVORABLE: 'border-bear/50 bg-bear/10 text-bear',
}

const TABS = [
  { id: 'buy', label: 'ACHAT', icon: TrendingUp, active: 'border-bull text-bull' },
  { id: 'sell', label: 'VENTE', icon: TrendingDown, active: 'border-bear text-bear' },
]

function Tiles({ scores }) {
  return (
    <div className="grid grid-cols-3 gap-2 text-center">
      {PARTS.map(([key, label, weight]) => (
        <div key={key} className="rounded-lg bg-bg p-2.5">
          <p className="flex flex-col items-center gap-1 text-[10px] uppercase text-muted sm:flex-row sm:justify-center">
            <span className="inline-block h-2 w-2 shrink-0 rounded-sm" style={{ background: PART_COLOR[key] }} aria-hidden="true" />
            <span className="max-w-full truncate">{label}</span>
          </p>
          <p className={`mt-1 text-lg font-bold ${scores[key] != null ? scoreColor(scores[key]) : 'text-gray-500'}`}>
            {scores[key] === undefined ? <Spinner className="h-4 w-4" /> : `${fmtScore(scores[key])}/10`}
          </p>
          <p className="text-[10px] text-muted">poids {weight}</p>
        </div>
      ))}
    </div>
  )
}

// Barre empilée : contribution de chaque analyse au score global (sur 10)
function Composition({ components, total }) {
  const parts = components.filter((c) => c.contribution != null)
  return (
    <div className="mt-3">
      <div className="flex h-3 gap-0.5 overflow-hidden rounded-full bg-bg" role="img"
        aria-label={`Score global ${fmtScore(total)} sur 10 : ` + parts.map((c) => `${c.label} ${fmtScore(c.contribution)}`).join(', ')}>
        {parts.map((c) => (
          <div key={c.key} className="h-full" title={`${c.label} : ${fmtScore(c.contribution)} pt`}
            style={{ width: `${c.contribution * 10}%`, background: PART_COLOR[c.key] }} />
        ))}
      </div>
      <p className="mt-1.5 text-xs text-muted">
        {parts.map((c, i) => (
          <span key={c.key}>
            {i > 0 && ' + '}
            {c.label} {fmtScore(c.score)} × {Math.round(c.weight * 100)} %
          </span>
        ))}
        {' = '}<b className="text-gray-100">{fmtScore(total)}/10</b>
      </p>
    </div>
  )
}

function Arguments({ side }) {
  const rows = [
    ...side.pros.map((t) => ({ t, icon: Check, cls: 'text-bull', label: 'Point d\'appui' })),
    ...side.cons.map((t) => ({ t, icon: CircleAlert, cls: 'text-bear', label: 'Point de vigilance' })),
    ...side.neutral.map((t) => ({ t, icon: Minus, cls: 'text-muted', label: 'Neutre' })),
  ]
  if (!rows.length) return null
  return (
    <ul className="mt-3 space-y-1.5 text-sm">
      {rows.map(({ t, icon: Icon, cls, label }) => (
        <li key={t} className="flex gap-2">
          <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${cls}`} aria-label={label} />
          <span>{t}</span>
        </li>
      ))}
    </ul>
  )
}

function Verdict({ side, tab }) {
  return (
    <div className={`rounded-xl border p-4 ${LEVEL_STYLE[side.level]}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider opacity-80">
            {tab === 'buy' ? 'Décision à l\'achat' : 'Si vous détenez ce produit'}
          </p>
          <p className="mt-1 text-lg font-extrabold leading-tight">{side.icon} {side.label}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-3xl font-extrabold leading-none">{fmtScore(side.score)}</p>
          <p className="text-[11px] opacity-80">{tab === 'buy' ? 'score global' : 'score de vente'} /10</p>
        </div>
      </div>
      <p className="mt-2 text-sm text-gray-200">{side.summary}</p>
    </div>
  )
}

export default function DecisionPanel({ product, decision, loading, scores }) {
  const [tab, setTab] = useState('buy')
  const side = decision?.available ? decision[tab] : null

  return (
    <section className="card min-w-0 overflow-hidden" aria-label="Décision">
      <div className="flex border-b border-line" role="tablist">
        {TABS.map(({ id, label, icon: Icon, active }) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`flex flex-1 items-center justify-center gap-2 border-b-2 py-3 text-sm font-semibold tracking-wide transition
              ${tab === id ? active + ' bg-panel2' : 'border-transparent text-muted hover:text-gray-100'}`}
          >
            <Icon className="h-4 w-4" /> {label}
          </button>
        ))}
      </div>

      <div className="space-y-3 p-4 sm:p-5" role="tabpanel">
        {!product && (
          <div className="py-4 text-center text-sm text-muted">
            <p className="text-base text-gray-100">{tab === 'buy' ? 'Analyse à l\'achat' : 'Analyse à la vente'}</p>
            <p className="mt-1">
              Lance une recherche pour obtenir le score global /10, la position vs MM100, les stop-loss proposés et le rapport justificatif.
            </p>
          </div>
        )}

        {product && !side && (
          <div className="flex items-center gap-3 rounded-xl border border-line p-4 text-sm text-muted">
            {loading ? <><Spinner className="h-5 w-5" /> Calcul de la décision ({product.name})…</> : 'Décision indisponible pour ce produit.'}
          </div>
        )}

        {side && <Verdict side={side} tab={tab} />}

        {tab === 'buy' && side?.warning && (
          <p className="flex gap-2 rounded-lg border-2 border-bear bg-bear/10 p-3 text-sm font-medium text-bear" role="alert">
            <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0" /> {side.warning}
          </p>
        )}

        {product && <Tiles scores={scores} />}
        {side && <Composition components={decision.components} total={decision.score} />}
        {side && <Arguments side={side} />}
        {side && <Notes notes={decision.notes} />}
        {side && (
          <a href="/apprendre/lire-les-scores" target="_blank" rel="noopener" className="inline-block text-xs text-muted underline underline-offset-2 hover:text-gray-200">
            Comment lire ce score ?
          </a>
        )}

        {side && (
          <p className="border-t border-line pt-3 text-[11px] text-muted">
            Seuils : ≥ 7,5 conditions favorables · 5 à 7,4 prudence · &lt; 5 conditions défavorables.
            Aide à la décision automatisée — ne constitue pas un conseil en investissement (MiFID II).
          </p>
        )}
      </div>
    </section>
  )
}
