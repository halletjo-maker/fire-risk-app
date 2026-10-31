import { useState } from 'react'
import { ArrowLeft, ArrowRight, Check, Mail, ShieldCheck } from 'lucide-react'
import { api } from '../lib/api'
import { Logo } from './ui'
import PasswordInput from './PasswordInput'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/
export const PASSWORD_MIN = 10

// Modes : login · register (premier compte / ALLOWED_EMAILS) · invite (lien d'invitation)
//         forgot (demande de lien par mail) · reset (nouveau mot de passe depuis le lien reçu)
export default function LoginScreen({ setupRequired, registrationOpen, invitation, reset, notice, onSubmit, onBack }) {
  const [mode, setMode] = useState(reset ? 'reset' : invitation ? 'invite' : setupRequired ? 'register' : 'login')
  const [email, setEmail] = useState(reset?.email || invitation?.email || '')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)
  const [busy, setBusy] = useState(false)
  const invited = mode === 'invite'
  const forgot = mode === 'forgot'
  const resetting = mode === 'reset'
  const newPassword = mode === 'register' || invited || resetting
  const lockedEmail = invited || resetting

  const switchMode = (m) => {
    setMode(m)
    setError(null)
    setInfo(null)
    setPassword('')
    setConfirm('')
  }

  const submit = async (e) => {
    e.preventDefault()
    const value = email.trim()
    if (!EMAIL_RE.test(value)) return setError('Adresse mail invalide.')
    if (forgot) {
      setBusy(true)
      setError(null)
      try { setInfo((await api.forgotPassword(value)).message) } catch (err) { setError(err.message) } finally { setBusy(false) }
      return
    }
    if (!password) return setError('Indique ton mot de passe.')
    if (newPassword) {
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

  const title = invited ? 'Tu es invité 🎉' : resetting ? 'Nouveau mot de passe 🔑' : forgot ? 'Mot de passe oublié'
    : mode === 'register' ? 'Crée ton accès 🔐' : 'Bienvenue 👋'
  const subtitle = invited
    ? `${invitation.invited_by || 'Un membre'} t'invite à utiliser Analyse Boursière. Choisis ton mot de passe pour créer ton compte personnel : tes watchlists et alertes ne sont visibles que par toi.`
    : resetting ? 'Choisis un nouveau mot de passe. Tes autres appareils seront déconnectés.'
      : forgot ? 'Indique l\'adresse de ton compte : tu recevras un lien pour choisir un nouveau mot de passe.'
        : mode === 'register'
          ? 'Choisis ton adresse mail et un mot de passe. Si tu utilisais déjà l\'application avec cette adresse, tu retrouves tes watchlists.'
          : 'Connecte-toi pour retrouver tes watchlists, ton historique et tes alertes.'
  const button = busy ? 'Un instant…' : forgot ? 'Recevoir le lien' : resetting ? 'Enregistrer et me connecter'
    : newPassword ? 'Créer mon accès' : 'Se connecter'

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center"><Logo /></div>
        {onBack && !forgot && (
          <button type="button" onClick={onBack} className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-gray-100">
            <ArrowLeft className="h-4 w-4" /> Retour à l'accueil
          </button>
        )}
        {forgot && (
          <button type="button" onClick={() => switchMode('login')} className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-gray-100">
            <ArrowLeft className="h-4 w-4" /> Retour à la connexion
          </button>
        )}
        <form onSubmit={submit} noValidate className="card p-6 sm:p-8">
          <h1 className="text-xl font-bold">{title}</h1>
          <p className="mt-1 text-sm text-muted">{subtitle}</p>
          {notice && <p className="mt-4 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn" role="status">{notice}</p>}

          <label htmlFor="email" className="mt-6 block text-sm font-medium">Adresse mail</label>
          <div className="relative mt-2">
            <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              id="email"
              type="email"
              inputMode="email"
              autoComplete={newPassword ? 'email' : 'username'}
              autoCapitalize="none"
              className={`input pl-9 ${lockedEmail ? 'opacity-70' : ''}`}
              placeholder="prenom.nom@exemple.be"
              value={email}
              readOnly={lockedEmail}
              aria-readonly={lockedEmail}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          {!forgot && (
            <>
              <label htmlFor="password" className="mt-4 block text-sm font-medium">{resetting ? 'Nouveau mot de passe' : 'Mot de passe'}</label>
              <PasswordInput
                id="password"
                value={password}
                onChange={setPassword}
                autoComplete={newPassword ? 'new-password' : 'current-password'}
                placeholder={newPassword ? `${PASSWORD_MIN} caractères minimum` : ''}
              />
            </>
          )}
          {newPassword && (
            <>
              <label htmlFor="confirm" className="mt-4 block text-sm font-medium">Confirme le mot de passe</label>
              <PasswordInput id="confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" />
            </>
          )}

          {error && <p className="mt-3 text-sm text-bear" role="alert">{error}</p>}
          {info && (
            <p className="mt-4 flex gap-2 rounded-lg border border-bull/40 bg-bull/10 px-3 py-2 text-sm text-bull" role="status">
              <Check className="mt-0.5 h-4 w-4 shrink-0" /> {info}
            </p>
          )}
          {!info && (
            <button type="submit" className="btn-primary mt-6 w-full" disabled={busy}>
              {button} <ArrowRight className="h-4 w-4" />
            </button>
          )}

          {mode === 'login' && (
            <p className="mt-4 text-center text-sm">
              <button type="button" className="text-muted underline-offset-2 hover:underline" onClick={() => switchMode('forgot')}>
                Mot de passe oublié ?
              </button>
            </p>
          )}
          {registrationOpen && !setupRequired && (mode === 'login' || mode === 'register') && (
            <p className="mt-2 text-center text-sm">
              {mode === 'register' ? (
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
          {newPassword && (
            <p className="mt-4 flex gap-2 text-xs text-muted">
              <ShieldCheck className="h-4 w-4 shrink-0" />
              Ton mot de passe est chiffré et ne quitte jamais cette installation. Tu resteras connecté 30 jours sur cet appareil.
            </p>
          )}
        </form>
      </div>
    </div>
  )
}
