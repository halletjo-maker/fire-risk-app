import { useEffect, useState } from 'react'
import { LogOut, UserRound, X } from 'lucide-react'
import { api } from '../lib/api'
import { Spinner } from './ui'
import AlertsSection from './AlertsSection'
import PasswordChange from './PasswordChange'
import ServerUpdate from './ServerUpdate'
import { MailSettings, MonthlyReport } from './MailAndReport'

const fmt = (iso) => {
  if (!iso) return '—'
  // SQLite renvoie "AAAA-MM-JJ HH:MM:SS" en UTC
  const d = new Date(iso.replace(' ', 'T') + 'Z')
  return d.toLocaleString('fr-BE', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function ProfileModal({ onClose, onLogout }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.me().then(setData).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    const esc = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [onClose])

  const stats = data && [
    ['Watchlists', data.stats.watchlists],
    ['Produits suivis', data.stats.products],
    ['Alertes actives', data.stats.active_alerts],
    ['Analyses', data.stats.analyses],
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label="Mon profil">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="card relative max-h-[90vh] w-full max-w-md overflow-y-auto rounded-b-none p-5 sm:rounded-xl sm:p-6">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-bold"><UserRound className="h-5 w-5" /> Mon profil</h2>
          <button className="btn-ghost p-2" onClick={onClose} aria-label="Fermer"><X className="h-5 w-5" /></button>
        </div>

        {error && <p className="mt-4 text-sm text-bear">{error}</p>}
        {!data && !error && <div className="flex justify-center py-10"><Spinner /></div>}

        {data && (
          <>
            <div className="mt-4 flex items-center gap-3">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-bull/15 text-xl font-bold text-bull">
                {data.user.email[0].toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-xs text-muted">Adresse mail active</p>
                <p className="truncate font-medium">{data.user.email}</p>
              </div>
            </div>

            <dl className="mt-4 space-y-1 text-sm">
              <div className="flex justify-between gap-2"><dt className="text-muted">Membre depuis</dt><dd className="whitespace-nowrap text-right">{fmt(data.user.created_at)}</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-muted">Dernière connexion</dt><dd className="whitespace-nowrap text-right">{fmt(data.user.last_login_at)}</dd></div>
            </dl>

            <div className="mt-4 grid grid-cols-2 gap-2">
              {stats.map(([label, value]) => (
                <div key={label} className="rounded-lg bg-bg p-3">
                  <p className="text-2xl font-bold">{value}</p>
                  <p className="text-xs text-muted">{label}</p>
                </div>
              ))}
            </div>

            <AlertsSection />
            <p className="mt-4 text-xs text-muted">
              Les alertes mail sont envoyées à cette adresse. Tes données restent sur cette
              installation, même après une déconnexion.
            </p>
            <MonthlyReport initial={data.preferences?.monthly_report ?? true} email={data.user.email} />
            {data.user.is_admin && <MailSettings />}
            <PasswordChange />
            {data.user.is_admin && <ServerUpdate />}
          </>
        )}

        <button
          className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-bear/50 px-4 py-2.5 font-semibold text-bear transition hover:bg-bear/10"
          onClick={onLogout}
        >
          <LogOut className="h-4 w-4" /> Se déconnecter
        </button>
      </div>
    </div>
  )
}
