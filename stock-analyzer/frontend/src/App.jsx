import { useEffect, useState } from 'react'
import { api, storedEmail } from './lib/api'
import LoginScreen from './components/LoginScreen'
import AppLayout from './components/AppLayout'
import { Spinner } from './components/ui'

export default function App() {
  // undefined = chargement, null = pas d'utilisateur, objet = utilisateur actif
  const [user, setUser] = useState(undefined)
  const [bootError, setBootError] = useState(null)

  const boot = () => {
    setBootError(null)
    setUser(undefined)
    api.currentUser()
      .then(({ user }) => {
        if (user) storedEmail.set(user.email)
        setUser(user)
      })
      .catch((e) => setBootError(e.message))
  }

  useEffect(boot, [])

  const handleLogin = async (email) => {
    const { user } = await api.login(email)
    storedEmail.set(user.email)
    setUser(user)
  }

  const handleLogout = async () => {
    try { await api.logout() } finally {
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
  if (!user) return <LoginScreen onLogin={handleLogin} defaultEmail={storedEmail.get() || ''} />
  return <AppLayout user={user} onLogout={handleLogout} />
}
