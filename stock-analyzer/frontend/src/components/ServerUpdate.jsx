import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, DownloadCloud, RefreshCw } from 'lucide-react'
import { api } from '../lib/api'
import { Spinner } from './ui'

const POLL_MS = 5000
const NO_CHANGE_AFTER_MS = 120 * 1000
const GIVE_UP_MS = 6 * 60 * 1000

const fmtDate = (iso) => {
  try { return new Date(iso).toLocaleString('fr-BE', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) } catch { return iso }
}

export default function ServerUpdate() {
  const [info, setInfo] = useState(null)
  const [phase, setPhase] = useState('idle') // idle | updating | done | nochange | slow
  const [error, setError] = useState(null)
  const timer = useRef(null)

  useEffect(() => {
    api.adminVersion().then(setInfo).catch((e) => setError(e.message))
    return () => clearTimeout(timer.current)
  }, [])

  const poll = (before, startedAt) => {
    timer.current = setTimeout(async () => {
      const elapsed = Date.now() - startedAt
      try {
        const now = await api.adminVersion()
        setInfo(now)
        if (now.version?.commit && now.version.commit !== before) return setPhase('done')
        if (!now.update_pending && elapsed > NO_CHANGE_AFTER_MS) return setPhase('nochange')
      } catch { /* l'application redémarre : on réessaie */ }
      if (elapsed > GIVE_UP_MS) return setPhase('slow')
      poll(before, startedAt)
    }, POLL_MS)
  }

  const update = async () => {
    setError(null)
    try {
      await api.adminUpdate()
      setPhase('updating')
      poll(info?.version?.commit, Date.now())
    } catch (e) {
      setError(e.message)
    }
  }

  if (!info && !error) return null
  const v = info?.version

  return (
    <div className="mt-5 rounded-lg border border-line p-4">
      <h3 className="flex items-center gap-2 font-semibold"><DownloadCloud className="h-4 w-4" /> Application</h3>
      <p className="mt-1 text-xs text-muted">
        {v ? <>Version installée : <span className="font-mono">{v.commit}</span> du {fmtDate(v.date)}<br />« {v.subject} »</> : 'Version : installation locale'}
      </p>
      {info && !info.auto_update && (
        <p className="mt-2 text-xs text-muted">Sur un PC, mets à jour en téléchargeant le nouveau ZIP. La mise à jour automatique est disponible sur le serveur en ligne.</p>
      )}
      {info?.auto_update && (
        <>
          <p className="mt-2 text-xs text-muted">Mise à jour automatique chaque nuit vers 4 h 30.</p>
          {phase === 'idle' && (
            <button className="btn-ghost mt-3 w-full justify-center border border-line" onClick={update}>
              <RefreshCw className="h-4 w-4" /> Mettre à jour maintenant
            </button>
          )}
          {phase === 'updating' && (
            <p className="mt-3 flex items-center gap-2 text-sm text-muted" role="status">
              <Spinner className="h-4 w-4" /> Mise à jour en cours… l'application redémarre (1 à 3 minutes).
            </p>
          )}
          {phase === 'done' && (
            <div className="mt-3" role="status">
              <p className="flex items-center gap-2 text-sm text-bull"><CheckCircle2 className="h-4 w-4" /> Nouvelle version installée.</p>
              <button className="btn-primary mt-2 w-full" onClick={() => window.location.reload()}>Recharger l'application</button>
            </div>
          )}
          {phase === 'nochange' && <p className="mt-3 text-sm text-muted" role="status">Aucune nouvelle version : l'application est à jour.</p>}
          {phase === 'slow' && <p className="mt-3 text-sm text-warn" role="status">La mise à jour prend plus de temps que prévu. Rouvre ton profil dans quelques minutes.</p>}
        </>
      )}
      {error && <p className="mt-2 text-sm text-bear">{error}</p>}
    </div>
  )
}
