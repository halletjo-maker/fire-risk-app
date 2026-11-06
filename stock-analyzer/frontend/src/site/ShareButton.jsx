import { useState } from 'react'
import { Check, Link2, Share2 } from 'lucide-react'

// Partager une page : menu de partage du téléphone (WhatsApp, Messenger…), sinon WhatsApp + copie du lien.
// ?ref=partage permet au compteur de visites de reconnaître les visiteurs venus d'un partage.
export default function ShareButton({ path, title, text, compact = false }) {
  const [copied, setCopied] = useState(false)
  const [open, setOpen] = useState(false)
  const url = `${window.location.origin}${path}?ref=partage`
  const message = `${text}\n${url}`

  const share = async () => {
    if (navigator.share) {
      try { await navigator.share({ title, text, url }) } catch { /* partage annulé */ }
      return
    }
    setOpen((o) => !o)
  }
  const copy = async () => {
    try { await navigator.clipboard.writeText(url) } catch { window.prompt('Copie ce lien :', url) }
    setCopied(true)
    setTimeout(() => setCopied(false), 2500)
  }

  return (
    <div className={compact ? 'inline-block' : 'mt-6'}>
      <button type="button" onClick={share}
        className={compact ? 'inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-sm text-muted hover:border-bull/60 hover:text-gray-100'
          : 'btn-primary w-full sm:w-auto'}>
        <Share2 className="h-4 w-4" /> {compact ? 'Partager' : 'Partager cette fiche'}
      </button>
      {open && (
        <div className="mt-2 flex flex-wrap gap-2">
          <a className="btn-ghost border border-line text-sm" target="_blank" rel="noreferrer"
            href={`https://wa.me/?text=${encodeURIComponent(message)}`}>WhatsApp</a>
          <a className="btn-ghost border border-line text-sm" target="_blank" rel="noreferrer"
            href={`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`}>Facebook</a>
          <button type="button" className="btn-ghost border border-line text-sm" onClick={copy}>
            {copied ? <><Check className="h-4 w-4 text-bull" /> Lien copié</> : <><Link2 className="h-4 w-4" /> Copier le lien</>}
          </button>
        </div>
      )}
    </div>
  )
}
