import { useEffect } from 'react'
import { AlertTriangle, ArrowLeft, ArrowRight, BookOpen, Clock, Cpu, Lightbulb, LineChart } from 'lucide-react'
import { Logo } from '../components/ui'
import { CATEGORIES, FICHES, FICHES_BY_SLUG } from './fiches'
import Illustration from './Illustrations'

export const LEARN_ROOT = '/apprendre'
export const ficheUrl = (slug) => `${LEARN_ROOT}/${slug}`

// Navigation sans rechargement (le serveur renvoie la même page pour toutes ces adresses)
export function navigate(href) {
  window.history.pushState(null, '', href)
  window.dispatchEvent(new PopStateEvent('popstate'))
  window.scrollTo(0, 0)
}

function Link({ href, className, children, ...rest }) {
  return (
    <a href={href} className={className} {...rest}
      onClick={(e) => { if (!e.metaKey && !e.ctrlKey) { e.preventDefault(); navigate(href) } }}>
      {children}
    </a>
  )
}

function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-bg/95 backdrop-blur">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3">
        <Link href={LEARN_ROOT} className="flex items-center gap-2" aria-label="Accueil des fiches">
          <Logo compact />
          <span className="text-sm font-semibold text-muted">Apprendre</span>
        </Link>
        <a href="/" className="btn-primary px-3 py-2 text-sm"><LineChart className="h-4 w-4" /> Ouvrir l'outil</a>
      </div>
    </header>
  )
}

function Footer() {
  return (
    <footer className="mx-auto max-w-3xl px-4 pb-10 pt-6 text-center text-[11px] leading-relaxed text-muted">
      Contenu pédagogique, à but d'information générale. Il ne constitue pas un conseil en investissement
      ni une recommandation d'achat ou de vente (MiFID II). Investir comporte un risque de perte en capital.
    </footer>
  )
}

function Index() {
  useEffect(() => { document.title = 'Apprendre — fiches pour comprendre la Bourse' }, [])
  return (
    <main className="mx-auto max-w-3xl px-4 py-6">
      <h1 className="flex items-center gap-2 text-2xl font-bold"><BookOpen className="h-6 w-6 text-bull" /> Comprendre les analyses</h1>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        Des fiches courtes pour comprendre ce que mesurent les indicateurs, comment les lire, leurs pièges — et
        exactement comment l'outil d'analyse s'en sert.
      </p>
      {CATEGORIES.map((cat) => (
        <section key={cat.key} className="mt-8" aria-labelledby={`cat-${cat.key}`}>
          <h2 id={`cat-${cat.key}`} className="text-xs font-semibold uppercase tracking-wider text-muted">{cat.label}</h2>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {FICHES.filter((f) => f.category === cat.key).map((f) => (
              <li key={f.slug}>
                <Link href={ficheUrl(f.slug)} className="card block h-full p-4 transition hover:border-bull/60">
                  <p className="flex items-start gap-2 font-semibold">
                    <span aria-hidden="true">{f.emoji}</span><span>{f.title}</span>
                  </p>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted">{f.oneLiner}</p>
                  <p className="mt-2 flex items-center gap-1 text-xs text-muted"><Clock className="h-3.5 w-3.5" /> {f.minutes} min de lecture</p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </main>
  )
}

function Block({ icon: Icon, title, tone = 'muted', children }) {
  const tones = {
    muted: 'border-line bg-panel',
    app: 'border-[#3987e5]/40 bg-[#3987e5]/10',
    warn: 'border-warn/40 bg-warn/10',
    key: 'border-bull/40 bg-bull/10',
  }
  return (
    <section className={`mt-5 rounded-xl border p-4 ${tones[tone]}`}>
      <h2 className="flex items-center gap-2 font-semibold"><Icon className="h-4 w-4" /> {title}</h2>
      <div className="mt-2">{children}</div>
    </section>
  )
}

const List = ({ items }) => (
  <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed">
    {items.map((t) => <li key={t}>{t}</li>)}
  </ul>
)

function Fiche({ fiche }) {
  useEffect(() => { document.title = `${fiche.title} — Apprendre` }, [fiche])
  const i = FICHES.indexOf(fiche)
  const prev = FICHES[i - 1]
  const next = FICHES[i + 1]
  const cat = CATEGORIES.find((c) => c.key === fiche.category)
  return (
    <main className="mx-auto max-w-3xl px-4 py-6">
      <Link href={LEARN_ROOT} className="inline-flex items-center gap-1 text-sm text-muted hover:text-gray-100">
        <ArrowLeft className="h-4 w-4" /> Toutes les fiches
      </Link>
      <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-muted">{cat?.label} · {fiche.minutes} min</p>
      <h1 className="mt-1 text-2xl font-bold leading-tight"><span aria-hidden="true">{fiche.emoji}</span> {fiche.title}</h1>
      <p className="mt-3 rounded-lg border-l-4 border-bull bg-panel px-4 py-3 text-[15px] leading-relaxed">
        <b>En une phrase :</b> {fiche.oneLiner}
      </p>

      <div className="mt-5 space-y-3 text-[15px] leading-relaxed text-gray-200">
        {fiche.intro.map((p) => <p key={p}>{p}</p>)}
      </div>
      {fiche.illustration && <Illustration name={fiche.illustration} />}

      {fiche.sections.map((s) => (
        <section key={s.title} className="mt-6">
          <h2 className="text-lg font-semibold">{s.title}</h2>
          <div className="mt-2 space-y-2 text-[15px] leading-relaxed text-gray-200">
            {s.paras?.map((p) => <p key={p}>{p}</p>)}
            {s.bullets && <List items={s.bullets} />}
          </div>
        </section>
      ))}

      <Block icon={Cpu} title="Dans l'application" tone="app"><List items={fiche.inApp} /></Block>
      <Block icon={AlertTriangle} title="Pièges à éviter" tone="warn"><List items={fiche.traps} /></Block>
      <Block icon={Lightbulb} title="À retenir" tone="key"><List items={fiche.keyPoints} /></Block>

      {fiche.related?.length > 0 && (
        <section className="mt-6">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">Pour aller plus loin</h2>
          <ul className="mt-2 flex flex-wrap gap-2">
            {fiche.related.map((slug) => FICHES_BY_SLUG[slug] && (
              <li key={slug}>
                <Link href={ficheUrl(slug)} className="inline-flex rounded-full border border-line px-3 py-1.5 text-sm hover:border-bull/60">
                  {FICHES_BY_SLUG[slug].emoji} {FICHES_BY_SLUG[slug].title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <nav className="mt-8 grid grid-cols-2 gap-3 border-t border-line pt-4" aria-label="Fiche précédente et suivante">
        {prev ? (
          <Link href={ficheUrl(prev.slug)} className="rounded-lg border border-line p-3 text-sm hover:border-bull/60">
            <span className="flex items-center gap-1 text-xs text-muted"><ArrowLeft className="h-3.5 w-3.5" /> Précédente</span>
            {prev.title}
          </Link>
        ) : <span />}
        {next && (
          <Link href={ficheUrl(next.slug)} className="rounded-lg border border-line p-3 text-right text-sm hover:border-bull/60">
            <span className="flex items-center justify-end gap-1 text-xs text-muted">Suivante <ArrowRight className="h-3.5 w-3.5" /></span>
            {next.title}
          </Link>
        )}
      </nav>
    </main>
  )
}

export default function LearnSite({ path }) {
  const slug = path.replace(/\/+$/, '').slice(LEARN_ROOT.length + 1)
  const fiche = slug ? FICHES_BY_SLUG[slug] : null
  return (
    <div className="min-h-full">
      <Header />
      {slug && !fiche ? (
        <main className="mx-auto max-w-3xl px-4 py-10 text-center">
          <p className="font-semibold">Cette fiche n'existe pas (ou plus).</p>
          <Link href={LEARN_ROOT} className="btn-primary mt-4 inline-flex">Voir toutes les fiches</Link>
        </main>
      ) : fiche ? <Fiche fiche={fiche} /> : <Index />}
      <Footer />
    </div>
  )
}
