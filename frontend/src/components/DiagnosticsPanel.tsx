import type { Diagnostic, Severity } from '../api/types'
import SeverityBadge from './SeverityBadge'
import Tabs from './Tabs'

interface DiagnosticsPanelProps {
  diagnostics: Diagnostic[]
  onSelect(diagnostic: Diagnostic): void
}

const SYNTAX_STAGES = new Set(['lexical', 'syntax'])

function DiagnosticItem({ d, onSelect }: { d: Diagnostic; onSelect(d: Diagnostic): void }) {
  return (
    <li className={`diagnostic diagnostic-${d.severity}`}>
      <button type="button" className="diagnostic-main" onClick={() => onSelect(d)}>
        <SeverityBadge severity={d.severity} />
        <span className="diagnostic-message">{d.message}</span>
        <span className="diagnostic-meta">
          Line {d.line}, column {d.column} · {d.rule_id}
        </span>
      </button>
      <p className="diagnostic-explanation">{d.explanation}</p>
      {d.fix_hint && (
        <p className="diagnostic-hint">
          <strong>How to fix:</strong> {d.fix_hint}
        </p>
      )}
    </li>
  )
}

function DiagnosticList({
  items,
  onSelect,
}: {
  items: Diagnostic[]
  onSelect(d: Diagnostic): void
}) {
  return (
    <ul className="diagnostic-list">
      {items.map((d, index) => (
        <DiagnosticItem key={`${d.rule_id}-${d.line}-${d.column}-${index}`} d={d} onSelect={onSelect} />
      ))}
    </ul>
  )
}

function ErrorsPanel({ errors, onSelect }: { errors: Diagnostic[]; onSelect(d: Diagnostic): void }) {
  if (errors.length === 0) return <p className="empty">No errors.</p>
  const structural = errors.filter((d) => SYNTAX_STAGES.has(d.stage))
  const semantic = errors.filter((d) => !SYNTAX_STAGES.has(d.stage))
  return (
    <>
      {structural.length > 0 && (
        <section aria-labelledby="syntax-errors-heading">
          <h4 id="syntax-errors-heading">Lexical and syntax errors</h4>
          <p className="note">The later analysis stages are skipped until these are fixed.</p>
          <DiagnosticList items={structural} onSelect={onSelect} />
        </section>
      )}
      {semantic.length > 0 && (
        <section aria-labelledby="semantic-errors-heading">
          <h4 id="semantic-errors-heading">Semantic errors</h4>
          <DiagnosticList items={semantic} onSelect={onSelect} />
        </section>
      )}
    </>
  )
}

const TITLES: Record<Severity, string> = {
  error: 'Errors',
  warning: 'Warnings',
  suggestion: 'Suggestions',
}

export default function DiagnosticsPanel({ diagnostics, onSelect }: DiagnosticsPanelProps) {
  const bySeverity = (severity: Severity) => diagnostics.filter((d) => d.severity === severity)
  const errors = bySeverity('error')
  const warnings = bySeverity('warning')
  const suggestions = bySeverity('suggestion')
  const initialTab = errors.length ? 'error' : warnings.length ? 'warning' : suggestions.length ? 'suggestion' : 'error'
  const tab = (severity: Severity, count: number) => (
    <>
      {TITLES[severity]} <span className="count">({count})</span>
    </>
  )

  return (
    <Tabs
      label="Diagnostics"
      initialTab={initialTab}
      tabs={[
        { id: 'error', label: tab('error', errors.length), panel: <ErrorsPanel errors={errors} onSelect={onSelect} /> },
        {
          id: 'warning',
          label: tab('warning', warnings.length),
          panel: warnings.length ? <DiagnosticList items={warnings} onSelect={onSelect} /> : <p className="empty">No warnings.</p>,
        },
        {
          id: 'suggestion',
          label: tab('suggestion', suggestions.length),
          panel: suggestions.length ? (
            <DiagnosticList items={suggestions} onSelect={onSelect} />
          ) : (
            <p className="empty">No suggestions.</p>
          ),
        },
      ]}
    />
  )
}
