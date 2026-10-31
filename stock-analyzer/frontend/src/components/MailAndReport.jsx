import { useEffect, useState } from 'react'
import { BarChart3, Check, Mail, Send } from 'lucide-react'
import { api } from '../lib/api'
import { Spinner } from './ui'
import PasswordInput from './PasswordInput'

// Rapport mensuel des portefeuilles fictifs (tous les utilisateurs)
export function MonthlyReport({ initial, email }) {
  const [enabled, setEnabled] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)

  const toggle = async () => {
    const next = !enabled
    setEnabled(next)
    try { await api.setPreferences({ monthly_report: next }) } catch { setEnabled(!next) }
  }
  const sendNow = async () => {
    setBusy(true)
    setResult(null)
    try { setResult(await api.sendMonthlyReport()) } catch (e) { setResult({ sent: false, status: e.message }) } finally { setBusy(false) }
  }

  return (
    <div className="mt-5 rounded-lg border border-line p-4">
      <h3 className="flex items-center gap-2 font-semibold"><BarChart3 className="h-4 w-4" /> Rapport mensuel</h3>
      <label className="mt-2 flex cursor-pointer items-start gap-3 text-sm">
        <input type="checkbox" className="mt-1 h-4 w-4 accent-[#00FF88]" checked={enabled} onChange={toggle} />
        <span>
          Recevoir le <b>1er de chaque mois à 8 h</b> la performance du mois précédent de mes portefeuilles fictifs
          <span className="block text-xs text-muted">Envoyé à {email}</span>
        </span>
      </label>
      <button className="btn-ghost mt-3 w-full justify-center border border-line" onClick={sendNow} disabled={busy}>
        {busy ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />} M'envoyer le rapport maintenant
      </button>
      {result && (
        <p className={`mt-2 text-sm ${result.sent ? 'text-bull' : 'text-warn'}`} role="status">
          {result.sent ? `Rapport ${result.label} envoyé à ${result.email}.` : `Non envoyé : ${result.status}`}
        </p>
      )}
    </div>
  )
}

// Compte d'envoi des mails (administrateur) : Gmail + mot de passe d'application
export function MailSettings() {
  const [info, setInfo] = useState(null)
  const [editing, setEditing] = useState(false)
  const [user, setUser] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => { api.mailSettings().then(setInfo).catch((e) => setError(e.message)) }, [])

  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setInfo(await api.saveMailSettings({ user: user.trim(), password }))
      setEditing(false)
      setPassword('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!info && !error) return null
  return (
    <div className="mt-5 rounded-lg border border-line p-4">
      <h3 className="flex items-center gap-2 font-semibold"><Mail className="h-4 w-4" /> Réglages mail</h3>
      {info && !editing && (
        <>
          <p className={`mt-1 flex items-center gap-1.5 text-sm ${info.configured ? 'text-bull' : 'text-warn'}`}>
            {info.configured ? <><Check className="h-4 w-4" /> Envoi actif depuis {info.user}</> : 'Aucun compte d\'envoi : les alertes et rapports ne partent pas.'}
          </p>
          <button className="btn-ghost mt-3 w-full justify-center border border-line" onClick={() => { setEditing(true); setUser(info.user || '') }}>
            {info.configured ? 'Changer de compte d\'envoi' : 'Configurer l\'envoi avec Gmail'}
          </button>
        </>
      )}
      {editing && (
        <form onSubmit={save} className="mt-2 space-y-3">
          <ol className="list-decimal space-y-1 pl-4 text-xs text-muted">
            <li>La <b className="text-gray-200">validation en deux étapes</b> doit être activée sur ton compte Google.</li>
            <li>Ouvre <a className="text-bull underline" href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer">myaccount.google.com/apppasswords</a>, crée un mot de passe nommé « Analyse Boursière ».</li>
            <li>Google affiche <b className="text-gray-200">16 lettres</b> : colle-les ci-dessous (les espaces ne comptent pas).</li>
          </ol>
          <label className="block text-sm font-medium">
            Adresse Gmail d'envoi
            <input className="input mt-2" type="email" autoCapitalize="none" placeholder="prenom.nom@gmail.com" value={user} onChange={(e) => setUser(e.target.value)} required />
          </label>
          <label className="block text-sm font-medium" htmlFor="smtp-pw">Mot de passe d'application (16 lettres)</label>
          <PasswordInput id="smtp-pw" value={password} onChange={setPassword} autoComplete="off" placeholder="abcd efgh ijkl mnop" />
          {error && <p className="text-sm text-bear" role="alert">{error}</p>}
          <div className="flex gap-2">
            <button type="button" className="btn-ghost flex-1 justify-center border border-line" onClick={() => { setEditing(false); setError(null) }}>Annuler</button>
            <button type="submit" className="btn-primary flex-1" disabled={busy || !user || password.replace(/\s/g, '').length < 8}>
              {busy ? 'Vérification…' : 'Vérifier et enregistrer'}
            </button>
          </div>
          <p className="text-[11px] text-muted">Le mot de passe est vérifié auprès de Gmail puis enregistré sur ton serveur ; il n'est jamais réaffiché.</p>
        </form>
      )}
      {error && !editing && <p className="mt-2 text-sm text-bear">{error}</p>}
    </div>
  )
}
