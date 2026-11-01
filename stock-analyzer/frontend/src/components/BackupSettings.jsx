import { useEffect, useState } from 'react'
import { Check, DatabaseBackup, Send } from 'lucide-react'
import { api } from '../lib/api'
import { Spinner } from './ui'
import PasswordInput from './PasswordInput'

const MIN = 12
const date = (iso) => (iso ? new Date(iso).toLocaleString('fr-BE', { dateStyle: 'long', timeStyle: 'short' }) : null)

// Sauvegardes (administrateur) : copie chaque nuit sur le serveur + copie chiffrée par mail chaque dimanche
export default function BackupSettings() {
  const [info, setInfo] = useState(null)
  const [editing, setEditing] = useState(false)
  const [pass, setPass] = useState('')
  const [confirm, setConfirm] = useState('')
  const [noted, setNoted] = useState(false)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  useEffect(() => { api.backupStatus().then(setInfo).catch(() => setInfo(null)) }, [])

  const save = async (e) => {
    e.preventDefault()
    if (pass.length < MIN) return setError(`Au moins ${MIN} caractères.`)
    if (pass !== confirm) return setError('Les deux mots de passe sont différents.')
    setBusy('save')
    setError(null)
    try {
      setInfo(await api.setBackupPassphrase(pass))
      setEditing(false)
      setPass('')
      setConfirm('')
      setNoted(false)
    } catch (err) { setError(err.message) } finally { setBusy(null) }
  }
  const sendNow = async () => {
    setBusy('send')
    setResult(null)
    try {
      const r = await api.sendBackup()
      setResult(r)
      setInfo(r)
    } catch (err) { setResult({ sent: false, status: err.message }) } finally { setBusy(null) }
  }

  if (!info) return null
  const last = info.local?.[0]
  return (
    <div className="mt-5 rounded-lg border border-line p-4">
      <h3 className="flex items-center gap-2 font-semibold"><DatabaseBackup className="h-4 w-4" /> Sauvegardes</h3>
      <ul className="mt-2 space-y-1.5 text-sm">
        <li className="flex gap-2">
          <Check className={`mt-0.5 h-4 w-4 shrink-0 ${last ? 'text-bull' : 'text-muted'}`} />
          <span>Chaque nuit, une copie sur le serveur (14 jours gardés).
            <span className="block text-xs text-muted">{last ? `Dernière : ${last.name.slice(6, 16).split('-').reverse().join('/')} · ${Math.max(1, Math.round(last.size / 1000))} ko` : 'Première copie cette nuit.'}</span>
          </span>
        </li>
        <li className="flex gap-2">
          <Check className={`mt-0.5 h-4 w-4 shrink-0 ${info.passphrase_set && info.mail_configured ? 'text-bull' : 'text-muted'}`} />
          <span>Chaque dimanche, une copie chiffrée envoyée sur ta boîte mail, au cas où le serveur casserait.
            <span className="block text-xs text-muted">
              {!info.passphrase_set ? 'À activer : choisis un mot de passe de sauvegarde.'
                : !info.mail_configured ? 'En attente : configure d\'abord l\'envoi des mails.'
                  : info.last_sent ? `Dernier envoi : ${date(info.last_sent)}` : 'Premier envoi dimanche matin.'}
              {info.last_status && info.last_status !== 'Envoyée' && <span className="block text-warn">Dernier essai : {info.last_status}</span>}
            </span>
          </span>
        </li>
      </ul>

      {!editing && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <button className="btn-ghost justify-center border border-line text-sm" onClick={() => { setEditing(true); setError(null) }}>
            {info.passphrase_set ? 'Changer le mot de passe' : 'Choisir le mot de passe'}
          </button>
          {info.passphrase_set && (
            <button className="btn-ghost justify-center border border-line text-sm" onClick={sendNow} disabled={!!busy || !info.mail_configured}>
              {busy === 'send' ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />} M'envoyer une copie
            </button>
          )}
        </div>
      )}
      {result && (
        <p className={`mt-2 text-sm ${result.sent ? 'text-bull' : 'text-warn'}`} role="status">
          {result.sent ? 'Copie envoyée : regarde ta boîte mail.' : `Non envoyée : ${result.status}`}
        </p>
      )}

      {editing && (
        <form onSubmit={save} className="mt-3 space-y-3">
          <p className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
            Ce mot de passe est le seul moyen d'ouvrir les copies reçues par mail. Note-le sur papier ou dans ton
            gestionnaire de mots de passe : s'il est perdu, les copies sont illisibles, même pour toi.
          </p>
          <label className="block text-sm font-medium" htmlFor="bk-pass">Mot de passe de sauvegarde</label>
          <PasswordInput id="bk-pass" value={pass} onChange={setPass} autoComplete="new-password" placeholder={`${MIN} caractères minimum`} />
          <label className="block text-sm font-medium" htmlFor="bk-confirm">Confirme-le</label>
          <PasswordInput id="bk-confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" />
          <label className="flex cursor-pointer items-start gap-2 text-sm">
            <input type="checkbox" className="mt-1 h-4 w-4 accent-[#00FF88]" checked={noted} onChange={(e) => setNoted(e.target.checked)} />
            Je l'ai noté en lieu sûr.
          </label>
          {info.passphrase_set && <p className="text-xs text-muted">Les copies déjà reçues gardent l'ancien mot de passe.</p>}
          {error && <p className="text-sm text-bear" role="alert">{error}</p>}
          <div className="flex gap-2">
            <button type="button" className="btn-ghost flex-1 justify-center border border-line" onClick={() => { setEditing(false); setError(null) }}>Annuler</button>
            <button type="submit" className="btn-primary flex-1" disabled={!!busy || !noted}>{busy === 'save' ? 'Un instant…' : 'Enregistrer'}</button>
          </div>
        </form>
      )}
    </div>
  )
}
