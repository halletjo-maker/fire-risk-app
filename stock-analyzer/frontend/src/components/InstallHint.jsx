import { useEffect, useState } from 'react'
import { Download, Share, X } from 'lucide-react'

const KEY = 'ab_install_hint_closed'
const isStandalone = () =>
  window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone === true
const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent) ||
  (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
const isMobile = () => /android|iphone|ipad|ipod|mobile/i.test(navigator.userAgent) || isIOS()

// Bandeau « installer l'application » : iPhone = instructions Safari ; Android = bouton d'installation
export default function InstallHint() {
  const [closed, setClosed] = useState(() => { try { return localStorage.getItem(KEY) === '1' } catch { return false } })
  const [prompt, setPrompt] = useState(null)

  useEffect(() => {
    const onPrompt = (e) => { e.preventDefault(); setPrompt(e) }
    window.addEventListener('beforeinstallprompt', onPrompt)
    return () => window.removeEventListener('beforeinstallprompt', onPrompt)
  }, [])

  const close = () => { setClosed(true); try { localStorage.setItem(KEY, '1') } catch { /* navigation privée */ } }
  if (closed || isStandalone() || !isMobile()) return null
  if (!isIOS() && !prompt) return null

  return (
    <div className="card relative flex gap-3 border-bull/40 p-3 pr-10 text-sm" role="note">
      <img src="/icon-192.png" alt="" className="h-10 w-10 shrink-0 rounded-lg" />
      <div className="min-w-0">
        <p className="font-semibold">Installe l'application sur ton téléphone</p>
        {isIOS() ? (
          <p className="mt-0.5 text-muted">
            Dans Safari, touche <Share className="inline h-4 w-4 align-text-bottom text-gray-100" aria-label="Partager" /> en bas de
            l'écran, puis <b className="whitespace-nowrap text-gray-100">«&nbsp;Sur l'écran d'accueil&nbsp;»</b>. Elle s'ouvrira en plein écran, comme une vraie appli.
          </p>
        ) : (
          <button className="btn-primary mt-2 px-3 py-1.5 text-sm" onClick={async () => { prompt.prompt(); await prompt.userChoice; setPrompt(null); close() }}>
            <Download className="h-4 w-4" /> Installer
          </button>
        )}
      </div>
      <button className="absolute right-2 top-2 rounded-md p-1.5 text-muted hover:text-gray-100" onClick={close} aria-label="Masquer">
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
