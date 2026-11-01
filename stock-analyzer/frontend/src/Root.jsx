import { lazy, Suspense, useEffect, useState } from 'react'
import App from './App.jsx'
import { Spinner } from './components/ui'

// /apprendre… : fiches publiques (sans compte) ; tout le reste : l'outil (connexion requise)
const LearnSite = lazy(() => import('./learn/LearnSite.jsx'))
const About = lazy(() => import('./site/StaticPages.jsx').then((m) => ({ default: m.About })))
const Privacy = lazy(() => import('./site/StaticPages.jsx').then((m) => ({ default: m.Privacy })))
const Showcase = lazy(() => import('./site/Showcase.jsx'))
const PUBLIC = { '/a-propos': About, '/confidentialite': Privacy, '/portefeuille-temoin': Showcase }
// Compteur de visites du site public (sans cookie) : le serveur ignore les robots et les membres connectés
let lastReferrer = document.referrer
function countVisit(path) {
  if (import.meta.env.VITE_DEMO === '1') return
  const params = new URLSearchParams(window.location.search)
  const body = JSON.stringify({ path, referrer: lastReferrer || null, ref: params.get('ref') || params.get('utm_source') })
  lastReferrer = window.location.href // navigations suivantes : internes au site
  fetch('/api/public/hit', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true }).catch(() => {})
}

const fallback = <div className="flex min-h-full items-center justify-center"><Spinner /></div>

export default function Root() {
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  const clean = path.replace(/\/+$/, '') || '/'
  useEffect(() => { countVisit(clean) }, [clean])
  if (clean === '/apprendre' || clean.startsWith('/apprendre/')) {
    return <Suspense fallback={fallback}><LearnSite path={clean} /></Suspense>
  }
  const Page = PUBLIC[clean]
  if (Page) return <Suspense fallback={fallback}><Page /></Suspense>
  return <App />
}
