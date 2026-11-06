import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import Modal from './Modal'

export default function ConfirmDialog({ title, message, detail, confirmLabel = 'Confirmer', onConfirm, onClose }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const confirm = async () => {
    setBusy(true)
    try {
      await onConfirm()
      onClose()
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  return (
    <Modal title={title} onClose={onClose} label={title}>
      <p className="mt-4 flex gap-3 text-sm">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-bear" />
        <span><b>{message}</b>{detail && <span className="mt-1 block text-muted">{detail}</span>}</span>
      </p>
      {error && <p className="mt-3 text-sm text-bear">{error}</p>}
      <div className="mt-5 flex gap-2">
        <button className="btn-ghost flex-1 justify-center border border-line" onClick={onClose} disabled={busy}>Annuler</button>
        <button
          className="inline-flex flex-1 items-center justify-center rounded-lg bg-bear px-4 py-2.5 font-semibold text-white transition hover:brightness-110 disabled:opacity-50"
          onClick={confirm}
          disabled={busy}
        >
          {busy ? '…' : confirmLabel}
        </button>
      </div>
    </Modal>
  )
}
