import { useEffect, useState } from 'react'
import { BellRing, Check, Send } from 'lucide-react'
import { api } from '../lib/api'
import { Spinner } from './ui'

const supported = () => typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
const isIos = () => /iphone|ipad|ipod/i.test(navigator.userAgent)
const standalone = () => window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone

function keyBytes(b64) {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4)
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

const KINDS = [
  ['alerts', 'Mes alertes', 'signal fort, croisement de la MM100…'],
  ['trades', 'Portefeuilles fictifs', 'chaque achat ou vente du programme'],
  ['access', "Demandes d'accès", 'quelqu’un demande une invitation'],
]

// Notifications sur le téléphone (Web Push), réglables par sorte
export default function PushSettings({ isAdmin }) {
  const [info, setInfo] = useState(null)
  const [here, setHere] = useState(null) // abonnement de CET appareil
  const [busy, setBusy] = useState(null)
  const [msg, setMsg] = useState(null)

  useEffect(() => {
    api.pushStatus().then(setInfo).catch(() => {})
    if (supported()) {
      navigator.serviceWorker.getRegistration().then((reg) => reg?.pushManager.getSubscription()).then((s) => setHere(s || null)).catch(() => {})
    }
  }, [])

  const enable = async () => {
    setBusy('on')
    setMsg(null)
    try {
      const perm = await Notification.requestPermission()
      if (perm !== 'granted') throw new Error('Notifications refusées. Autorise-les dans les réglages du navigateur pour mm100.be, puis réessaie.')
      const reg = (await navigator.serviceWorker.getRegistration()) || (await navigator.serviceWorker.register('/sw.js'))
      await navigator.serviceWorker.ready
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(info.public_key) })
      setInfo(await api.pushSubscribe(sub.toJSON()))
      setHere(sub)
      await api.pushTest()
      setMsg({ ok: true, text: 'Activé ! Une notification de test vient d’être envoyée.' })
    } catch (e) {
      const pushDown = e.name === 'AbortError' || /push service/i.test(e.message || '')
      setMsg({ ok: false, text: pushDown
        ? 'Le service de notifications du téléphone ne répond pas (Chrome passe par les Services Google Play). Vérifie qu’ils sont installés et sans restriction de batterie, ou active les notifications depuis Firefox.'
        : e.message })
    } finally { setBusy(null) }
  }
  const disable = async () => {
    setBusy('off')
    try {
      await api.pushUnsubscribe(here.endpoint).then(setInfo)
      await here.unsubscribe()
      setHere(null)
      setMsg(null)
    } catch (e) { setMsg({ ok: false, text: e.message }) } finally { setBusy(null) }
  }
  const test = async () => {
    setBusy('test')
    try { await api.pushTest(); setMsg({ ok: true, text: 'Notification envoyée.' }) } catch (e) { setMsg({ ok: false, text: e.message }) } finally { setBusy(null) }
  }
  const toggle = async (kind) => {
    const next = !info.kinds[kind]
    setInfo({ ...info, kinds: { ...info.kinds, [kind]: next } })
    try { setInfo(await api.pushKinds({ [kind]: next })) } catch { /* l'état sera relu à la prochaine ouverture */ }
  }

  if (!info) return null
  const kinds = KINDS.filter(([k]) => k !== 'access' || isAdmin)
  return (
    <div className="mt-5 rounded-lg border border-line p-4">
      <h3 className="flex items-center gap-2 font-semibold"><BellRing className="h-4 w-4" /> Notifications sur le téléphone</h3>
      {!supported() ? (
        <p className="mt-2 text-sm text-muted">
          {isIos() && !standalone()
            ? 'Sur iPhone, installe d’abord MM100 sur l’écran d’accueil (Partager → « Sur l’écran d’accueil »), puis ouvre-le depuis son icône et reviens ici.'
            : 'Ce navigateur ne gère pas les notifications. Essaie avec Chrome ou Brave.'}
        </p>
      ) : here ? (
        <>
          <p className="mt-1 flex items-center gap-1.5 text-sm text-bull"><Check className="h-4 w-4" /> Actives sur cet appareil</p>
          <ul className="mt-3 space-y-2">
            {kinds.map(([k, label, hint]) => (
              <li key={k}>
                <label className="flex cursor-pointer items-start gap-3 text-sm">
                  <input type="checkbox" className="mt-1 h-4 w-4 accent-[#00FF88]" checked={info.kinds[k]} onChange={() => toggle(k)} />
                  <span>{label}<span className="block text-xs text-muted">{hint}</span></span>
                </label>
              </li>
            ))}
          </ul>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button className="btn-ghost justify-center border border-line text-sm" onClick={test} disabled={!!busy}>
              {busy === 'test' ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />} Tester
            </button>
            <button className="btn-ghost justify-center border border-line text-sm" onClick={disable} disabled={!!busy}>Désactiver ici</button>
          </div>
        </>
      ) : (
        <>
          <p className="mt-1 text-sm text-muted">
            Reçois tes alertes, les opérations des portefeuilles fictifs{isAdmin ? ' et les demandes d’accès' : ''} directement sur
            ce téléphone, même MM100 fermé.{info.devices > 0 ? ` Déjà actives sur ${info.devices} autre${info.devices > 1 ? 's' : ''} appareil${info.devices > 1 ? 's' : ''}.` : ''}
          </p>
          <button className="btn-primary mt-3 w-full" onClick={enable} disabled={!!busy}>
            {busy === 'on' ? <Spinner className="h-4 w-4" /> : <BellRing className="h-4 w-4" />} Activer sur cet appareil
          </button>
        </>
      )}
      {msg && <p className={`mt-2 text-sm ${msg.ok ? 'text-bull' : 'text-warn'}`} role="status">{msg.text}</p>}
    </div>
  )
}
