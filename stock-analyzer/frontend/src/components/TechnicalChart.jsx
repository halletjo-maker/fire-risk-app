import { useMemo, useState } from 'react'
import {
  Bar, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { fmtNumber } from '../lib/format'

// Couleurs : bougies = haussier/baissier de l'app ; moyennes = palette catégorielle validée
// (fond sombre, daltonisme OK) — MM50 bleu, MM100 orange (critère principal), MM200 violet.
const C = {
  bull: '#00FF88', bear: '#FF4444', m50: '#3987e5', m100: '#d95926', m200: '#9085e9',
  grid: '#21262D', axis: '#8B949E', band: '#8B949E', macd: '#3987e5', sig: '#d95926', rsi: '#9085e9',
}
const PERIODS = [['3M', 63], ['6M', 126], ['1A', 260]]
const SYNC = 'technique'

const fmtDate = (t) => new Date(t).toLocaleDateString('fr-BE', { month: 'short', year: '2-digit' })
const fmtDay = (t) => new Date(t).toLocaleDateString('fr-BE', { day: 'numeric', month: 'short', year: 'numeric' })

// Bougie dessinée dans la plage [bas, haut] fournie par Recharts
function Candle({ x, y, width, height, payload }) {
  if (!payload || payload.open == null || payload.high == null || payload.low == null) return null
  const { open, close, high, low } = payload
  const range = high - low || 1
  const toY = (p) => y + ((high - p) / range) * height
  const color = close >= open ? C.bull : C.bear
  const bodyTop = toY(Math.max(open, close))
  const bodyH = Math.max(1, Math.abs(toY(open) - toY(close)))
  const w = Math.max(1, Math.min(width * 0.7, 8))
  const cx = x + width / 2
  return (
    <g>
      <line x1={cx} x2={cx} y1={y} y2={y + height} stroke={color} strokeWidth={1} />
      <rect x={cx - w / 2} y={bodyTop} width={w} height={bodyH} fill={color} rx={1} />
    </g>
  )
}

function Row({ color, label, value, dashed }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="flex items-center gap-1.5 text-muted">
        {color && (
          <svg width="12" height="4" aria-hidden="true">
            <line x1="0" y1="2" x2="12" y2="2" stroke={color} strokeWidth="2" strokeDasharray={dashed ? '3 2' : undefined} />
          </svg>
        )}
        {label}
      </span>
      <span className="font-semibold text-gray-100">{value}</span>
    </div>
  )
}

function PriceTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  const n = (v) => (v == null ? '—' : fmtNumber(v, 2))
  return (
    <div className="min-w-[10rem] rounded-lg border border-line bg-panel/95 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 font-semibold text-gray-100">{fmtDay(d.t)}</p>
      <Row label="Clôture" value={n(d.close)} />
      <Row label="Ouv. / + haut / + bas" value={`${n(d.open)} / ${n(d.high)} / ${n(d.low)}`} />
      <Row color={C.m50} label="MM50" value={n(d.m50)} />
      <Row color={C.m100} label="MM100" value={n(d.m100)} />
      <Row color={C.m200} label="MM200" value={n(d.m200)} />
    </div>
  )
}

function SmallTooltip({ active, payload, rows }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="rounded-lg border border-line bg-panel/95 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 font-semibold text-gray-100">{fmtDay(d.t)}</p>
      {rows.map(([key, label, color]) => (
        <Row key={key} color={color} label={label} value={d[key] == null ? '—' : fmtNumber(d[key], 2)} />
      ))}
    </div>
  )
}

function Legend({ showBands }) {
  const items = [
    [C.bull, 'Bougie haussière', 'box'], [C.bear, 'Bougie baissière', 'box'],
    [C.m50, 'MM50'], [C.m100, 'MM100 ★'], [C.m200, 'MM200'],
  ]
  if (showBands) items.push([C.band, 'Bollinger', 'dash'])
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
      {items.map(([color, label, kind]) => (
        <span key={label} className="flex items-center gap-1">
          {kind === 'box'
            ? <span className="inline-block h-2.5 w-1.5 rounded-sm" style={{ background: color }} />
            : <svg width="14" height="4" aria-hidden="true"><line x1="0" y1="2" x2="14" y2="2" stroke={color} strokeWidth="2" strokeDasharray={kind === 'dash' ? '3 2' : undefined} /></svg>}
          {label}
        </span>
      ))}
    </div>
  )
}

export default function TechnicalChart({ data, support, resistance }) {
  const [period, setPeriod] = useState(126)
  const [showBands, setShowBands] = useState(false)
  const [showTable, setShowTable] = useState(false)

  const rows = useMemo(
    () => data.slice(-period).map((d) => ({ ...d, range: [d.low, d.high] })),
    [data, period],
  )
  const [min, max] = useMemo(() => {
    const vals = rows.flatMap((d) => [d.low, d.high, d.m50, d.m100, d.m200, showBands ? d.bbl : null, showBands ? d.bbu : null])
      .filter((v) => v != null)
    const lo = Math.min(...vals), hi = Math.max(...vals)
    const pad = (hi - lo) * 0.05
    return [lo - pad, hi + pad]
  }, [rows, showBands])

  const axisProps = { stroke: C.axis, tick: { fill: C.axis, fontSize: 10 }, tickLine: false, axisLine: false }
  const xAxis = (hide) => (
    <XAxis dataKey="t" tickFormatter={fmtDate} minTickGap={40} hide={hide} {...axisProps} />
  )
  const cursor = { stroke: C.axis, strokeWidth: 1, strokeDasharray: '3 3' }

  return (
    <div className="mt-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex rounded-lg border border-line p-0.5" role="group" aria-label="Période du graphique">
          {PERIODS.map(([label, n]) => (
            <button
              key={label}
              onClick={() => setPeriod(n)}
              aria-pressed={period === n}
              className={`rounded-md px-2.5 py-1 text-xs font-medium ${period === n ? 'bg-panel2 text-gray-100' : 'text-muted'}`}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1.5 text-xs text-muted">
          <input type="checkbox" checked={showBands} onChange={(e) => setShowBands(e.target.checked)} className="accent-bull" />
          Bandes de Bollinger
        </label>
      </div>
      <Legend showBands={showBands} />

      {/* Cours + moyennes mobiles */}
      <div className="mt-2 h-60 sm:h-72" role="img" aria-label="Graphique en chandeliers avec moyennes mobiles 50, 100 et 200 jours">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} syncId={SYNC} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            {xAxis(true)}
            <YAxis domain={[min, max]} orientation="right" width={48} tickFormatter={(v) => fmtNumber(v, v >= 100 ? 0 : 2)} {...axisProps} />
            <Tooltip content={<PriceTooltip />} cursor={cursor} isAnimationActive={false} />
            {support != null && <ReferenceLine y={support} stroke={C.bull} strokeOpacity={0.5} strokeDasharray="4 4" label={{ value: 'Support', fill: C.axis, fontSize: 10, position: 'insideBottomLeft' }} />}
            {resistance != null && <ReferenceLine y={resistance} stroke={C.bear} strokeOpacity={0.5} strokeDasharray="4 4" label={{ value: 'Résistance', fill: C.axis, fontSize: 10, position: 'insideTopLeft' }} />}
            {showBands && <Line dataKey="bbu" stroke={C.band} strokeWidth={1} strokeDasharray="3 2" dot={false} isAnimationActive={false} />}
            {showBands && <Line dataKey="bbl" stroke={C.band} strokeWidth={1} strokeDasharray="3 2" dot={false} isAnimationActive={false} />}
            <Bar dataKey="range" shape={<Candle />} isAnimationActive={false} />
            <Line dataKey="m50" stroke={C.m50} strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
            <Line dataKey="m200" stroke={C.m200} strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
            <Line dataKey="m100" stroke={C.m100} strokeWidth={2.5} dot={false} isAnimationActive={false} connectNulls />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* MACD */}
      <p className="mt-3 flex items-center gap-3 text-[11px] text-muted">
        <span className="font-semibold uppercase tracking-wide">MACD (12, 26, 9)</span>
        <span className="flex items-center gap-1"><svg width="12" height="4"><line x1="0" y1="2" x2="12" y2="2" stroke={C.macd} strokeWidth="2" /></svg>MACD</span>
        <span className="flex items-center gap-1"><svg width="12" height="4"><line x1="0" y1="2" x2="12" y2="2" stroke={C.sig} strokeWidth="2" /></svg>Signal</span>
      </p>
      <div className="h-24" role="img" aria-label="Graphique du MACD">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} syncId={SYNC} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            {xAxis(true)}
            <YAxis orientation="right" width={48} tickFormatter={(v) => fmtNumber(v, 1)} {...axisProps} />
            <Tooltip content={<SmallTooltip rows={[['macd', 'MACD', C.macd], ['sig', 'Signal', C.sig], ['hist', 'Histogramme']]} />} cursor={cursor} isAnimationActive={false} />
            <ReferenceLine y={0} stroke={C.axis} strokeOpacity={0.4} />
            <Bar dataKey="hist" isAnimationActive={false}>
              {rows.map((d) => <Cell key={d.t} fill={(d.hist ?? 0) >= 0 ? C.bull : C.bear} fillOpacity={0.45} />)}
            </Bar>
            <Line dataKey="macd" stroke={C.macd} strokeWidth={1.5} dot={false} isAnimationActive={false} />
            <Line dataKey="sig" stroke={C.sig} strokeWidth={1.5} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* RSI */}
      <p className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-muted">RSI (14) · zones 30 / 70</p>
      <div className="h-24" role="img" aria-label="Graphique du RSI">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} syncId={SYNC} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            {xAxis(false)}
            <YAxis domain={[0, 100]} ticks={[30, 70]} orientation="right" width={48} {...axisProps} />
            <Tooltip content={<SmallTooltip rows={[['rsi', 'RSI', C.rsi]]} />} cursor={cursor} isAnimationActive={false} />
            <ReferenceLine y={70} stroke={C.bear} strokeOpacity={0.5} strokeDasharray="3 3" />
            <ReferenceLine y={30} stroke={C.bull} strokeOpacity={0.5} strokeDasharray="3 3" />
            <Line dataKey="rsi" stroke={C.rsi} strokeWidth={1.5} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Vue tableau (accessibilité) */}
      <button className="mt-3 text-xs text-muted underline-offset-2 hover:underline" onClick={() => setShowTable((v) => !v)} aria-expanded={showTable}>
        {showTable ? 'Masquer' : 'Voir'} les valeurs des 10 dernières séances
      </button>
      {showTable && (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[28rem] text-right text-xs">
            <thead className="text-muted">
              <tr><th className="py-1 text-left font-medium">Date</th><th>Clôture</th><th>MM50</th><th>MM100</th><th>MM200</th><th>RSI</th><th>MACD</th></tr>
            </thead>
            <tbody>
              {data.slice(-10).reverse().map((d) => (
                <tr key={d.t} className="border-t border-line">
                  <td className="py-1 text-left">{fmtDay(d.t)}</td>
                  {['close', 'm50', 'm100', 'm200', 'rsi', 'macd'].map((k) => <td key={k}>{d[k] == null ? '—' : fmtNumber(d[k], 2)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
