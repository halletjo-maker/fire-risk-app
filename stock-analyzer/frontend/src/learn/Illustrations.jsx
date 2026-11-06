// Schémas pédagogiques (données illustratives, pas de vrais cours).
// Mêmes couleurs que le graphique technique : MM100 orange, MACD bleu / signal orange.
const C = {
  price: '#E6EDF3', mm: '#d95926', blue: '#3987e5', orange: '#d95926', bull: '#00FF88', bear: '#FF4444',
  grid: '#21262D', text: '#8B949E', band: '#8B949E',
}
const W = 320
const H = 150

// Courbe lissée à partir de valeurs (0 = bas, 1 = haut)
function path(values, top = 12, bottom = H - 22) {
  const step = (W - 16) / (values.length - 1)
  return values.map((v, i) => `${i ? 'L' : 'M'}${(8 + i * step).toFixed(1)},${(bottom - v * (bottom - top)).toFixed(1)}`).join(' ')
}
const xAt = (i, n) => 8 + i * ((W - 16) / (n - 1))
const yAt = (v, top = 12, bottom = H - 22) => bottom - v * (bottom - top)

function Frame({ label, children, legend }) {
  return (
    <figure className="my-4 rounded-lg border border-line bg-bg p-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={label}>
        {[0.25, 0.5, 0.75].map((g) => <line key={g} x1="8" x2={W - 8} y1={yAt(g)} y2={yAt(g)} stroke={C.grid} strokeWidth="1" />)}
        {children}
      </svg>
      {legend && (
        <figcaption className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {legend.map(([color, text, dashed]) => (
            <span key={text} className="flex items-center gap-1.5">
              <svg width="14" height="4" aria-hidden="true"><line x1="0" y1="2" x2="14" y2="2" stroke={color} strokeWidth="2" strokeDasharray={dashed ? '3 2' : undefined} /></svg>
              {text}
            </span>
          ))}
        </figcaption>
      )}
    </figure>
  )
}

const PRICE = [0.3, 0.26, 0.22, 0.25, 0.2, 0.18, 0.22, 0.27, 0.33, 0.4, 0.46, 0.43, 0.5, 0.56, 0.62, 0.58, 0.66, 0.72, 0.7, 0.78]
const MM = [0.36, 0.34, 0.32, 0.31, 0.29, 0.27, 0.26, 0.26, 0.27, 0.29, 0.32, 0.35, 0.38, 0.41, 0.45, 0.48, 0.51, 0.55, 0.58, 0.61]

function MM100() {
  const n = PRICE.length
  // Point exact où le cours repasse au-dessus de la moyenne (interpolation entre deux séances)
  const i = PRICE.findIndex((v, k) => k > 0 && PRICE[k - 1] < MM[k - 1] && v >= MM[k])
  const d0 = PRICE[i - 1] - MM[i - 1]
  const d1 = PRICE[i] - MM[i]
  const t = d0 / (d0 - d1)
  const cx = xAt(i - 1, n) + t * (xAt(i, n) - xAt(i - 1, n))
  const cy = yAt(MM[i - 1] + t * (MM[i] - MM[i - 1]))
  return (
    <Frame label="Schéma : le cours passe sous puis au-dessus de sa moyenne mobile 100 jours" legend={[[C.price, 'Cours'], [C.mm, 'MM100']]}>
      <path d={path(MM)} fill="none" stroke={C.mm} strokeWidth="2.5" strokeLinecap="round" />
      <path d={path(PRICE)} fill="none" stroke={C.price} strokeWidth="2" strokeLinecap="round" />
      <circle cx={cx} cy={cy} r="6" fill="none" stroke={C.bull} strokeWidth="2" />
      <text x={cx + 10} y={cy + 16} fill={C.text} fontSize="10">⚡ croisement haussier</text>
      <text x="10" y={yAt(0.05)} fill={C.text} fontSize="10">sous la MM100 : baissier</text>
      <text x={W - 10} y={yAt(0.92)} fill={C.text} fontSize="10" textAnchor="end">au-dessus : haussier</text>
    </Frame>
  )
}

function RSI() {
  const v = [0.5, 0.58, 0.66, 0.74, 0.78, 0.72, 0.62, 0.5, 0.4, 0.3, 0.24, 0.22, 0.3, 0.42, 0.5, 0.56, 0.6, 0.55, 0.5, 0.52]
  return (
    <Frame label="Schéma : RSI entre 0 et 100 avec les zones de surachat au-dessus de 70 et de survente sous 30" legend={[[C.blue, 'RSI (14)']]}>
      <rect x="8" y={yAt(1)} width={W - 16} height={yAt(0.7) - yAt(1)} fill={C.bear} opacity="0.12" />
      <rect x="8" y={yAt(0.3)} width={W - 16} height={yAt(0) - yAt(0.3)} fill={C.bull} opacity="0.12" />
      <line x1="8" x2={W - 8} y1={yAt(0.7)} y2={yAt(0.7)} stroke={C.bear} strokeDasharray="4 3" opacity="0.7" />
      <line x1="8" x2={W - 8} y1={yAt(0.3)} y2={yAt(0.3)} stroke={C.bull} strokeDasharray="4 3" opacity="0.7" />
      <path d={path(v)} fill="none" stroke={C.blue} strokeWidth="2" strokeLinecap="round" />
      <text x={W - 10} y={yAt(0.86)} fill={C.text} fontSize="10" textAnchor="end">70 · surachat</text>
      <text x={W - 10} y={yAt(0.12)} fill={C.text} fontSize="10" textAnchor="end">30 · survente</text>
    </Frame>
  )
}

function MACD() {
  const macd = [0.38, 0.35, 0.32, 0.3, 0.31, 0.35, 0.41, 0.48, 0.55, 0.6, 0.63, 0.64, 0.62, 0.58, 0.53, 0.49, 0.46, 0.45, 0.47, 0.5]
  const sig = [0.42, 0.4, 0.38, 0.36, 0.34, 0.34, 0.36, 0.39, 0.43, 0.48, 0.52, 0.56, 0.58, 0.59, 0.58, 0.56, 0.53, 0.5, 0.49, 0.49]
  const n = macd.length
  const zero = 0.45
  const bw = (W - 16) / n - 4
  return (
    <Frame label="Schéma : MACD, ligne de signal et histogramme qui grandit puis diminue" legend={[[C.blue, 'MACD'], [C.orange, 'Signal']]}>
      {macd.map((m, i) => {
        const h = (m - sig[i]) * 2.2
        const y0 = yAt(zero)
        const y1 = yAt(zero + h)
        return <rect key={i} x={xAt(i, n) - bw / 2} y={Math.min(y0, y1)} width={bw} height={Math.max(1, Math.abs(y1 - y0))}
          rx="1" fill={h >= 0 ? C.bull : C.bear} opacity="0.55" />
      })}
      <path d={path(sig)} fill="none" stroke={C.orange} strokeWidth="2" strokeLinecap="round" />
      <path d={path(macd)} fill="none" stroke={C.blue} strokeWidth="2" strokeLinecap="round" />
      <text x={xAt(6, n)} y={yAt(0.86)} fill={C.text} fontSize="10">MACD &gt; signal : dynamique positive</text>
    </Frame>
  )
}

function Bollinger() {
  const mid = [0.45, 0.46, 0.46, 0.47, 0.47, 0.48, 0.48, 0.49, 0.5, 0.52, 0.54, 0.56, 0.58, 0.6, 0.62, 0.63, 0.64, 0.65, 0.66, 0.66]
  const width = [0.12, 0.11, 0.09, 0.07, 0.06, 0.05, 0.05, 0.06, 0.08, 0.12, 0.16, 0.19, 0.2, 0.2, 0.19, 0.18, 0.17, 0.16, 0.16, 0.15]
  const price = [0.44, 0.5, 0.45, 0.49, 0.46, 0.5, 0.47, 0.52, 0.56, 0.63, 0.7, 0.72, 0.75, 0.78, 0.74, 0.77, 0.73, 0.7, 0.74, 0.72]
  return (
    <Frame label="Schéma : bandes de Bollinger qui se resserrent puis s'écartent quand le cours accélère"
      legend={[[C.price, 'Cours'], [C.band, 'Bandes (±2 écarts-types)', true]]}>
      <path d={path(mid.map((m, i) => m + width[i]))} fill="none" stroke={C.band} strokeWidth="1.5" strokeDasharray="4 3" />
      <path d={path(mid.map((m, i) => m - width[i]))} fill="none" stroke={C.band} strokeWidth="1.5" strokeDasharray="4 3" />
      <path d={path(mid)} fill="none" stroke={C.band} strokeWidth="1" opacity="0.6" />
      <path d={path(price)} fill="none" stroke={C.price} strokeWidth="2" strokeLinecap="round" />
      <text x={xAt(4, 20)} y={yAt(0.2)} fill={C.text} fontSize="10" textAnchor="middle">resserrement</text>
      <text x={xAt(13, 20)} y={yAt(0.16)} fill={C.text} fontSize="10" textAnchor="middle">les bandes s'écartent</text>
    </Frame>
  )
}

function Levels() {
  const price = [0.5, 0.62, 0.72, 0.66, 0.5, 0.34, 0.3, 0.4, 0.56, 0.7, 0.73, 0.6, 0.45, 0.33, 0.31, 0.42, 0.58, 0.69, 0.78, 0.86]
  return (
    <Frame label="Schéma : le cours rebondit sur un support, cale sous une résistance puis la franchit ; stop-loss sous le support"
      legend={[[C.bull, 'Support', true], [C.bear, 'Résistance', true], [C.text, 'Stop-loss', true]]}>
      <line x1="8" x2={W - 8} y1={yAt(0.74)} y2={yAt(0.74)} stroke={C.bear} strokeWidth="1.5" strokeDasharray="5 3" />
      <line x1="8" x2={W - 8} y1={yAt(0.3)} y2={yAt(0.3)} stroke={C.bull} strokeWidth="1.5" strokeDasharray="5 3" />
      <line x1="8" x2={W - 8} y1={yAt(0.2)} y2={yAt(0.2)} stroke={C.text} strokeWidth="1" strokeDasharray="2 3" />
      <path d={path(price)} fill="none" stroke={C.price} strokeWidth="2" strokeLinecap="round" />
      <text x={xAt(6, 20)} y={yAt(0.74) - 5} fill={C.text} fontSize="10" textAnchor="middle">résistance (plafond)</text>
      <text x={xAt(9.5, 20)} y={yAt(0.3) - 5} fill={C.text} fontSize="10" textAnchor="middle">support</text>
      <text x={W - 10} y={yAt(0.2) + 12} fill={C.text} fontSize="10" textAnchor="end">stop-loss, juste sous le support</text>
      <text x={W - 10} y={yAt(0.92)} fill={C.text} fontSize="10" textAnchor="end">cassure ↗</text>
    </Frame>
  )
}

const MAP = { mm100: MM100, rsi: RSI, macd: MACD, bollinger: Bollinger, levels: Levels }

export default function Illustration({ name }) {
  const Comp = MAP[name]
  return Comp ? <Comp /> : null
}
