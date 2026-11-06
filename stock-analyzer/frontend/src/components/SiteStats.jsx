import { useEffect, useState } from 'react'
import { BarChart3 } from 'lucide-react'
import { api } from '../lib/api'
import { Spinner } from './ui'

const nf = new Intl.NumberFormat('fr-BE')

function Ranking({ title, rows, label, value }) {
  const max = Math.max(1, ...rows.map(value))
  return (
    <div className="mt-4">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</h4>
      {rows.length === 0 ? <p className="mt-1 text-sm text-muted">Rien pour l’instant.</p> : (
        <ul className="mt-1.5 space-y-1.5">
          {rows.map((r) => (
            <li key={label(r)} className="text-sm">
              <div className="flex justify-between gap-3"><span className="min-w-0 truncate">{label(r)}</span><span className="shrink-0 font-semibold">{nf.format(value(r))}</span></div>
              <div className="mt-0.5 h-1 rounded-full bg-bg"><div className="h-full rounded-full bg-gray-400" style={{ width: `${(value(r) / max) * 100}%` }} /></div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// Visites du site public (administrateur) : compteur maison, sans cookie
export default function SiteStats() {
  const [days, setDays] = useState(30)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    setData(null)
    api.siteStats(days).then(setData).catch((e) => setError(e.message))
  }, [days])

  return (
    <div className="mt-5 rounded-lg border border-line p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 font-semibold"><BarChart3 className="h-4 w-4" /> Visites du site</h3>
        <div className="flex rounded-lg bg-bg p-0.5 text-xs" role="radiogroup" aria-label="Période">
          {[7, 30, 90].map((d) => (
            <button key={d} role="radio" aria-checked={days === d} onClick={() => setDays(d)}
              className={`rounded-md px-2 py-1 ${days === d ? 'bg-panel font-semibold text-gray-100' : 'text-muted'}`}>{d} j</button>
          ))}
        </div>
      </div>
      {error && <p className="mt-2 text-sm text-bear">{error}</p>}
      {!data && !error && <div className="flex justify-center py-6"><Spinner className="h-5 w-5" /></div>}
      {data && (
        <>
          <div className="mt-3 grid grid-cols-3 gap-2">
            {[['Visiteurs', data.visitors], ['Pages vues', data.views], ["Aujourd'hui", data.today.visitors]].map(([l, v]) => (
              <div key={l} className="rounded-lg bg-bg p-2.5">
                <p className="text-xl font-bold">{nf.format(v)}</p>
                <p className="text-[11px] text-muted">{l}</p>
              </div>
            ))}
          </div>
          {data.pending_requests > 0 && (
            <p className="mt-2 text-sm text-warn">{data.pending_requests} demande{data.pending_requests > 1 ? 's' : ''} d’accès en attente (menu → Inviter un ami).</p>
          )}
          <Ranking title="Pages les plus lues" rows={data.pages} label={(r) => r.title} value={(r) => r.views} />
          <Ranking title="D’où viennent les visiteurs" rows={data.sources} label={(r) => r.source} value={(r) => r.visitors} />
          <p className="mt-3 text-[11px] text-muted">
            Compteur sans cookie : les robots et les membres connectés ne comptent pas. Astuce : ajoute <b>?ref=reddit</b> (ou whatsapp,
            facebook…) aux liens que tu partages pour savoir d’où viennent les visiteurs.
          </p>
        </>
      )}
    </div>
  )
}
