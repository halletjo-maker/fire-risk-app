import { useEffect } from 'react'
import SiteLayout, { Link } from './SiteLayout'

function Page({ title, intro, children }) {
  useEffect(() => { document.title = `${title} — Analyse Boursière` }, [title])
  return (
    <SiteLayout>
      <main className="mx-auto max-w-3xl px-4 py-8">
        <h1 className="text-2xl font-bold">{title}</h1>
        {intro && <p className="mt-3 text-[15px] leading-relaxed text-gray-300">{intro}</p>}
        <div className="mt-2">{children}</div>
      </main>
    </SiteLayout>
  )
}

function Section({ title, children }) {
  return (
    <section className="mt-7">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="mt-2 space-y-2 text-[15px] leading-relaxed text-gray-300">{children}</div>
    </section>
  )
}

const List = ({ items }) => (
  <ul className="list-disc space-y-1.5 pl-5">{items.map((t) => <li key={t}>{t}</li>)}</ul>
)

export function About() {
  return (
    <Page
      title="À propos"
      intro="Analyse Boursière est un projet personnel, construit par un investisseur particulier pour lui-même, ses amis et ses collègues. Il n'a ni but commercial, ni publicité, ni partenaire financier."
    >
      <Section title="Pourquoi cet outil ?">
        <p>
          Avant d'acheter une action, on se pose toujours les mêmes questions : l'entreprise est-elle solide ? Le cours
          est-il bien orienté ? Que dit l'actualité ? Cet outil rassemble ces réponses au même endroit, explique son
          raisonnement, et aide à garder une discipline : une porte de sortie (stop-loss), un objectif, de la
          diversification.
        </p>
        <p>
          Il est aussi fait pour apprendre : chaque indicateur est expliqué dans une <Link href="/apprendre" className="text-bull underline underline-offset-2">fiche</Link>, avec la règle exacte que l'outil applique.
        </p>
      </Section>
      <Section title="La méthode, en bref">
        <List items={[
          'Trois analyses notées sur 10 : fondamentale (35 %), technique (45 %) et sentiment des actualités (20 %).',
          'Critère principal : la position du cours par rapport à sa moyenne mobile 100 jours.',
          'Signal : 🟢 à partir de 7,5/10, 🟡 de 5 à 7,4, 🔴 sous 5.',
          'Les portefeuilles fictifs testent ces règles avec de l’argent virtuel et se comparent à un ETF MSCI World.',
        ]} />
      </Section>
      <Section title="D'où viennent les données ?">
        <p>
          De sources publiques et gratuites : Yahoo Finance, Boursorama, Google Finance, justETF, CoinGecko, Google
          Actualités et l'outil de filtrage de Nasdaq. Quand une source ne répond pas, une autre prend le relais.
          Les cours peuvent avoir quelques minutes de retard et certaines données peuvent manquer.
        </p>
      </Section>
      <Section title="Les limites, en toute transparence">
        <List items={[
          'Ce n’est pas un conseil en investissement ni une recommandation personnalisée : la décision et le risque restent les tiens.',
          'Aucune méthode ne prédit l’avenir ; les performances passées, réelles ou simulées, ne préjugent pas des performances futures.',
          'L’outil ne connaît ni ta situation, ni tes objectifs, ni ta tolérance au risque.',
        ]} />
      </Section>
      <Section title="Contact">
        <p>Pour une question, une invitation ou une suggestion, adresse-toi à la personne qui t'a présenté l'outil.</p>
      </Section>
    </Page>
  )
}

export function Privacy() {
  return (
    <Page
      title="Confidentialité"
      intro="Ce que l'application garde sur toi, pourquoi, où, et comment le faire effacer. En résumé : le strict nécessaire pour faire fonctionner ton compte, rien n'est vendu ni partagé."
    >
      <Section title="Les données gardées">
        <List items={[
          'Ton adresse mail : pour te connecter et t’envoyer les alertes et le rapport mensuel que tu as demandés.',
          'Ton mot de passe, uniquement sous forme chiffrée (haché) : personne ne peut le lire, pas même l’administrateur.',
          'Tes watchlists, alertes, portefeuilles fictifs et l’historique de tes analyses.',
          'Tes sessions de connexion (30 jours), pour ne pas avoir à te reconnecter à chaque visite.',
        ]} />
        <p>Les fiches « Apprendre » se consultent sans compte et sans aucune donnée personnelle.</p>
      </Section>
      <Section title="Où sont-elles ?">
        <p>
          Sur un serveur loué chez Hetzner, en Allemagne (Union européenne), protégé par un pare-feu et une connexion
          chiffrée (https). Les mails sont envoyés par l'intermédiaire de Gmail (Google).
        </p>
      </Section>
      <Section title="Cookies et traceurs">
        <p>
          Un seul cookie, strictement nécessaire : celui qui garde ta session ouverte. Aucune publicité, aucun outil de
          mesure d'audience, aucun traceur tiers. Le navigateur mémorise aussi quelques préférences sur ton appareil
          (dernière watchlist ouverte, bandeau d'installation masqué).
        </p>
      </Section>
      <Section title="Partage">
        <p>
          Tes données ne sont ni vendues, ni louées, ni partagées. Les autres membres ne voient pas tes watchlists, tes
          alertes ni tes portefeuilles. Pour analyser un produit, le serveur interroge des sources de cours publiques sans
          leur transmettre ton identité.
        </p>
      </Section>
      <Section title="Tes droits">
        <p>
          Tu peux demander à consulter, corriger ou effacer tes données. L'administrateur de cette installation — la
          personne qui t'a invité — peut supprimer ton compte : tes watchlists, alertes et portefeuilles sont alors
          effacés définitivement. Tu peux aussi désactiver le rapport mensuel à tout moment dans ton profil.
        </p>
      </Section>
    </Page>
  )
}
