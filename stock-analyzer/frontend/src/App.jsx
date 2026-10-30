import { useEffect, useState } from 'react'
import { api, SESSION_EXPIRED } from './lib/api'
import LoginScreen from './components/LoginScreen'
import AppLayout from './components/AppLayout'
import { Spinner } from './components/ui'

// Lien d'invitation : https://…/?invitation=JETON
function invitationToken() {
  try { return new URLSearchParams(window.location.search).get('invitation') } catch { return null }
}
function clearInvitationFromUrl() {
  try {
    const url = new URL(window.location.href)
    url.searchParams.delete('invitation')
    window.history.replaceState(null, '', url.pathname + url.search + url.hash)
  } catch { /* sans importance */ }
}

export default function App() {
  // undefined = chargement, null = pas connecté, objet = utilisateur connecté
  const [user, setUser] = useState(undefined)
  const [auth, setAuth] = useState({ setup_required: false, registration_open: false })
  const [invitation, setInvitation] = useState(null) // { token, email, invited_by }
  const [notice, setNotice] = useState(null)
  const [bootError, setBootError] = useState(null)

  const boot = async () => {
    setBootError(null)
    setUser(undefined)
    try {
      const { user, setup_required, registration_open } = await api.currentUser()
      const token = invitationToken()
      if (token && !user) {
        try {
          const info = await api.invitationInfo(token)
          setInvitation({ token, ...info })
        } catch (e) {
          setNotice(e.message)
          clearInvitationFromUrl()
        }
      } else if (token) {
        clearInvitationFromUrl() // déjà connecté sur cet appareil
      }
      setAuth({ setup_required, registration_open })
      setUser(user)
    } catch (e) {
      setBootError(e.message)
    }
  }

  useEffect(() => { boot() }, [])

  // Une requête refusée (session expirée, mot de passe changé ailleurs) ramène à la connexion
  useEffect(() => {
    const expired = () => {
      setUser((u) => {
        if (u) setNotice('Ta session a expiré : reconnecte-toi.')
        return null
      })
    }
    window.addEventListener(SESSION_EXPIRED, expired)
    return () => window.removeEventListener(SESSION_EXPIRED, expired)
  }, [])

  const handleAuth = async (mode, email, password) => {
    let res
    if (mode === 'invite') res = await api.register(email, password, invitation.token)
    else if (mode === 'register') res = await api.register(email, password)
    else res = await api.login(email, password)
    if (mode === 'invite') { clearInvitationFromUrl(); setInvitation(null) }
    setNotice(null)
    setAuth({ setup_required: false, registration_open: auth.registration_open && mode !== 'register' })
    setUser(res.user)
  }

  const handleLogout = async () => {
    try { await api.logout() } catch { /* serveur injoignable : on déconnecte quand même */ } finally {
      setNotice(null)
      setUser(null)
    }
  }

  if (bootError) {
    return (
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="card max-w-sm p-6 text-center">
          <p className="font-semibold text-bear">Connexion au serveur impossible</p>
          <p className="mt-2 text-sm text-muted">{bootError}</p>
          <button className="btn-primary mt-4 w-full" onClick={boot}>Réessayer</button>
        </div>
      </div>
    )
  }
  if (user === undefined) {
    return <div className="flex min-h-full items-center justify-center"><Spinner /></div>
  }
  if (!user) {
    return (
      <LoginScreen
        setupRequired={auth.setup_required}
        registrationOpen={auth.registration_open}
        invitation={invitation}
        notice={notice}
        onSubmit={handleAuth}
      />
    )
  }
  return <AppLayout user={user} onLogout={handleLogout} />
}
