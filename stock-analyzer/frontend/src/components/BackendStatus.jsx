import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { api } from '../lib/api'

function Row({ label, ok, text }) {
  return (
    <li className="flex items-center justify-between gap-2 py-1.5">
      <span className="text-muted">{label}</span>
      <span className={ok ? 'text-bull' : 'text-warn'}>{text ?? (ok ? 'OK' : 'Non configuré')}</span>
    </li>
  )
}

// Test de communication frontend ↔ backend (appel de /health).
export default function BackendStatus() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const check = async () => {
    setBusy(true)
    try {
      setHealth(await api.health())
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { check() }, [])

  const jobs = health?.scheduler?.jobs || []
  const next = jobs[0]?.next_run
    ? new Date(jobs[0].next_run).toLocaleTimeString('fr-BE', { hour: '2-digit', minute: '2-digit' })
    : null

  return (
    <section className="card p-4 text-sm">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">État du serveur</h2>
        <button className="btn-ghost p-1.5" onClick={check} aria-label="Revérifier" disabled={busy}>
          <RefreshCw className={`h-4 w-4 ${busy ? 'animate-spin' : ''}`} />
        </button>
      </div>
      {error && <p className="mt-2 text-bear">❌ {error}</p>}
      {health && (
        <ul className="mt-2 divide-y divide-line">
          <Row label="Backend" ok={health.status === 'ok'} text={health.status === 'ok' ? `✅ v${health.version}` : '⚠️ dégradé'} />
          <Row label="Base SQLite" ok={health.database.ok} text={health.database.ok ? 'OK' : 'Erreur'} />
          <Row
            label="Tâches de fond"
            ok={health.scheduler.running}
            text={health.scheduler.running ? `Actives${next ? ` · prochaine ${next}` : ''}` : 'Arrêtées'}
          />
          <Row label="SMTP (alertes)" ok={health.config.smtp_configured} />
          <Row label="NewsAPI" ok={health.config.newsapi_configured} />
        </ul>
      )}
    </section>
  )
}
