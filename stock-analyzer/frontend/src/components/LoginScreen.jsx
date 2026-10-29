import { useState } from 'react'
import { ArrowRight, Mail } from 'lucide-react'
import { Logo } from './ui'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

export default function LoginScreen({ onLogin, defaultEmail = '' }) {
  const [email, setEmail] = useState(defaultEmail)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    const value = email.trim()
    if (!EMAIL_RE.test(value)) {
      setError('Adresse mail invalide')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await onLogin(value)
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
          <h1 className="text-xl font-bold">Bienvenue 👋</h1>
          <p className="mt-1 text-sm text-muted">
            Indique ton adresse mail pour retrouver tes watchlists, ton historique et tes alertes.
          </p>
          <label htmlFor="email" className="mt-6 block text-sm font-medium">Adresse mail</label>
          <div className="relative mt-2">
            <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              id="email"
              type="email"
              inputMode="email"
              autoComplete="email"
              autoFocus
              className="input pl-9"
              placeholder="prenom.nom@exemple.be"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          {error && <p className="mt-2 text-sm text-bear">{error}</p>}
          <button type="submit" className="btn-primary mt-6 w-full" disabled={busy}>
            {busy ? 'Connexion…' : 'Commencer'} <ArrowRight className="h-4 w-4" />
          </button>
          <p className="mt-4 text-xs text-muted">
            Pas de mot de passe : l'application tourne sur ton réseau local et se souviendra de toi.
          </p>
        </form>
      </div>
    </div>
  )
}
