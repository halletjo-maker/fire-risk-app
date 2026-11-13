import { useState } from 'react'
import { Check, KeyRound } from 'lucide-react'
import { api } from '../lib/api'
import PasswordInput from './PasswordInput'
import { PASSWORD_MIN } from './LoginScreen'

export default function PasswordChange() {
  const [open, setOpen] = useState(false)
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (next.length < PASSWORD_MIN) return setError(`Le nouveau mot de passe doit contenir au moins ${PASSWORD_MIN} caractères.`)
    if (next !== confirm) return setError('Les deux nouveaux mots de passe sont différents.')
    setBusy(true)
    setError(null)
    try {
      await api.changePassword(current, next)
      setDone(true)
      setOpen(false)
      setCurrent(''); setNext(''); setConfirm('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <div className="mt-5">
        <button className="btn-ghost w-full justify-center border border-line" onClick={() => { setOpen(true); setDone(false) }}>
          <KeyRound className="h-4 w-4" /> Changer le mot de passe
        </button>
        {done && (
          <p className="mt-2 flex items-center gap-1.5 text-sm text-bull" role="status">
            <Check className="h-4 w-4" /> Mot de passe changé. Tes autres appareils sont déconnectés.
          </p>
        )}
      </div>
    )
  }

  return (
    <form onSubmit={submit} noValidate className="mt-5 rounded-lg border border-line p-4">
      <h3 className="flex items-center gap-2 font-semibold"><KeyRound className="h-4 w-4" /> Changer le mot de passe</h3>
      <label htmlFor="pw-current" className="mt-3 block text-sm font-medium">Mot de passe actuel</label>
      <PasswordInput id="pw-current" value={current} onChange={setCurrent} />
      <label htmlFor="pw-new" className="mt-3 block text-sm font-medium">Nouveau mot de passe</label>
      <PasswordInput id="pw-new" value={next} onChange={setNext} autoComplete="new-password" placeholder={`${PASSWORD_MIN} caractères minimum`} />
      <label htmlFor="pw-confirm" className="mt-3 block text-sm font-medium">Confirme le nouveau mot de passe</label>
      <PasswordInput id="pw-confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" />
      {error && <p className="mt-2 text-sm text-bear" role="alert">{error}</p>}
      <div className="mt-4 flex gap-2">
        <button type="button" className="btn-ghost flex-1 justify-center border border-line" onClick={() => { setOpen(false); setError(null) }}>
          Annuler
        </button>
        <button type="submit" className="btn-primary flex-1" disabled={busy || !current}>
          {busy ? 'Enregistrement…' : 'Enregistrer'}
        </button>
      </div>
    </form>
  )
}
