import { useEffect } from 'react'
import { X } from 'lucide-react'

// Fenêtre : feuille en bas de l'écran sur mobile, centrée sur PC
export default function Modal({ title, onClose, children, label }) {
  useEffect(() => {
    const esc = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={label || title}>
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="card relative max-h-[90vh] w-full max-w-md overflow-y-auto rounded-b-none p-5 sm:rounded-xl sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-bold">{title}</h2>
          <button className="btn-ghost p-2" onClick={onClose} aria-label="Fermer"><X className="h-5 w-5" /></button>
        </div>
        {children}
      </div>
    </div>
  )
}
