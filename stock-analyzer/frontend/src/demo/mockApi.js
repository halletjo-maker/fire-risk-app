// Mode démo : l'API est simulée dans la page à partir de réponses réelles enregistrées
// (window.__DEMO_DATA__). Compte, watchlists et alertes restent dans ce navigateur.
const DATA = () => window.__DEMO_DATA__ || { products: {}, aliases: {} }
const KEY = 'ab_demo_store_v1'
const COLORS = ['#00FF88', '#3B82F6', '#A855F7', '#F59E0B', '#EF4444', '#06B6D4', '#EC4899', '#94A3B8']
const ALERT_TYPES = {
  SIGNAL_FORT: { icon: '🚨', label: 'Signal fort', help: 'Le score global passe à 7,5/10 ou plus (conditions favorables).' },
  ALERTE_BAISSE: { icon: '📉', label: 'Alerte baisse', help: 'Le score global passe sous 5/10 (conditions défavorables).' },
  MM100_CROISEMENT: { icon: '📊', label: 'Croisement MM100', help: 'Le prix croise sa moyenne mobile 100 jours, à la hausse ou à la baisse.' },
  ACTUALITE_IMPORTANTE: { icon: '📰', label: 'Actualité importante', help: "Sentiment très négatif détecté dans l'actualité (score < 3/10)." },
  RESULTATS_A_VENIR: { icon: '💰', label: 'Résultats à venir', help: 'Résultats trimestriels dans moins de 48 heures.' },
}
const FREQ = { immediate: 'Immédiate', daily: '1 × par jour', weekly: '1 × par semaine' }

let memory = null
function load() {
  if (memory) return memory
  try { memory = JSON.parse(localStorage.getItem(KEY)) } catch { memory = null }
  memory = memory || { seq: 1, users: [], active: null, watchlists: [], items: [], alerts: [], events: [], analyses: {} }
  return memory
}
function save() { try { localStorage.setItem(KEY, JSON.stringify(memory)) } catch { /* stockage bloqué : la démo marche en mémoire */ } }
const nextId = () => { const db = load(); db.seq += 1; return db.seq }
const sqlNow = () => new Date().toISOString().slice(0, 19).replace('T', ' ')

class ApiError extends Error {}
const fail = (detail) => { throw new ApiError(detail) }
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

const norm = (s) => (s || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().trim()

function product(pid) { return DATA().products[pid] }
function catalog() {
  return Object.entries(DATA().products).map(([id, p]) => {
    const a = p.analyze
    return { id, symbol: a.product.symbol, isin: a.product.isin, name: a.product.name, type: a.product.type,
             type_label: a.product.type_label, exchange: a.product.exchange, change_pct: a.quote.change_pct, source: a.source }
  })
}
function findProducts(q) {
  const n = norm(q)
  const alias = DATA().aliases[q.toUpperCase()]
  if (alias && product(alias)) return catalog().filter((c) => c.id === alias)
  const words = n.split(/\s+/).filter((w) => !['turbo', 'turbos', 'warrant', 'call', 'put'].includes(w))
  const wantsDerivative = /\b(turbo|warrant|call|put)\b/.test(n)
  let list = catalog().filter((c) => {
    const hay = norm(`${c.name} ${c.symbol || ''} ${c.isin || ''} ${c.id}`)
    return words.every((w) => hay.includes(w))
  })
  if (wantsDerivative) {
    const under = catalog().filter((c) => ['TURBO', 'WARRANT'].includes(c.type) &&
      words.every((w) => norm(product(c.id).derivative?.underlying || product(c.id).analyze.derivative?.underlying).includes(w) || norm(c.name).includes(w)))
    list = [...under, ...list.filter((c) => !under.includes(c))]
  }
  return list
}
function kind(q) {
  if (/^[A-Z]{2}[A-Z0-9]{9}\d$/i.test(q.trim())) return 'isin'
  if (!q.includes(' ') && (q === q.toUpperCase() || q.length <= 5)) return 'ticker'
  return 'nom'
}
const suggestions = () => catalog().slice(0, 8).map((c) => c.symbol || c.name).join(', ')

function currentUser() {
  const db = load()
  const u = db.users.find((x) => x.id === db.active)
  if (!u) { const e = new ApiError('Session expirée : reconnecte-toi.'); e.status = 401; throw e }
  return u
}
function ownWatchlist(u, id) {
  const w = load().watchlists.find((x) => x.id === Number(id) && x.user_id === u.id)
  if (!w) fail('Watchlist introuvable')
  return w
}
const itemCount = (wid) => load().items.filter((i) => i.watchlist_id === wid).length
const summary = (w) => ({ id: w.id, name: w.name, color: w.color, position: w.position, created_at: w.created_at, item_count: itemCount(w.id) })
const alertCount = (itemId) => load().alerts.filter((a) => a.item_id === itemId && a.enabled).length
const itemOut = (i) => ({ ...i, alert_count: alertCount(i.id) })

function scored(pid) {
  const d = product(pid)?.decision?.decision
  const q = product(pid)?.analyze?.quote
  return { last_price: q?.price ?? null, last_change_pct: q?.change_pct ?? null,
           last_score: d?.available ? d.score : null, last_signal: d?.available ? d.signal : null, last_refresh_at: sqlNow() }
}

// ---------------------------------------------------------------- alertes (même logique que le serveur)
function evaluate(type, state, pid) {
  const p = product(pid)
  if (!p) return [false, state, {}]
  const d = p.decision?.decision, t = p.technical?.technical, s = p.sentiment?.sentiment
  const score = d?.available ? d.score : null
  if (type === 'SIGNAL_FORT' || type === 'ALERTE_BAISSE') {
    if (score == null) return [false, state, {}]
    const on = type === 'SIGNAL_FORT' ? score >= 7.5 : score < 5
    return [on && state !== 'ON', on ? 'ON' : 'OFF', { score }]
  }
  if (type === 'MM100_CROISEMENT') {
    const mm = t?.applicable ? t.mm100 : null
    if (!mm) return [false, state, {}]
    const st = mm.above ? 'ABOVE' : 'BELOW'
    const crossed = state == null ? !!mm.cross : st !== state
    return [crossed, st, { direction: mm.above ? 'HAUSSIER' : 'BAISSIER', mm }]
  }
  if (type === 'ACTUALITE_IMPORTANTE') {
    const raw = s?.inverse ? s.underlying_score : s?.score
    const on = raw != null && raw < 3 && s.items?.length > 0
    return [on && state !== 'ON', on ? 'ON' : 'OFF', { sentiment: raw }]
  }
  if (type === 'RESULTATS_A_VENIR') {
    const e = (s?.events || []).find((x) => x.type === 'Earnings Date' && x.days >= 0 && x.days <= 2)
    return e ? [state !== e.date, e.date, { date: e.date }] : [false, state, {}]
  }
  return [false, state, {}]
}
function subject(type, ctx, pid) {
  const a = product(pid).analyze.product
  const name = `${a.name} (${a.symbol || a.isin || ''})`.replace(' ()', '')
  const sc = (product(pid).decision?.decision?.score ?? 0).toFixed(1).replace('.', ',')
  if (type === 'SIGNAL_FORT') return `[SIGNAL ACHAT ✅] ${name} — Score ${sc}/10`
  if (type === 'ALERTE_BAISSE') return `[ALERTE BAISSE 📉] ${name} — Score ${sc}/10`
  if (type === 'MM100_CROISEMENT') return `[MM100 ⚡ CROISEMENT ${ctx.direction}] ${name} — Score ${sc}/10`
  if (type === 'ACTUALITE_IMPORTANTE') return `[ACTUALITÉ 📰 NÉGATIVE] ${name} — Sentiment ${ctx.sentiment.toFixed(1).replace('.', ',')}/10`
  return `[RÉSULTATS 💰 DANS 48 H] ${name} — ${new Date(ctx.date).toLocaleDateString('fr-BE')}`
}
function checkAlerts() {
  const db = load()
  for (const a of db.alerts.filter((x) => x.enabled)) {
    const item = db.items.find((i) => i.id === a.item_id)
    const w = item && db.watchlists.find((x) => x.id === item.watchlist_id)
    if (!item || !w) continue
    const [fire, state, ctx] = evaluate(a.alert_type, a.last_state, item.product_id)
    if (fire) {
      db.events.unshift({ id: nextId(), user_id: w.user_id, alert_type: a.alert_type, product_id: item.product_id, product: item.name,
                          subject: subject(a.alert_type, ctx, item.product_id), delivered: 0,
                          status: 'Démo : aucun mail envoyé', sent_at: sqlNow() })
      a.last_triggered_at = sqlNow()
    }
    a.last_state = state
  }
  save()
}

// ---------------------------------------------------------------- routes
export async function mockRequest(path, { method = 'GET', body, headers = {} } = {}) {
  await wait(120 + Math.random() * 250)
  const url = new URL(path, 'http://demo')
  const p = url.pathname
  const q = Object.fromEntries(url.searchParams)
  const db = load()
  let m

  if (p === '/health') {
    const h = DATA().health || {}
    return { ...h, status: 'ok', version: 'démo', scheduler: { running: false, jobs: [] },
             config: { smtp_configured: false, newsapi_configured: false, alpha_vantage_configured: false } }
  }

  // ---- utilisateur
  // Démo : n'importe quel mot de passe est accepté (aucune donnée réelle)
  if ((p === '/users/login' || p === '/users/register') && method === 'POST') {
    const email = (body.email || '').trim().toLowerCase()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) fail('Adresse mail invalide')
    let u = db.users.find((x) => x.email === email)
    if (!u) { u = { id: nextId(), email, is_admin: true, created_at: sqlNow(), last_login_at: sqlNow() }; db.users.push(u) }
    u.last_login_at = sqlNow()
    db.active = u.id; save()
    return { user: u }
  }
  if (p === '/users/current') return { user: db.users.find((u) => u.id === db.active) || null, setup_required: false, registration_open: true }
  if (p === '/users/password') return { ok: true }
  if ((m = p.match(/^\/watchlists\/(\d+)\/suggestions$/))) {
    return { status: 'ready', items: [], message: 'Démo hors ligne : les suggestions sont calculées sur la vraie application.' }
  }
  if (p === '/admin/version') return { version: null, auto_update: false, update_pending: false }
  if (p === '/users/members') {
    const u = currentUser()
    return { members: [{ ...u, is_admin: true, active: true, is_me: true }], invitations: db.invitations || [] }
  }
  if (p === '/users/invitations' && method === 'POST') {
    const inv = { id: nextId(), email: (body.email || '').toLowerCase(), created_at: sqlNow(), expires_at: sqlNow() }
    db.invitations = [inv, ...(db.invitations || []).filter((i) => i.email !== inv.email)]; save()
    return { invitation: inv, link: `${location.origin}/?invitation=demo`, mail: { sent: false, status: 'Démo : aucun mail envoyé' } }
  }
  if ((m = p.match(/^\/users\/invitations\/(\d+)$/)) && method === 'DELETE') {
    db.invitations = (db.invitations || []).filter((i) => i.id !== Number(m[1])); save()
    return { ok: true }
  }
  if (p === '/users/logout') { db.active = null; save(); return { user: null } }
  if (p === '/users/me') {
    const u = currentUser(headers)
    const wls = db.watchlists.filter((w) => w.user_id === u.id)
    const items = db.items.filter((i) => wls.some((w) => w.id === i.watchlist_id))
    return { user: u, stats: { watchlists: wls.length, products: items.length,
      active_alerts: db.alerts.filter((a) => a.enabled && items.some((i) => i.id === a.item_id)).length,
      analyses: db.analyses[u.id] || 0 } }
  }

  // ---- recherche et analyses
  if (p === '/search') {
    const candidates = findProducts(q.q || '').slice(0, 8)
    return { query: q.q, query_kind: kind(q.q || ''), candidates, sources: [{ name: 'Démo (données enregistrées)', ok: candidates.length > 0 }] }
  }
  if (p === '/analyze') {
    const pid = (q.id && product(q.id)) ? q.id : findProducts(q.q || '')[0]?.id
    if (!pid) {
      return { query: q.q, query_kind: kind(q.q || ''), status: 'not_found', sources: [],
               message: `Démo : ce produit n'est pas enregistré. Essaie par exemple : ${suggestions()}.` }
    }
    const u = db.users.find((x) => x.id === db.active)
    if (u) { db.analyses[u.id] = (db.analyses[u.id] || 0) + 1; save() }
    const rec = product(pid).analyze
    const alternatives = findProducts(q.q || '').filter((c) => c.id !== pid).slice(0, 5)
    return { ...rec, query: q.q, alternatives }
  }
  for (const ep of ['quote', 'fundamentals', 'technical', 'sentiment', 'decision', 'report']) {
    if (p === `/${ep}`) {
      const rec = product(q.id)
      if (!rec) fail("Démo : ce produit n'est pas enregistré.")
      if (ep === 'quote') return { product: rec.analyze.product, quote: rec.analyze.quote, derivative: rec.analyze.derivative, source: rec.analyze.source, sources: rec.analyze.sources }
      if (!rec[ep]) fail('Analyse indisponible pour ce produit.')
      return rec[ep]
    }
  }

  // ---- watchlists
  if (p === '/watchlists' && method === 'GET') {
    const u = currentUser(headers)
    return { watchlists: db.watchlists.filter((w) => w.user_id === u.id).sort((a, b) => a.position - b.position).map(summary) }
  }
  if (p === '/watchlists' && method === 'POST') {
    const u = currentUser(headers)
    const name = (body.name || '').trim()
    if (!name) fail('Le nom est obligatoire')
    if (db.watchlists.some((w) => w.user_id === u.id && w.name === name)) fail('Une watchlist porte déjà ce nom')
    const w = { id: nextId(), user_id: u.id, name, color: body.color || COLORS[0], position: db.watchlists.length, created_at: sqlNow() }
    db.watchlists.push(w); save()
    return { watchlist: summary(w) }
  }
  if ((m = p.match(/^\/watchlists\/(\d+)$/))) {
    const u = currentUser(headers)
    const w = ownWatchlist(u, m[1])
    if (method === 'PATCH') {
      if (body.name && db.watchlists.some((x) => x.user_id === u.id && x.id !== w.id && x.name === body.name.trim())) fail('Une watchlist porte déjà ce nom')
      if (body.name) w.name = body.name.trim()
      if (body.color) w.color = body.color
      save(); return { watchlist: summary(w) }
    }
    if (method === 'DELETE') {
      const ids = db.items.filter((i) => i.watchlist_id === w.id).map((i) => i.id)
      db.alerts = db.alerts.filter((a) => !ids.includes(a.item_id))
      db.items = db.items.filter((i) => i.watchlist_id !== w.id)
      db.watchlists = db.watchlists.filter((x) => x.id !== w.id); save()
      return { deleted: { id: w.id, name: w.name, items: ids.length } }
    }
  }
  if ((m = p.match(/^\/watchlists\/(\d+)\/duplicate$/))) {
    const u = currentUser(headers)
    const w = ownWatchlist(u, m[1])
    let name = `${w.name} (copie)`, n = 2
    while (db.watchlists.some((x) => x.user_id === u.id && x.name === name)) name = `${w.name} (copie) (${n++})`
    const copy = { ...w, id: nextId(), name, position: db.watchlists.length, created_at: sqlNow() }
    db.watchlists.push(copy)
    db.items.filter((i) => i.watchlist_id === w.id).forEach((i) => db.items.push({ ...i, id: nextId(), watchlist_id: copy.id }))
    save(); return { watchlist: summary(copy) }
  }
  if ((m = p.match(/^\/watchlists\/(\d+)\/items$/))) {
    const u = currentUser(headers)
    const w = ownWatchlist(u, m[1])
    if (method === 'GET') {
      return { watchlist: w, items: db.items.filter((i) => i.watchlist_id === w.id).sort((a, b) => a.position - b.position).map(itemOut) }
    }
    const rec = product(body.product_id)
    if (!rec) fail("Démo : ce produit n'est pas enregistré.")
    if (db.items.some((i) => i.watchlist_id === w.id && i.product_id === body.product_id)) fail('Ce produit est déjà dans cette watchlist')
    const a = rec.analyze.product
    const item = { id: nextId(), watchlist_id: w.id, symbol: a.symbol || a.isin || body.product_id, product_id: body.product_id,
                   name: a.name, isin: a.isin, exchange: a.exchange, product_type: a.type,
                   position: itemCount(w.id), added_at: sqlNow(), last_price: rec.analyze.quote.price,
                   last_change_pct: rec.analyze.quote.change_pct, last_score: null, last_signal: null, last_refresh_at: null }
    db.items.push(item); save()
    // le « calcul en arrière-plan » de la vraie app, simulé
    setTimeout(() => { Object.assign(item, scored(item.product_id)); save() }, 2500)
    return { item: itemOut(item) }
  }
  if ((m = p.match(/^\/watchlists\/(\d+)\/items\/(\d+)$/)) && method === 'DELETE') {
    const u = currentUser(headers)
    ownWatchlist(u, m[1])
    const item = db.items.find((i) => i.id === Number(m[2]))
    if (!item) fail('Produit introuvable dans cette watchlist')
    const alerts = db.alerts.filter((a) => a.item_id === item.id).length
    db.alerts = db.alerts.filter((a) => a.item_id !== item.id)
    db.items = db.items.filter((i) => i.id !== item.id); save()
    return { deleted: { id: item.id, name: item.name, symbol: item.symbol, alerts } }
  }
  if ((m = p.match(/^\/watchlists\/(\d+)\/items\/order$/))) {
    const u = currentUser(headers)
    ownWatchlist(u, m[1])
    body.ids.forEach((id, pos) => { const it = db.items.find((i) => i.id === id); if (it) it.position = pos })
    save(); return { ok: true }
  }
  if ((m = p.match(/^\/watchlists\/(\d+)\/refresh$/))) {
    const u = currentUser(headers)
    const w = ownWatchlist(u, m[1])
    db.items.filter((i) => i.watchlist_id === w.id).forEach((i) => Object.assign(i, scored(i.product_id)))
    save(); return { scheduled: true }
  }

  // ---- alertes
  if ((m = p.match(/^\/alerts\/item\/(\d+)$/))) {
    currentUser(headers)
    const item = db.items.find((i) => i.id === Number(m[1]))
    if (!item) fail('Produit introuvable')
    if (method === 'PUT') {
      for (const a of body.alerts) {
        let row = db.alerts.find((x) => x.item_id === item.id && x.alert_type === a.type)
        if (!row) { row = { id: nextId(), item_id: item.id, alert_type: a.type, last_state: null, last_triggered_at: null }; db.alerts.push(row) }
        row.enabled = a.enabled; row.frequency = a.frequency
      }
      save()
    }
    const alerts = Object.entries(ALERT_TYPES).map(([type, meta]) => {
      const r = db.alerts.find((x) => x.item_id === item.id && x.alert_type === type)
      return { type, ...meta, enabled: !!r?.enabled, frequency: r?.frequency || 'immediate', last_triggered_at: r?.last_triggered_at || null }
    })
    return { item: { id: item.id, name: item.name, symbol: item.symbol }, alerts, frequencies: FREQ, smtp_configured: false }
  }
  if (p === '/alerts/history') {
    const u = currentUser(headers)
    return { events: db.events.filter((e) => e.user_id === u.id).slice(0, Number(q.limit || 10)), smtp_configured: false }
  }
  if (p === '/alerts/test') return { delivered: false, status: 'Démo : les mails ne sont pas envoyés. Ils fonctionneront dans la vraie app, une fois Gmail configuré.' }
  if (p === '/alerts/check') { checkAlerts(); return { scheduled: true } }

  fail(`Démo : action non disponible (${p}).`)
}
