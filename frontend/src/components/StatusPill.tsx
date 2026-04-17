import type { ModelRuntimeStatus, RiskLevel } from '../types'

type StatusPillProps = {
  label: string
  tone?: ModelRuntimeStatus | RiskLevel | 'neutral'
}

export function StatusPill({ label, tone = 'neutral' }: StatusPillProps) {
  const toneClass = tone.toString().replaceAll('_', '-')
  return <span className={`status-pill tone-${toneClass}`}>{label}</span>
}
