import { lazy, Suspense, useEffect, useState } from 'react'
import App from './App.jsx'
import { Spinner } from './components/ui'

// /apprendre… : fiches publiques (sans compte) ; tout le reste : l'outil (connexion requise)
const LearnSite = lazy(() => import('./learn/LearnSite.jsx'))
const About = lazy(() => import('./site/StaticPages.jsx').then((m) => ({ default: m.About })))
const Privacy = lazy(() => import('./site/StaticPages.jsx').then((m) => ({ default: m.Privacy })))
const Showcase = lazy(() => import('./site/Showcase.jsx'))
const PUBLIC = { '/a-propos': About, '/confidentialite': Privacy, '/portefeuille-temoin': Showcase }
const fallback = <div className="flex min-h-full items-center justify-center"><Spinner /></div>

export default function Root() {
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  const clean = path.replace(/\/+$/, '') || '/'
  if (clean === '/apprendre' || clean.startsWith('/apprendre/')) {
    return <Suspense fallback={fallback}><LearnSite path={clean} /></Suspense>
  }
  const Page = PUBLIC[clean]
  if (Page) return <Suspense fallback={fallback}><Page /></Suspense>
  return <App />
}
