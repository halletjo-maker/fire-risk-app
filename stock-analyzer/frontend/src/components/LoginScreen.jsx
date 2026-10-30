import { useState } from 'react'
import { ArrowRight, Mail, ShieldCheck } from 'lucide-react'
import { Logo } from './ui'
import PasswordInput from './PasswordInput'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/
export const PASSWORD_MIN = 10

export default function LoginScreen({ setupRequired, registrationOpen, invitation, notice, onSubmit }) {
  // Invitation : création du mot de passe pour l'adresse invitée ;
  // première utilisation : création du compte administrateur ; ensuite : connexion
  const [mode, setMode] = useState(invitation ? 'invite' : setupRequired ? 'register' : 'login')
  const [email, setEmail] = useState(invitation?.email || '')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const invited = mode === 'invite'
  const register = mode === 'register' || invited

  const switchMode = (m) => {
    setMode(m)
    setError(null)
    setPassword('')
    setConfirm('')
  }

  const submit = async (e) => {
    e.preventDefault()
    const value = email.trim()
    if (!EMAIL_RE.test(value)) return setError('Adresse mail invalide.')
    if (!password) return setError('Indique ton mot de passe.')
    if (register) {
      if (password.length < PASSWORD_MIN) return setError(`Le mot de passe doit contenir au moins ${PASSWORD_MIN} caractères.`)
      if (password !== confirm) return setError('Les deux mots de passe sont différents.')
    }
    setBusy(true)
    setError(null)
    try {
      await onSubmit(mode, value, password)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center"><Logo /></div>
        <form onSubmit={submit} noValidate className="card p-6 sm:p-8">
          <h1 className="text-xl font-bold">{invited ? 'Tu es invité 🎉' : register ? 'Crée ton accès 🔐' : 'Bienvenue 👋'}</h1>
          <p className="mt-1 text-sm text-muted">
            {invited
              ? `${invitation.invited_by || 'Un membre'} t'invite à utiliser Analyse Boursière. Choisis ton mot de passe pour créer ton compte personnel : tes watchlists et alertes ne sont visibles que par toi.`
              : register
                ? 'Choisis ton adresse mail et un mot de passe. Si tu utilisais déjà l\'application avec cette adresse, tu retrouves tes watchlists.'
                : 'Connecte-toi pour retrouver tes watchlists, ton historique et tes alertes.'}
          </p>
          {notice && <p className="mt-4 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn" role="status">{notice}</p>}

          <label htmlFor="email" className="mt-6 block text-sm font-medium">Adresse mail</label>
          <div className="relative mt-2">
            <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              id="email"
              type="email"
              inputMode="email"
              autoComplete={register ? 'email' : 'username'}
              autoCapitalize="none"
              className={`input pl-9 ${invited ? 'opacity-70' : ''}`}
              placeholder="prenom.nom@exemple.be"
              value={email}
              readOnly={invited}
              aria-readonly={invited}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <label htmlFor="password" className="mt-4 block text-sm font-medium">Mot de passe</label>
          <PasswordInput
            id="password"
            value={password}
            onChange={setPassword}
            autoComplete={register ? 'new-password' : 'current-password'}
            placeholder={register ? `${PASSWORD_MIN} caractères minimum` : ''}
          />
          {register && (
            <>
              <label htmlFor="confirm" className="mt-4 block text-sm font-medium">Confirme le mot de passe</label>
              <PasswordInput id="confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" />
            </>
          )}

          {error && <p className="mt-3 text-sm text-bear" role="alert">{error}</p>}
          <button type="submit" className="btn-primary mt-6 w-full" disabled={busy}>
            {busy ? 'Connexion…' : register ? 'Créer mon accès' : 'Se connecter'} <ArrowRight className="h-4 w-4" />
          </button>

          {registrationOpen && !setupRequired && !invited && (
            <p className="mt-4 text-center text-sm">
              {register ? (
                <button type="button" className="text-muted underline-offset-2 hover:underline" onClick={() => switchMode('login')}>
                  J'ai déjà un mot de passe
                </button>
              ) : (
                <button type="button" className="text-muted underline-offset-2 hover:underline" onClick={() => switchMode('register')}>
                  Première connexion ? Crée ton mot de passe
                </button>
              )}
            </p>
          )}
          <p className="mt-4 flex gap-2 text-xs text-muted">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            {register
              ? 'Ton mot de passe est chiffré et ne quitte jamais cette installation. Tu resteras connecté 30 jours sur cet appareil.'
              : 'Mot de passe oublié ? Lance reset_password.bat sur le PC qui fait tourner l\'application.'}
          </p>
        </form>
      </div>
    </div>
  )
}
