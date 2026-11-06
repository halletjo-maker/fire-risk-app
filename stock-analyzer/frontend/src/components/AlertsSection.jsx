import { useEffect, useState } from 'react'
import { BellRing, CheckCircle2, Mail, MailWarning, RefreshCw } from 'lucide-react'
import { api } from '../lib/api'

function when(sql) {
  const d = new Date(sql.replace(' ', 'T') + 'Z')
  return d.toLocaleString('fr-BE', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

// Profil : état du SMTP, mail de test, vérification immédiate, historique des alertes
export default function AlertsSection() {
  const [hist, setHist] = useState(null)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = () => api.alertHistory(10).then(setHist).catch(() => setHist({ events: [], smtp_configured: false }))
  useEffect(() => { load() }, [])

  const test = async () => {
    setBusy(true)
    try {
      const r = await api.testMail()
      setMsg({ ok: r.delivered, text: r.delivered ? 'Mail de test envoyé : vérifie ta boîte de réception.' : r.status })
    } catch (e) {
      setMsg({ ok: false, text: e.message })
    }
    setBusy(false)
  }

  const check = async () => {
    setBusy(true)
    try {
      await api.checkAlerts()
      setMsg({ ok: true, text: 'Vérification lancée. Les alertes déclenchées apparaîtront ci-dessous.' })
      setTimeout(load, 8000)
    } catch (e) {
      setMsg({ ok: false, text: e.message })
    }
    setBusy(false)
  }

  return (
    <div className="mt-5 border-t border-line pt-4">
      <h3 className="flex items-center gap-2 font-semibold"><BellRing className="h-4 w-4" /> Alertes mail</h3>
      {hist && (
        <p className={`mt-2 flex items-start gap-2 text-xs ${hist.smtp_configured ? 'text-bull' : 'text-warn'}`}>
          {hist.smtp_configured ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <MailWarning className="h-4 w-4 shrink-0" />}
          {hist.smtp_configured
            ? 'SMTP configuré : les alertes sont envoyées à ton adresse.'
            : "Envoi des mails pas encore configuré : les alertes et rapports sont enregistrés sans être envoyés. L'administrateur les active dans « Réglages mail » ci-dessous."}
        </p>
      )}
      <div className="mt-3 grid grid-cols-2 gap-2">
        <button className="btn-ghost justify-center border border-line" onClick={test} disabled={busy}>
          <Mail className="h-4 w-4" /> Mail de test
        </button>
        <button className="btn-ghost justify-center border border-line" onClick={check} disabled={busy}>
          <RefreshCw className="h-4 w-4" /> Vérifier
        </button>
      </div>
      {msg && <p className={`mt-2 text-xs ${msg.ok ? 'text-bull' : 'text-warn'}`} role="status">{msg.text}</p>}
      <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-muted">Dernières alertes</p>
      {hist && hist.events.length === 0 && <p className="mt-1 text-xs text-muted">Aucune alerte déclenchée pour l'instant.</p>}
      <ul className="mt-1 space-y-1.5">
        {hist?.events.map((e) => (
          <li key={e.id} className="text-xs">
            <p className="break-words">{e.subject}</p>
            <p className="text-muted">{when(e.sent_at)} · {e.delivered ? '✅ envoyé' : `📁 ${e.status}`}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}
