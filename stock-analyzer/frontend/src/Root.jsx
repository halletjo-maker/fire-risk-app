import { lazy, Suspense, useEffect, useState } from 'react'
import App from './App.jsx'
import { Spinner } from './components/ui'

// /apprendre… : fiches publiques (sans compte) ; tout le reste : l'outil (connexion requise)
const LearnSite = lazy(() => import('./learn/LearnSite.jsx'))

export default function Root() {
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  if (path === '/apprendre' || path.startsWith('/apprendre/')) {
    return (
      <Suspense fallback={<div className="flex min-h-full items-center justify-center"><Spinner /></div>}>
        <LearnSite path={path} />
      </Suspense>
    )
  }
  return <App />
}
