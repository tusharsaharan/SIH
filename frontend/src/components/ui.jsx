/** Shared design primitives — one visual language across all panels. */

export function Card({ className = '', children, ...rest }) {
  return (
    <div className={`rounded-2xl border border-line bg-ivory-soft shadow-soft p-4 ${className}`} {...rest}>
      {children}
    </div>
  )
}

export function SectionTitle({ children, right = null }) {
  return (
    <div className="flex items-center justify-between mb-2">
      <span className="text-xs tracking-widest text-ink-soft uppercase">{children}</span>
      {right}
    </div>
  )
}

const BADGE = {
  orange: 'bg-orange-100 text-orange-700 border-orange-200',
  blue: 'bg-blue-100 text-blue-700 border-blue-200',
  lime: 'bg-lime-100 text-lime-700 border-lime-200',
  muted: 'bg-ivory-deep/70 text-ink-soft border-line',
}

export function Badge({ tone = 'muted', className = '', children }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${BADGE[tone] || BADGE.muted} ${className}`}>
      {children}
    </span>
  )
}

export function EmptyState({ glyph = '○', children }) {
  return (
    <div className="flex-1 grid place-items-center py-6 text-center">
      <div>
        <div className="text-2xl text-ink-faint">{glyph}</div>
        <div className="mt-1 text-xs text-ink-faint">{children}</div>
      </div>
    </div>
  )
}

export function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded-lg bg-ivory-deep ${className}`} />
}

export function Stat({ label, value, tone = '' }) {
  return (
    <div className="flex items-center justify-between py-1 border-b border-line last:border-0">
      <span className="text-[11px] text-ink-soft">{label}</span>
      <span className={`text-[11px] tabular-nums ${tone || 'text-ink'}`}>{value}</span>
    </div>
  )
}

export function Dot({ tone = 'muted', pulse = false }) {
  const c = { orange: 'bg-orange-500', blue: 'bg-blue-500', lime: 'bg-lime-500', muted: 'bg-[#D8CFB6]' }[tone] || 'bg-[#D8CFB6]'
  return <span className={`inline-block w-1.5 h-1.5 rounded-full ${c} ${pulse ? 'animate-pulse' : ''}`} />
}
