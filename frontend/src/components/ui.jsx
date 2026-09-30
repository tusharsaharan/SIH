/** Shared design primitives — light engaging SOC language.
 *  Functional roles (Primer/Carbon-style): primary indigo = interactive/live,
 *  error red = critical, ok emerald = contained/healthy, muted = quiet. */

export function Card({ className = '', children, ...rest }) {
  return (
    <div className={`rounded-md border border-[#E2DED4] bg-[#FFFFFF] p-4 ${className}`} {...rest}>
      {children}
    </div>
  )
}

export function SectionTitle({ children, right = null }) {
  return (
    <div className="flex items-center justify-between mb-2">
      <span className="qf-section-title">{children}</span>
      {right}
    </div>
  )
}

const BADGE = {
  primary: 'bg-[#0F766E] text-white border-[#0F766E]',
  secondary: 'bg-transparent text-[#1C1917] border-[#E2DED4]',
  error: 'bg-[#F0D3D1] text-[#B42318] border-[#E1A7A3]',
  ok: 'bg-[#CDE4DA] text-[#067647] border-[#9BC8B5]',
  muted: 'bg-[#F4F3EF] text-[#57534E] border-[#E2DED4]',
  // legacy aliases
  orange: 'bg-[#F0D3D1] text-[#B42318] border-[#E1A7A3]',
  blue: 'bg-[#CFE4E2] text-[#115E59] border-[#9FC8C5]',
  lime: 'bg-[#CDE4DA] text-[#067647] border-[#9BC8B5]',
}

export function Badge({ tone = 'muted', className = '', children }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-light ${BADGE[tone] || BADGE.muted} ${className}`}>
      {children}
    </span>
  )
}

export function EmptyState({ glyph = '○', children }) {
  return (
    <div className="flex-1 grid place-items-center py-6 text-center">
      <div>
        <div className="text-2xl text-[#A8A29E]">{glyph}</div>
        <div className="mt-1 text-xs font-light text-[#57534E]">{children}</div>
      </div>
    </div>
  )
}

export function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded bg-[#E8E6E0] ${className}`} />
}

export function Stat({ label, value, tone = '' }) {
  return (
    <div className="flex items-center justify-between py-1 border-b border-[#E2DED4] last:border-0">
      <span className="text-[11px] font-light text-[#57534E]">{label}</span>
      <span className={`text-[11px] font-light tabular-nums ${tone || 'text-[#1C1917]'}`}>{value}</span>
    </div>
  )
}

export function Dot({ tone = 'muted', pulse = false }) {
  const c = {
    primary: 'bg-[#0F766E]',
    secondary: 'bg-[#A8A29E]',
    error: 'bg-[#B42318]',
    ok: 'bg-[#067647]',
    // legacy aliases
    orange: 'bg-[#B42318]',
    blue: 'bg-[#0F766E]',
    lime: 'bg-[#067647]',
    muted: 'bg-[#D6D3D1]',
  }[tone] || 'bg-[#D6D3D1]'
  return <span className={`inline-block w-1.5 h-1.5 rounded-full ${c} ${pulse ? 'animate-pulse' : ''}`} />
}
