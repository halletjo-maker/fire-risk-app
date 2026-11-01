// Avant la construction : titres et descriptions de chaque page publique, pour Google et les aperçus
// de liens. Le serveur les insère dans la page (balises <title>, description, Open Graph) et en tire
// le plan du site (sitemap.xml). Source unique : les fiches de src/learn/fiches.js.
import { writeFileSync } from 'node:fs'
import { CATEGORIES, FICHES } from '../src/learn/fiches.js'

const pages = {
  '/': {
    title: 'MM100 · Comprendre une action avant d’investir',
    description: 'L’entreprise, son cours et l’actualité notés sur 10, avec des fiches gratuites pour apprendre à lire les indicateurs. Sans publicité.',
    priority: 1.0,
  },
  '/apprendre': {
    title: 'Apprendre à investir : fiches simples et gratuites · MM100',
    description: `${FICHES.length} fiches sans jargon : moyenne mobile 100 jours, RSI, PER, ETF, turbos, et la fiscalité belge (taxe sur les plus-values 2026, TOB, précompte).`,
    priority: 0.9,
  },
  '/portefeuille-temoin': {
    title: 'Portefeuille témoin : la méthode MM100 face au MSCI World',
    description: 'Un portefeuille virtuel géré seul par des règles publiques, comparé jour après jour à un ETF MSCI World. Gains et pertes montrés tels quels.',
    priority: 0.8,
  },
  '/a-propos': {
    title: 'À propos · MM100',
    description: 'Un projet personnel, gratuit et sans publicité pour comprendre une action avant d’investir.',
    priority: 0.4,
  },
  '/confidentialite': {
    title: 'Confidentialité · MM100',
    description: 'Les données gardées par MM100, où elles sont, et comment les faire effacer.',
    priority: 0.2,
  },
}
for (const f of FICHES) {
  const cat = CATEGORIES.find((c) => c.key === f.category)?.label
  pages[`/apprendre/${f.slug}`] = {
    title: `${f.title} · MM100`,
    description: f.oneLiner,
    section: cat,
    priority: f.category === 'fiscalite' ? 0.8 : 0.7,
  }
}
writeFileSync(new URL('../public/seo.json', import.meta.url), JSON.stringify(pages, null, 1) + '\n')
console.log(`seo.json : ${Object.keys(pages).length} pages`)
