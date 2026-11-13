import { useEffect, useRef, useState } from 'react'
import { Check, Globe } from 'lucide-react'
import { api } from '../lib/api'
import { Spinner } from './ui'

// Nom de domaine (administrateur) : vérifie le DNS puis le serveur se configure seul (https compris)
export default function DomainSettings() {
  const [info, setInfo] = useState(null)
  const [domain, setDomain] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [waiting, setWaiting] = useState(null) // noms en cours d'activation
  const timer = useRef(null)

  const load = () => api.domainStatus().then(setInfo).catch(() => setInfo(null))
  useEffect(() => { load(); return () => clearTimeout(timer.current) }, [])

  const poll = (names, start = Date.now()) => {
    timer.current = setTimeout(async () => {
      try {
        const st = await api.domainStatus()
        setInfo(st)
        if (!st.pending && st.last) return setWaiting(null)
      } catch { /* le serveur redémarre */ }
      if (Date.now() - start < 3 * 60 * 1000) poll(names, start)
      else setWaiting(null)
    }, 4000)
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = await api.setDomain(domain.trim())
      setWaiting(r.names)
      poll(r.names)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!info || !info.available) return null
  const isIp = /sslip\.io$/.test(info.current || '')
  return (
    <div className="mt-5 rounded-lg border border-line p-4">
      <h3 className="flex items-center gap-2 font-semibold"><Globe className="h-4 w-4" /> Nom de domaine</h3>
      <p className="mt-1 text-xs text-muted">Adresse actuelle : <span className="text-gray-200">https://{info.current}</span></p>

      {waiting && (
        <p className="mt-3 flex items-center gap-2 text-sm text-muted" role="status">
          <Spinner className="h-4 w-4" /> Activation de {waiting.join(' et ')} : certificat https et redémarrage (1 à 2 minutes)…
        </p>
      )}
      {!waiting && info.last?.ok && !isIp && (
        <div className="mt-3 text-sm" role="status">
          <p className="flex items-center gap-1.5 text-bull"><Check className="h-4 w-4" /> Actif : {info.last.detail}</p>
          {window.location.hostname !== info.current && (
            <a href={`https://${info.current}`} className="btn-primary mt-2 w-full">Ouvrir https://{info.current}</a>
          )}
          <p className="mt-2 text-xs text-muted">Sur la nouvelle adresse, reconnecte-toi une fois et réinstalle l'application sur ton téléphone. L'ancienne adresse reste valable.</p>
        </div>
      )}
      {!waiting && info.last && !info.last.ok && <p className="mt-2 text-sm text-bear">Dernier essai refusé : {info.last.detail}</p>}

      {!waiting && (
        <form onSubmit={submit} className="mt-3 space-y-2">
          <p className="text-xs text-muted">
            Chez ton fournisseur de domaine, la zone DNS doit contenir une entrée <b className="text-gray-200">A</b> vers
            <b className="text-gray-200"> {info.server_ip || "l'adresse du serveur"}</b> (et une pour « www » si tu le souhaites).
          </p>
          <div className="flex gap-2">
            <input className="input" placeholder="mm100.be" autoCapitalize="none" value={domain} onChange={(e) => setDomain(e.target.value)} aria-label="Nom de domaine" />
            <button type="submit" className="btn-primary shrink-0" disabled={busy || domain.trim().length < 3}>
              {busy ? <Spinner className="h-4 w-4" /> : 'Activer'}
            </button>
          </div>
          {error && <p className="text-sm text-bear" role="alert">{error}</p>}
        </form>
      )}
    </div>
  )
}
