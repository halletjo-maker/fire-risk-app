import { useEffect, useState } from 'react'
import {
  ArrowRight, Bell, BookOpen, Check, FileText, Globe2, Layers, LineChart, LogIn, Mail, Newspaper, ShieldCheck, Smartphone,
  Wallet,
} from 'lucide-react'
import SiteLayout, { Link } from './SiteLayout'
import { FICHES, FICHES_BY_SLUG } from '../learn/fiches'
import { api } from '../lib/api'
import { changeColor, fmtPct } from '../lib/format'

// Aperçu illustratif d'une analyse (exemple, pas un vrai produit)
function Preview() {
  const parts = [['Fondamental', 7.2, 35], ['Technique', 8.4, 45], ['Sentiment', 6.5, 20]]
  return (
    <div className="card w-full max-w-sm p-4 shadow-2xl" aria-label="Exemple d'analyse (illustration)">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">Exemple d'analyse</p>
      <div className="mt-2 flex items-center justify-between gap-3">
        <div>
          <p className="font-semibold">Société Exemple</p>
          <p className="text-xs text-muted">Action · EXMPL · <span className="whitespace-nowrap">52,40 € <span className="text-bull">+1,2&nbsp;%</span></span></p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-bull">7,6<span className="text-sm font-normal text-muted">/10</span></p>
          <p className="text-xs font-semibold text-bull">🟢 Conditions favorables</p>
        </div>
      </div>
      <ul className="mt-3 space-y-2">
        {parts.map(([label, score, weight]) => (
          <li key={label} className="text-xs">
            <div className="flex justify-between text-muted"><span>{label} <span className="opacity-70">· {weight} %</span></span><span className="font-semibold text-gray-100">{String(score).replace('.', ',')}</span></div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-bg">
              <div className={`h-full rounded-full ${score >= 7.5 ? 'bg-bull' : 'bg-warn'}`} style={{ width: `${score * 10}%` }} />
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 rounded-lg bg-bg px-3 py-2 text-xs">
        <span className="text-bull">Achat ≤ 50,10 €</span><span className="text-muted"> · </span><span className="text-warn">Vente 57,80 €</span>
        <span className="block text-muted">★ au-dessus de sa MM100 (+6,4 %) · stop conseillé 47,90 €</span>
      </p>
    </div>
  )
}

// Formulaire « Demander une invitation » (le champ « site » est un piège à robots, invisible)
function AccessRequest() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [trap, setTrap] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(null)
  const [error, setError] = useState(null)
  const submit = async (e) => {
    e.preventDefault()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email.trim())) return setError('Adresse mail invalide.')
    setBusy(true)
    setError(null)
    try {
      setDone((await api.requestAccess({ email: email.trim(), message: message.trim() || null, website: trap || null })).message)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  if (done) return <p className="mt-4 flex gap-2 rounded-lg border border-bull/40 bg-bull/10 px-3 py-2 text-sm text-bull" role="status"><Check className="mt-0.5 h-4 w-4 shrink-0" /> {done}</p>
  return (
    <form onSubmit={submit} noValidate className="mt-4 space-y-2">
      <label htmlFor="req-email" className="block text-sm font-medium">Demander une invitation</label>
      <input id="req-email" type="email" inputMode="email" autoComplete="email" autoCapitalize="none" className="input"
        placeholder="ton adresse mail" value={email} onChange={(e) => setEmail(e.target.value)} />
      <textarea className="input min-h-[64px] resize-y" maxLength={500} placeholder="Un mot pour te présenter (facultatif)"
        value={message} onChange={(e) => setMessage(e.target.value)} aria-label="Message (facultatif)" />
      <input type="text" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" value={trap}
        onChange={(e) => setTrap(e.target.value)} className="absolute -left-[9999px] h-px w-px opacity-0" />
      {error && <p className="text-sm text-bear" role="alert">{error}</p>}
      <button type="submit" className="btn-primary w-full" disabled={busy}><Mail className="h-4 w-4" /> {busy ? 'Envoi…' : 'Envoyer ma demande'}</button>
      <p className="text-xs text-muted">Ton adresse ne sert qu’à te répondre. Chaque demande est lue ; si elle est acceptée, tu reçois un lien par mail.</p>
    </form>
  )
}

// Carte en direct du portefeuille témoin (masquée s'il n'y en a pas)
function ShowcaseTeaser() {
  const [d, setD] = useState(null)
  useEffect(() => { api.publicPortfolio().then(setD).catch(() => setD(null)) }, [])
  if (!d) return null
  const last = d.history?.filter((h) => h.benchmark_eur != null).at(-1)
  const bench = last ? (last.benchmark_eur / d.initial_cash - 1) * 100 : null
  const since = new Date(`${d.started}T12:00:00`).toLocaleDateString('fr-BE', { day: 'numeric', month: 'long' })
  return (
    <Link href="/portefeuille-temoin" className="card mt-3 block w-full max-w-sm p-4 transition hover:border-bull/60">
      <p className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-muted">
        <span>Portefeuille témoin · en direct</span><ArrowRight className="h-4 w-4" />
      </p>
      <div className="mt-2 grid grid-cols-2 gap-3">
        <div>
          <p className={`text-xl font-bold ${changeColor(d.pnl_pct)}`}>{fmtPct(d.pnl_pct)}</p>
          <p className="text-xs text-muted">géré seul par l’outil</p>
        </div>
        <div>
          <p className={`text-xl font-bold ${bench == null ? '' : changeColor(bench)}`}>{bench == null ? '—' : fmtPct(bench)}</p>
          <p className="text-xs text-muted">ETF MSCI World</p>
        </div>
      </div>
      <p className="mt-2 text-xs text-muted">Depuis le {since} · {d.positions.length} lignes · argent virtuel</p>
    </Link>
  )
}

const FEATURES = [
  [LineChart, 'Une analyse en quelques secondes', 'Tape un nom, un ticker ou un code ISIN : action, ETF, crypto, indice ou turbo. Score sur 10, signal et rapport détaillé avec stop-loss et alternatives.'],
  [Layers, 'Des watchlists qui vivent', 'Tes listes se mettent à jour toutes les 15 minutes, avec pour chaque produit un cours d’achat et un objectif de vente.'],
  [Globe2, 'Des listes prêtes à l’emploi', 'Les introductions en Bourse des 5 et 10 dernières années, et 500 grandes sociétés du monde entier plus 20 cryptos, suivies selon les Bourses ouvertes.'],
  [Wallet, 'Des portefeuilles fictifs', '5 000 € virtuels gérés seuls par les règles de l’outil, comparés jour après jour à un ETF MSCI World. Pour juger la méthode sans risquer un euro.'],
  [Bell, 'Des alertes et un rapport mensuel', 'Un mail quand un signal fort apparaît ou qu’un cours croise sa moyenne 100 jours, et le bilan de tes portefeuilles le 1er de chaque mois.'],
  [BookOpen, 'Des fiches pour comprendre', 'Chaque indicateur a sa fiche : ce qu’il mesure, comment le lire, ses pièges. Un « ? » dans l’outil t’y emmène.'],
]

const STEPS = [
  ['Fondamental', '35 %', 'L’entreprise est-elle solide ? Valorisation, croissance, rentabilité, dette, trésorerie, dividende, avis des analystes.'],
  ['Technique', '45 %', 'Le cours est-il bien orienté ? La moyenne mobile 100 jours en critère principal, puis tendances, RSI, MACD, Bollinger, volumes.'],
  ['Sentiment', '20 %', 'Que dit l’actualité ? Le ton des titres de presse des 72 dernières heures, en français et en anglais.'],
]

export default function Landing({ onLogin }) {
  useEffect(() => { document.title = 'Analyse Boursière — comprendre avant d’investir' }, [])
  const teaser = ['lire-les-scores', 'moyenne-mobile-100', 'diversifier-gerer-risque'].map((s) => FICHES_BY_SLUG[s])

  return (
    <SiteLayout onLogin={onLogin}>
      <main>
      {/* Accroche */}
      <section className="mx-auto grid max-w-5xl items-center gap-8 px-4 py-10 md:grid-cols-2 md:py-16">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-bull">
            <span className="block">MM100 · l’analyse expliquée</span>
            <span className="mt-1 block text-muted">Investir en comprenant</span>
          </p>
          <h1 className="mt-2 text-3xl font-bold leading-tight sm:text-4xl">Comprendre une action avant d’investir.</h1>
          <p className="mt-4 text-[15px] leading-relaxed text-gray-300">
            Un outil d’aide à la décision qui croise trois regards — l’entreprise, son cours et l’actualité — et
            t’explique son raisonnement, avec des fiches pour apprendre à lire les indicateurs par toi-même.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <button className="btn-primary" onClick={onLogin}><LogIn className="h-4 w-4" /> Se connecter</button>
            <Link href="/apprendre" className="btn-ghost border border-line"><BookOpen className="h-4 w-4" /> Découvrir les fiches</Link>
          </div>
        </div>
        <div className="flex flex-col items-center md:items-end"><Preview /><ShowcaseTeaser /></div>
      </section>

      {/* Fonctions */}
      <section className="border-t border-line bg-panel/40">
        <div className="mx-auto max-w-5xl px-4 py-10">
          <h2 className="text-xl font-bold">Ce que tu y trouves</h2>
          <ul className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(([Icon, title, text]) => (
              <li key={title} className="card p-4">
                <Icon className="h-5 w-5 text-bull" />
                <p className="mt-2 font-semibold">{title}</p>
                <p className="mt-1 text-sm leading-relaxed text-muted">{text}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Méthode */}
      <section className="mx-auto max-w-5xl px-4 py-10">
        <h2 className="text-xl font-bold">Comment l’outil raisonne</h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">
          Trois analyses notées sur 10, combinées en un score global. 7,5 et plus : conditions favorables 🟢 ; de 5 à 7,4 :
          prudence 🟡 ; moins de 5 : défavorables 🔴. Les règles sont publiques et détaillées dans les fiches.
        </p>
        <ol className="mt-5 grid gap-4 md:grid-cols-3">
          {STEPS.map(([title, weight, text], i) => (
            <li key={title} className="card p-4">
              <p className="flex items-baseline justify-between">
                <span className="font-semibold">{i + 1}. {title}</span>
                <span className="text-sm font-semibold text-bull">{weight}</span>
              </p>
              <p className="mt-2 text-sm leading-relaxed text-muted">{text}</p>
            </li>
          ))}
        </ol>
        <p className="mt-4 flex gap-2 text-sm text-muted">
          <ShieldCheck className="h-5 w-5 shrink-0 text-bull" />
          Filtre de prudence : quand le marché mondial passe sous sa moyenne 100 jours, les portefeuilles fictifs cessent d’acheter.
        </p>
        <Link href="/portefeuille-temoin" className="mt-4 inline-flex items-center gap-1 text-sm text-bull hover:underline">
          Voir le portefeuille témoin, géré seul par ces règles <ArrowRight className="h-4 w-4" />
        </Link>
      </section>

      {/* Fiches */}
      <section className="border-t border-line bg-panel/40">
        <div className="mx-auto max-w-5xl px-4 py-10">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="text-xl font-bold">Apprendre, sans jargon</h2>
            <Link href="/apprendre" className="inline-flex items-center gap-1 text-sm text-bull hover:underline">
              Les {FICHES.length} fiches <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <ul className="mt-5 grid gap-4 md:grid-cols-3">
            {teaser.map((f) => (
              <li key={f.slug}>
                <Link href={`/apprendre/${f.slug}`} className="card block h-full p-4 transition hover:border-bull/60">
                  <p className="font-semibold"><span aria-hidden="true">{f.emoji}</span> {f.title}</p>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted">{f.oneLiner}</p>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Limites + accès */}
      <section className="mx-auto grid max-w-5xl gap-4 px-4 py-10 md:grid-cols-2">
        <div className="card p-5">
          <h2 className="flex items-center gap-2 text-lg font-bold"><FileText className="h-5 w-5 text-warn" /> Ce que l’outil n’est pas</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-gray-300">
            <li>Ce n’est pas un conseil en investissement : il aide à réfléchir, la décision t’appartient.</li>
            <li>Il ne passe aucun ordre et ne touche jamais à ton argent.</li>
            <li>Il s’appuie sur des sources publiques gratuites : une donnée peut manquer ou être en retard.</li>
            <li>Un bon score n’est pas une garantie : une action bien notée peut baisser.</li>
          </ul>
        </div>
        <div className="card p-5">
          <h2 className="flex items-center gap-2 text-lg font-bold"><Mail className="h-5 w-5 text-bull" /> Comment y accéder</h2>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-gray-300">
            <li>L’outil est réservé aux personnes invitées : laisse ton adresse ci-dessous pour en demander une.</li>
            <li>Les fiches « Apprendre » sont ouvertes à tous, sans compte.</li>
            <li className="flex gap-2"><Smartphone className="h-5 w-5 shrink-0 text-muted" /> Installable sur iPhone et Android, comme une vraie application.</li>
            <li className="flex gap-2"><Newspaper className="h-5 w-5 shrink-0 text-muted" /> Gratuit, sans publicité, sans revente de données.</li>
          </ul>
          <AccessRequest />
          <button className="btn-ghost mt-3 w-full justify-center border border-line" onClick={onLogin}><LogIn className="h-4 w-4" /> J’ai déjà un compte</button>
        </div>
      </section>
      </main>
    </SiteLayout>
  )
}
