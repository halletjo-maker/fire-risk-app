import { useEffect, useState } from 'react'
import { MessageCircleHeart, Trash2 } from 'lucide-react'
import { api } from '../lib/api'

const KIND = { idee: '💡 Idée', probleme: '🐞 Problème', avis: '💬 Avis' }
const when = (sql) => new Date(sql.replace(' ', 'T') + 'Z').toLocaleString('fr-BE', { dateStyle: 'medium', timeStyle: 'short' })

// Administrateur : avis reçus des membres et des visiteurs
export default function FeedbackInbox() {
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(false)
  useEffect(() => { api.feedbackList().then(setData).catch(() => {}) }, [])
  if (!data) return null
  const toggle = async () => {
    setOpen(!open)
    if (!open && data.unread) setData(await api.feedbackRead())
  }
  return (
    <div className="mt-5 rounded-lg border border-line p-4">
      <button className="flex w-full items-center justify-between" onClick={toggle} aria-expanded={open}>
        <h3 className="flex items-center gap-2 font-semibold"><MessageCircleHeart className="h-4 w-4" /> Avis reçus</h3>
        <span className="text-sm text-muted">
          {data.unread > 0 && <span className="mr-2 rounded-full bg-[#E8762F] px-2 py-0.5 text-xs font-semibold text-black">{data.unread} nouveau{data.unread > 1 ? 'x' : ''}</span>}
          {data.feedback.length}
        </span>
      </button>
      {open && (
        data.feedback.length === 0 ? <p className="mt-2 text-sm text-muted">Aucun avis pour l'instant.</p> : (
          <ul className="mt-2 divide-y divide-line">
            {data.feedback.map((f) => (
              <li key={f.id} className="flex gap-2 py-2.5 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted">
                    {KIND[f.kind] || f.kind}{f.rating ? ` · ${'★'.repeat(f.rating)}${'☆'.repeat(5 - f.rating)}` : ''} · {f.email || 'anonyme'} · {when(f.created_at)}{f.page ? ` · ${f.page}` : ''}
                  </p>
                  <p className="mt-0.5 whitespace-pre-wrap">{f.message}</p>
                  {f.email && <a className="mt-1 inline-block text-xs text-bull underline" href={`mailto:${f.email}?subject=${encodeURIComponent('Ton avis sur MM100')}`}>Répondre</a>}
                </div>
                <button className="shrink-0 self-start rounded-md p-2 text-muted hover:bg-bear/10 hover:text-bear" aria-label="Supprimer l'avis"
                  onClick={async () => setData(await api.deleteFeedback(f.id))}><Trash2 className="h-4 w-4" /></button>
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  )
}
