import { useEffect, useState } from 'react'
import { MailWarning } from 'lucide-react'
import { api } from '../lib/api'
import Modal from './Modal'
import { Spinner } from './ui'

function Toggle({ checked, onChange, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 shrink-0 rounded-full transition ${checked ? 'bg-bull' : 'bg-line'}`}
    >
      <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition ${checked ? 'left-[1.375rem]' : 'left-0.5'}`} />
    </button>
  )
}

export default function AlertSettings({ item, onClose, onSaved }) {
  const [data, setData] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.itemAlerts(item.id)
      .then((d) => { setData(d); setAlerts(d.alerts) })
      .catch((e) => setError(e.message))
  }, [item.id])

  const set = (type, patch) => setAlerts((list) => list.map((a) => (a.type === type ? { ...a, ...patch } : a)))

  const save = async () => {
    setBusy(true)
    try {
      await api.saveItemAlerts(item.id, alerts.map(({ type, enabled, frequency }) => ({ type, enabled, frequency })))
      onSaved?.(alerts.filter((a) => a.enabled).length)
      onClose()
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  return (
    <Modal title="Alertes mail" onClose={onClose} label={`Alertes mail pour ${item.name}`}>
      <p className="mt-1 text-sm text-muted">{item.name} · {item.symbol}</p>
      {data && !data.smtp_configured && (
        <p className="mt-3 flex gap-2 rounded-lg border border-warn/30 bg-warn/5 p-3 text-xs text-warn">
          <MailWarning className="h-4 w-4 shrink-0" />
          Le SMTP n'est pas encore configuré : les alertes seront enregistrées (historique et dossier outbox) mais pas envoyées. Voir le README, section Gmail.
        </p>
      )}
      {!data && !error && <div className="flex justify-center py-8"><Spinner /></div>}
      {error && <p className="mt-3 text-sm text-bear">{error}</p>}
      {data && (
        <ul className="mt-3 divide-y divide-line">
          {alerts.map((a) => (
            <li key={a.type} className="py-3">
              <div className="flex items-start gap-3">
                <span className="text-lg leading-6" aria-hidden="true">{a.icon}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{a.label}</p>
                  <p className="text-xs text-muted">{a.help}</p>
                </div>
                <Toggle checked={a.enabled} onChange={(v) => set(a.type, { enabled: v })} label={`${a.label} : ${a.enabled ? 'activée' : 'désactivée'}`} />
              </div>
              {a.enabled && (
                <label className="ml-9 mt-2 flex items-center gap-2 text-xs text-muted">
                  Fréquence max.
                  <select
                    className="rounded-md border border-line bg-bg px-2 py-1 text-gray-100"
                    value={a.frequency}
                    onChange={(e) => set(a.type, { frequency: e.target.value })}
                    aria-label={`Fréquence de l'alerte ${a.label}`}
                  >
                    {Object.entries(data.frequencies).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </label>
              )}
            </li>
          ))}
        </ul>
      )}
      {data && (
        <>
          <p className="mt-2 text-[11px] text-muted">
            Vérification toutes les 15 minutes. Un mail part quand la condition devient vraie ; chaque mail contient un lien de désinscription.
          </p>
          <button className="btn-primary mt-4 w-full" onClick={save} disabled={busy}>Enregistrer</button>
        </>
      )}
    </Modal>
  )
}
