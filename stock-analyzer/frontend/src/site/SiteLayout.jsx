import { BookOpen, Info, LogIn } from 'lucide-react'
import { Logo } from '../components/ui'

// Pages publiques : accueil, fiches « Apprendre », à propos, confidentialité
export const LOGIN_URL = '/?connexion=1'

// Navigation sans rechargement (le serveur renvoie la même page pour toutes ces adresses)
export function navigate(href) {
  window.history.pushState(null, '', href)
  window.dispatchEvent(new PopStateEvent('popstate'))
  window.scrollTo(0, 0)
}

export function Link({ href, className, children, ...rest }) {
  return (
    <a href={href} className={className} {...rest}
      onClick={(e) => { if (!e.metaKey && !e.ctrlKey && !rest.target) { e.preventDefault(); navigate(href) } }}>
      {children}
    </a>
  )
}

export function SiteHeader({ onLogin }) {
  const login = onLogin
    ? <button className="btn-primary px-3 py-2 text-sm" onClick={onLogin}><LogIn className="h-4 w-4" /> Se connecter</button>
    : <a href={LOGIN_URL} className="btn-primary px-3 py-2 text-sm"><LogIn className="h-4 w-4" /> Se connecter</a>
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-bg/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="shrink-0" aria-label="Accueil">
          <span className="sm:hidden"><Logo compact /></span>
          <span className="hidden sm:block"><Logo /></span>
        </Link>
        <nav className="flex items-center gap-1 sm:gap-2" aria-label="Navigation principale">
          <Link href="/apprendre" className="btn-ghost px-2.5 py-2 text-sm"><BookOpen className="h-4 w-4" /> Apprendre</Link>
          <Link href="/a-propos" className="btn-ghost hidden px-2.5 py-2 text-sm sm:inline-flex"><Info className="h-4 w-4" /> À propos</Link>
          {login}
        </nav>
      </div>
    </header>
  )
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto max-w-5xl px-4 py-6 text-sm">
        <nav className="flex flex-wrap gap-x-5 gap-y-2 text-muted" aria-label="Liens du site">
          <Link href="/" className="hover:text-gray-100">Accueil</Link>
          <Link href="/apprendre" className="hover:text-gray-100">Apprendre</Link>
          <Link href="/a-propos" className="hover:text-gray-100">À propos</Link>
          <Link href="/confidentialite" className="hover:text-gray-100">Confidentialité</Link>
          <a href={LOGIN_URL} className="hover:text-gray-100">Se connecter</a>
        </nav>
        <p className="mt-4 text-[11px] leading-relaxed text-muted">
          Projet personnel et non commercial, sans publicité. Les informations et analyses fournies sont générées
          automatiquement à partir de sources publiques, à titre d'information générale : elles ne constituent pas un
          conseil en investissement ni une recommandation d'achat ou de vente (MiFID II). Investir comporte un risque
          de perte en capital.
        </p>
      </div>
    </footer>
  )
}

export default function SiteLayout({ children, onLogin }) {
  return (
    <div className="flex min-h-full flex-col">
      <SiteHeader onLogin={onLogin} />
      <div className="flex-1">{children}</div>
      <SiteFooter />
    </div>
  )
}
