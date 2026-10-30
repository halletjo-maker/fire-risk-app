import { useState } from 'react'
import { Eye, EyeOff, Lock } from 'lucide-react'

export default function PasswordInput({ id, value, onChange, autoComplete = 'current-password', placeholder }) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="relative mt-2">
      <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
      <input
        id={id}
        type={visible ? 'text' : 'password'}
        autoComplete={autoComplete}
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        className="input px-9"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute right-1 top-1/2 -translate-y-1/2 rounded-md p-2 text-muted transition hover:text-gray-200"
        aria-label={visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
        title={visible ? 'Masquer' : 'Afficher'}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  )
}
