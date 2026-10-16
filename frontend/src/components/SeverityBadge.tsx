import type { Severity } from '../api/types'

const ICONS: Record<Severity, string> = { error: '✖', warning: '⚠', suggestion: '💡' }
const LABELS: Record<Severity, string> = { error: 'Error', warning: 'Warning', suggestion: 'Suggestion' }

/** Severity shown with an icon and a text label, never by colour alone. */
export default function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`badge badge-${severity}`}>
      <span aria-hidden="true">{ICONS[severity]}</span> {LABELS[severity]}
    </span>
  )
}
