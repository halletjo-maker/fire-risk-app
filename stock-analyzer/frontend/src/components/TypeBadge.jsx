import { TYPE_STYLES } from '../lib/format'

export default function TypeBadge({ type, label }) {
  return (
    <span className={`inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${TYPE_STYLES[type] || TYPE_STYLES.AUTRE}`}>
      {label || type}
    </span>
  )
}
