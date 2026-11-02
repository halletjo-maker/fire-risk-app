import { useState } from 'react'
import { Check, MessageCircleHeart, Star } from 'lucide-react'
import { api } from '../lib/api'
import Modal from './Modal'

const KINDS = [['avis', '💬 Avis'], ['idee', '💡 Idée'], ['probleme', '🐞 Problème']]

// « Votre avis m'intéresse » : membres (adresse jointe automatiquement) et visiteurs du site
export default function FeedbackModal({ onClose, signedIn = false }) {
  const [kind, setKind] = useState('avis')
  const [rating, setRating] = useState(null)
  const [message, setMessage] = useState('')
  const [email, setEmail] = useState('')
  const [trap, setTrap] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(null)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (message.trim().length < 3) return setError('Écris quelques mots.')
    setBusy(true)
    setError(null)
    try {
      setDone((await api.sendFeedback({
        kind, rating, message: message.trim(), email: !signedIn && email.trim() ? email.trim() : null,
        page: window.location.pathname, website: trap || null,
      })).message)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <Modal title="Votre avis m'intéresse" onClose={onClose}>
      {done ? (
        <div className="mt-4 space-y-4">
          <p className="flex gap-2 rounded-lg border border-bull/40 bg-bull/10 px-3 py-2 text-sm text-bull" role="status"><Check className="mt-0.5 h-4 w-4 shrink-0" /> {done}</p>
          <button className="btn-primary w-full" onClick={onClose}>Fermer</button>
        </div>
      ) : (
        <form onSubmit={submit} noValidate className="mt-2 space-y-3">
          <p className="text-sm text-muted">Une idée, un bug, une page pas claire ? Chaque message est lu et aide à améliorer MM100.</p>
          <div className="grid grid-cols-3 gap-1 rounded-lg bg-bg p-1 text-sm" role="radiogroup" aria-label="Type de message">
            {KINDS.map(([k, l]) => (
              <button key={k} type="button" role="radio" aria-checked={kind === k} onClick={() => setKind(k)}
                className={`rounded-md py-1.5 ${kind === k ? 'bg-panel font-semibold text-gray-100' : 'text-muted'}`}>{l}</button>
            ))}
          </div>
          {kind === 'avis' && (
            <div>
              <p className="text-sm font-medium">Ta note (facultatif)</p>
              <div className="mt-1 flex gap-1" role="radiogroup" aria-label="Note sur 5">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button key={n} type="button" role="radio" aria-checked={rating === n} aria-label={`${n} sur 5`}
                    onClick={() => setRating(rating === n ? null : n)} className="p-1">
                    <Star className={`h-7 w-7 ${rating && n <= rating ? 'fill-[#E8762F] text-[#E8762F]' : 'text-muted'}`} />
                  </button>
                ))}
              </div>
            </div>
          )}
          <label className="block text-sm font-medium" htmlFor="fb-msg">Ton message</label>
          <textarea id="fb-msg" className="input min-h-[120px] resize-y" maxLength={2000} value={message} onChange={(e) => setMessage(e.target.value)}
            placeholder={kind === 'probleme' ? 'Que s’est-il passé ? Sur quelle page ?' : kind === 'idee' ? 'Qu’aimerais-tu voir dans MM100 ?' : 'Ce que tu aimes, ce qui manque…'} />
          {!signedIn && (
            <label className="block text-sm font-medium">Ton adresse mail <span className="font-normal text-muted">(facultatif, pour une réponse)</span>
              <input type="email" inputMode="email" autoCapitalize="none" className="input mt-1" value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
          )}
          <input type="text" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" value={trap}
            onChange={(e) => setTrap(e.target.value)} className="absolute -left-[9999px] h-px w-px opacity-0" />
          {error && <p className="text-sm text-bear" role="alert">{error}</p>}
          <button type="submit" className="btn-primary w-full" disabled={busy}>
            <MessageCircleHeart className="h-4 w-4" /> {busy ? 'Envoi…' : 'Envoyer'}
          </button>
        </form>
      )}
    </Modal>
  )
}
