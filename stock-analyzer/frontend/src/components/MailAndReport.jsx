import { useEffect, useState } from 'react'
import { BarChart3, Check, Mail, Send } from 'lucide-react'
import { api } from '../lib/api'
import { Spinner } from './ui'
import PasswordInput from './PasswordInput'

// Rapport mensuel des portefeuilles fictifs (tous les utilisateurs)
export function MonthlyReport({ initial, email }) {
  const [enabled, setEnabled] = useState(initial)
  const [busy, setBusy] = useState(null)
  const [result, setResult] = useState(null)

  const toggle = async () => {
    const next = !enabled
    setEnabled(next)
    try { await api.setPreferences({ monthly_report: next }) } catch { setEnabled(!next) }
  }
  const sendNow = async (period) => {
    setBusy(period)
    setResult(null)
    try { setResult(await api.sendMonthlyReport(period)) } catch (e) { setResult({ sent: false, status: e.message }) } finally { setBusy(null) }
  }
  const today = new Date().toLocaleDateString('fr-BE', { day: 'numeric', month: 'long' })

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
      <p className="mt-3 text-xs font-medium text-muted">M'envoyer un rapport maintenant :</p>
      <div className="mt-1.5 grid grid-cols-2 gap-2">
        <button className="btn-ghost justify-center border border-line text-sm" onClick={() => sendNow('current')} disabled={!!busy}>
          {busy === 'current' ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />}
          <span className="text-left leading-tight">Mois en cours<span className="block text-[11px] text-muted">du 1er au {today}</span></span>
        </button>
        <button className="btn-ghost justify-center border border-line text-sm" onClick={() => sendNow('previous')} disabled={!!busy}>
          {busy === 'previous' ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />}
          <span className="text-left leading-tight">Mois dernier<span className="block text-[11px] text-muted">mois complet</span></span>
        </button>
      </div>
      {result && (
        <p className={`mt-2 text-sm ${result.sent ? 'text-bull' : 'text-warn'}`} role="status">
          {result.sent ? `Rapport ${result.label} envoyé à ${result.email}.` : `Non envoyé : ${result.status}`}
        </p>
      )}
    </div>
  )
}

// Compte d'envoi des mails (administrateur) : Gmail (mot de passe d'application) ou adresse du domaine chez OVHcloud
export function MailSettings() {
  const [info, setInfo] = useState(null)
  const [editing, setEditing] = useState(false)
  const [provider, setProvider] = useState('ovh')
  const [user, setUser] = useState('')
  const [password, setPassword] = useState('')
  const gmail = provider === 'gmail'
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => { api.mailSettings().then(setInfo).catch((e) => setError(e.message)) }, [])

  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setInfo(await api.saveMailSettings({ user: user.trim(), password, provider }))
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
          <button className="btn-ghost mt-3 w-full justify-center border border-line" onClick={() => { setEditing(true); setProvider(info.provider || 'ovh'); setUser(info.user || '') }}>
            {info.configured ? 'Changer de compte d\'envoi' : 'Configurer l\'envoi des mails'}
          </button>
        </>
      )}
      {editing && (
        <form onSubmit={save} className="mt-2 space-y-3">
          <div className="grid grid-cols-2 gap-1 rounded-lg bg-bg p-1 text-sm" role="radiogroup" aria-label="Fournisseur">
            {[['ovh', 'Mon domaine (OVHcloud)'], ['gmail', 'Gmail']].map(([id, label]) => (
              <button key={id} type="button" role="radio" aria-checked={provider === id}
                className={`rounded-md px-2 py-1.5 ${provider === id ? 'bg-panel font-semibold text-gray-100' : 'text-muted'}`}
                onClick={() => { setProvider(id); setError(null) }}>{label}</button>
            ))}
          </div>
          {gmail ? (
            <ol className="list-decimal space-y-1 pl-4 text-xs text-muted">
              <li>La <b className="text-gray-200">validation en deux étapes</b> doit être activée sur ton compte Google.</li>
              <li>Ouvre <a className="text-bull underline" href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer">myaccount.google.com/apppasswords</a>, crée un mot de passe nommé « Analyse Boursière ».</li>
              <li>Google affiche <b className="text-gray-200">16 lettres</b> : colle-les ci-dessous (les espaces ne comptent pas).</li>
            </ol>
          ) : (
            <ol className="list-decimal space-y-1 pl-4 text-xs text-muted">
              <li>Dans OVHcloud, crée la boîte mail (ex. <b className="text-gray-200">contact@mm100.be</b>) incluse avec ton domaine.</li>
              <li>Indique ci-dessous cette adresse et le mot de passe choisi pour elle.</li>
              <li>Tes invités verront cette adresse comme expéditeur, plus ton Gmail.</li>
            </ol>
          )}
          <label className="block text-sm font-medium">
            Adresse d'envoi
            <input className="input mt-2" type="email" autoCapitalize="none" placeholder={gmail ? 'prenom.nom@gmail.com' : 'contact@mm100.be'} value={user} onChange={(e) => setUser(e.target.value)} required />
          </label>
          <label className="block text-sm font-medium" htmlFor="smtp-pw">{gmail ? 'Mot de passe d\'application (16 lettres)' : 'Mot de passe de cette boîte mail'}</label>
          <PasswordInput id="smtp-pw" value={password} onChange={setPassword} autoComplete="off" placeholder={gmail ? 'abcd efgh ijkl mnop' : ''} />
          {error && <p className="text-sm text-bear" role="alert">{error}</p>}
          <div className="flex gap-2">
            <button type="button" className="btn-ghost flex-1 justify-center border border-line" onClick={() => { setEditing(false); setError(null) }}>Annuler</button>
            <button type="submit" className="btn-primary flex-1" disabled={busy || !user || password.replace(/\s/g, '').length < 8}>
              {busy ? 'Vérification…' : 'Vérifier et enregistrer'}
            </button>
          </div>
          <p className="text-[11px] text-muted">Le mot de passe est vérifié auprès de {gmail ? 'Gmail' : 'OVHcloud'} puis enregistré sur ton serveur ; il n'est jamais réaffiché.</p>
        </form>
      )}
      {error && !editing && <p className="mt-2 text-sm text-bear">{error}</p>}
    </div>
  )
}
