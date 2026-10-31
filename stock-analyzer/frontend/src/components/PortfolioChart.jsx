import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

// Palette catégorielle validée (fond sombre, daltonisme OK) : portefeuille bleu, repère orange
const C = { pf: '#3987e5', bench: '#d95926', grid: '#21262D', axis: '#8B949E', ref: '#8B949E' }
const EUR = new Intl.NumberFormat('fr-BE', { style: 'currency', currency: 'EUR' })
const EUR0 = new Intl.NumberFormat('fr-BE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })
const fmtDay = (d) => new Date(`${d}T12:00:00`).toLocaleDateString('fr-BE', { day: 'numeric', month: 'short' })
const pct = (v, base) => {
  const p = (v / base - 1) * 100
  return `${p > 0 ? '+' : p < 0 ? '−' : ''}${Math.abs(p).toFixed(2).replace('.', ',')} %`
}

function Swatch({ color }) {
  return (
    <svg width="14" height="4" aria-hidden="true" className="shrink-0">
      <line x1="0" y1="2" x2="14" y2="2" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

function ChartTooltip({ active, payload, initial, benchLabel }) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div className="rounded-lg border border-line bg-panel px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 font-semibold text-gray-100">{fmtDay(row.day)}</p>
      <div className="flex items-center justify-between gap-4">
        <span className="flex items-center gap-1.5 text-muted"><Swatch color={C.pf} /> Portefeuille</span>
        <span className="font-semibold text-gray-100">{EUR.format(row.value_eur)} <span className="font-normal text-muted">{pct(row.value_eur, initial)}</span></span>
      </div>
      {row.benchmark_eur != null && (
        <div className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-muted"><Swatch color={C.bench} /> {benchLabel}</span>
          <span className="font-semibold text-gray-100">{EUR.format(row.benchmark_eur)} <span className="font-normal text-muted">{pct(row.benchmark_eur, initial)}</span></span>
        </div>
      )}
    </div>
  )
}

export default function PortfolioChart({ history, initial, benchLabel }) {
  const rows = history.filter((h) => h.value_eur != null)
  const last = rows[rows.length - 1]
  const hasBench = rows.some((r) => r.benchmark_eur != null)
  const values = rows.flatMap((r) => [r.value_eur, r.benchmark_eur, initial]).filter((v) => v != null)
  const pad = Math.max((Math.max(...values) - Math.min(...values)) * 0.15, initial * 0.005)
  const domain = [Math.floor(Math.min(...values) - pad), Math.ceil(Math.max(...values) + pad)]
  const fewPoints = rows.length < 8

  return (
    <div>
      {/* Légende (2 séries) avec valeur actuelle de chacune */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <span className="flex items-center gap-1.5 text-muted">
          <Swatch color={C.pf} /> Portefeuille <b className="text-gray-100">{pct(last.value_eur, initial)}</b>
        </span>
        {hasBench && last.benchmark_eur != null && (
          <span className="flex items-center gap-1.5 text-muted">
            <Swatch color={C.bench} /> {benchLabel} (même somme) <b className="text-gray-100">{pct(last.benchmark_eur, initial)}</b>
          </span>
        )}
      </div>
      <div className="mt-2 h-48" role="img"
        aria-label={`Évolution de la valeur du portefeuille comparée à la même somme placée dans un ${benchLabel}`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis dataKey="day" tickFormatter={fmtDay} tick={{ fill: C.axis, fontSize: 10 }} axisLine={false} tickLine={false}
              minTickGap={24} />
            <YAxis domain={domain} orientation="right" width={58} tickFormatter={(v) => EUR0.format(v)}
              tick={{ fill: C.axis, fontSize: 10 }} axisLine={false} tickLine={false} />
            <ReferenceLine y={initial} stroke={C.ref} strokeOpacity={0.6} strokeDasharray="4 4"
              label={{ value: 'Capital de départ', fill: C.axis, fontSize: 10, position: 'insideBottomLeft' }} />
            <Tooltip content={<ChartTooltip initial={initial} benchLabel={benchLabel} />}
              cursor={{ stroke: C.axis, strokeWidth: 1 }} isAnimationActive={false} />
            {hasBench && (
              <Line dataKey="benchmark_eur" stroke={C.bench} strokeWidth={2} isAnimationActive={false} connectNulls
                dot={fewPoints ? { r: 4, fill: C.bench, stroke: '#161B22', strokeWidth: 2 } : false}
                activeDot={{ r: 5, stroke: '#161B22', strokeWidth: 2 }} />
            )}
            <Line dataKey="value_eur" stroke={C.pf} strokeWidth={2} isAnimationActive={false}
              dot={fewPoints ? { r: 4, fill: C.pf, stroke: '#161B22', strokeWidth: 2 } : false}
              activeDot={{ r: 5, stroke: '#161B22', strokeWidth: 2 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-1 text-xs text-muted">
        <summary className="cursor-pointer select-none">Voir les valeurs</summary>
        <table className="mt-2 w-full">
          <thead><tr className="text-left"><th className="py-1 font-medium">Jour</th><th className="py-1 text-right font-medium">Portefeuille</th>{hasBench && <th className="py-1 text-right font-medium">{benchLabel}</th>}</tr></thead>
          <tbody>
            {[...rows].reverse().slice(0, 60).map((r) => (
              <tr key={r.day} className="border-t border-line">
                <td className="py-1">{fmtDay(r.day)}</td>
                <td className="py-1 text-right text-gray-100">{EUR.format(r.value_eur)}</td>
                {hasBench && <td className="py-1 text-right text-gray-100">{r.benchmark_eur != null ? EUR.format(r.benchmark_eur) : '—'}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}
