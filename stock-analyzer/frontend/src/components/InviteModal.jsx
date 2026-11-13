import { useEffect, useState } from 'react'
import { Check, Copy, Mail, Send, Share2, ShieldCheck, Trash2, UserPlus, X } from 'lucide-react'
import { api } from '../lib/api'
import Modal from './Modal'
import ConfirmDialog from './ConfirmDialog'
import { Spinner } from './ui'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/
const canShare = typeof navigator !== 'undefined' && !!navigator.share

const fmtDate = (sql) => {
  if (!sql) return '—'
  const d = new Date(sql.replace(' ', 'T') + 'Z')
  return d.toLocaleDateString('fr-BE', { day: 'numeric', month: 'short', year: 'numeric' })
}

function InvitationLink({ result, onDone }) {
  const [copied, setCopied] = useState(false)
  const message = `Je t'invite à utiliser Analyse Boursière. Crée ton mot de passe avec ce lien personnel (valable 7 jours) : ${result.link}`

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(result.link)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* presse-papiers refusé : le lien reste sélectionnable */ }
  }
  const share = async () => {
    try { await navigator.share({ title: 'Invitation : Analyse Boursière', text: message }) } catch { /* partage annulé */ }
  }

  return (
    <div className="mt-4 rounded-lg border border-bull/40 bg-bull/5 p-4">
      <p className="flex items-center gap-2 font-semibold text-bull"><Check className="h-4 w-4" /> Invitation créée pour {result.invitation.email}</p>
      <p className="mt-1 text-sm text-muted">
        {result.mail.sent
          ? 'Un mail avec le lien vient de lui être envoyé. Tu peux aussi lui transmettre le lien toi-même.'
          : 'Les mails ne sont pas encore configurés : envoie-lui ce lien toi-même (WhatsApp, SMS, mail…).'}
      </p>
      <input
        readOnly
        value={result.link}
        onFocus={(e) => e.target.select()}
        className="input mt-3 font-mono text-xs"
        aria-label="Lien d'invitation"
      />
      <div className="mt-3 flex gap-2">
        <button className="btn-ghost flex-1 justify-center border border-line" onClick={copy}>
          {copied ? <><Check className="h-4 w-4 text-bull" /> Copié</> : <><Copy className="h-4 w-4" /> Copier</>}
        </button>
        {canShare && (
          <button className="btn-primary flex-1" onClick={share}>
            <Share2 className="h-4 w-4" /> Partager
          </button>
        )}
      </div>
      <p className="mt-3 flex gap-2 text-xs text-muted">
        <ShieldCheck className="h-4 w-4 shrink-0" />
        Lien personnel à usage unique, valable 7 jours, réservé à cette adresse mail.
      </p>
      <button className="mt-2 text-sm text-muted underline-offset-2 hover:underline" onClick={onDone}>
        Inviter quelqu'un d'autre
      </button>
    </div>
  )
}

export default function InviteModal({ onClose }) {
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [data, setData] = useState(null)
  const [removing, setRemoving] = useState(null)

  const [requests, setRequests] = useState([])
  const [reqBusy, setReqBusy] = useState(null)
  const load = () => {
    api.members().then(setData).catch((e) => setError(e.message))
    api.accessRequests().then((r) => setRequests(r.requests)).catch(() => {})
  }
  useEffect(() => { load() }, [])

  const answer = async (req, accept) => {
    setReqBusy(req.id)
    setError(null)
    try {
      if (accept) setResult(await api.acceptAccessRequest(req.id))
      else await api.declineAccessRequest(req.id)
      load()
    } catch (e) { setError(e.message) } finally { setReqBusy(null) }
  }

  const submit = async (e) => {
    e.preventDefault()
    const value = email.trim()
    if (!EMAIL_RE.test(value)) return setError('Adresse mail invalide.')
    setBusy(true)
    setError(null)
    try {
      setResult(await api.invite(value))
      setEmail('')
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const cancel = async (inv) => {
    try { await api.cancelInvitation(inv.id); load() } catch (e) { setError(e.message) }
  }

  return (
    <Modal title="Inviter un ami" onClose={onClose}>
      <p className="mt-2 text-sm text-muted">
        Ton ami aura son propre compte : ses watchlists et ses alertes ne sont visibles que par lui, et il ne voit pas les tiennes.
      </p>

      {result ? (
        <InvitationLink result={result} onDone={() => setResult(null)} />
      ) : (
        <form onSubmit={submit} noValidate className="mt-4">
          <label htmlFor="invite-email" className="block text-sm font-medium">Adresse mail de ton ami</label>
          <div className="relative mt-2">
            <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              id="invite-email"
              type="email"
              inputMode="email"
              autoComplete="off"
              autoCapitalize="none"
              className="input pl-9"
              placeholder="prenom.nom@exemple.be"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          {error && <p className="mt-2 text-sm text-bear" role="alert">{error}</p>}
          <button type="submit" className="btn-primary mt-4 w-full" disabled={busy}>
            {busy ? 'Création…' : <><Send className="h-4 w-4" /> Créer l'invitation</>}
          </button>
        </form>
      )}

      {requests.length > 0 && (
        <div className="mt-6 border-t border-line pt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Demandes d'accès ({requests.length})</h3>
          <p className="mt-1 text-xs text-muted">Déposées depuis la page d'accueil. Accepter envoie une invitation sans ton adresse ; refuser efface la demande sans prévenir.</p>
          <ul className="mt-2 divide-y divide-line">
            {requests.map((r) => (
              <li key={r.id} className="py-2.5">
                <p className="truncate text-sm font-medium">{r.email}</p>
                <p className="text-xs text-muted">Le {fmtDate(r.created_at)}{r.message ? ` · « ${r.message} »` : ''}</p>
                <div className="mt-2 flex gap-2">
                  <button className="btn-primary flex-1 py-1.5 text-sm" disabled={reqBusy === r.id} onClick={() => answer(r, true)}>
                    {reqBusy === r.id ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />} Inviter
                  </button>
                  <button className="btn-ghost flex-1 justify-center border border-line py-1.5 text-sm" disabled={reqBusy === r.id} onClick={() => answer(r, false)}>
                    <X className="h-4 w-4" /> Refuser
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-6 border-t border-line pt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Membres</h3>
        {!data && <div className="flex justify-center py-4"><Spinner className="h-5 w-5" /></div>}
        {data && (
          <ul className="mt-2 divide-y divide-line">
            {data.members.map((m) => (
              <li key={m.id} className="flex items-center gap-3 py-2.5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-bull/15 text-sm font-semibold text-bull">
                  {m.email[0].toUpperCase()}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm">{m.email}{m.is_me && <span className="text-muted"> (toi)</span>}</span>
                  <span className="block text-xs text-muted">
                    {m.is_admin ? 'Administrateur' : 'Membre'} · {m.active ? `dernière connexion ${fmtDate(m.last_login_at)}` : 'mot de passe pas encore créé'}
                  </span>
                </span>
                {!m.is_admin && (
                  <button
                    className="shrink-0 rounded-md p-2 text-muted transition hover:bg-bear/10 hover:text-bear"
                    onClick={() => setRemoving(m)}
                    aria-label={`Retirer l'accès de ${m.email}`}
                    title="Retirer l'accès"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {data?.invitations.length > 0 && (
          <>
            <h3 className="mt-4 text-xs font-semibold uppercase tracking-wider text-muted">Invitations en attente</h3>
            <ul className="mt-2 divide-y divide-line">
              {data.invitations.map((i) => (
                <li key={i.id} className="flex items-center gap-3 py-2.5">
                  <UserPlus className="h-4 w-4 shrink-0 text-muted" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm">{i.email}</span>
                    <span className="block text-xs text-muted">Valable jusqu'au {fmtDate(i.expires_at)}</span>
                  </span>
                  <button
                    className="shrink-0 rounded-md p-2 text-muted transition hover:bg-bear/10 hover:text-bear"
                    onClick={() => cancel(i)}
                    aria-label={`Annuler l'invitation de ${i.email}`}
                    title="Annuler l'invitation"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {removing && (
        <ConfirmDialog
          title="Retirer l'accès"
          message={`Retirer l'accès de ${removing.email} ?`}
          detail="Son compte, ses watchlists et ses alertes seront supprimés définitivement. Tu pourras l'inviter à nouveau plus tard."
          confirmLabel="Retirer"
          onConfirm={async () => { await api.removeMember(removing.id); load() }}
          onClose={() => setRemoving(null)}
        />
      )}
    </Modal>
  )
}
