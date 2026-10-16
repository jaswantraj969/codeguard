import type { Statistics } from '../api/types'

const ROWS: { key: keyof Statistics; label: string }[] = [
  { key: 'variables', label: 'Variables' },
  { key: 'functions', label: 'Functions' },
  { key: 'errors', label: 'Errors' },
  { key: 'warnings', label: 'Warnings' },
  { key: 'suggestions', label: 'Suggestions' },
  { key: 'tokens', label: 'Tokens' },
  { key: 'lines', label: 'Lines' },
  { key: 'duration_ms', label: 'Analysis time (ms)' },
]

export default function StatisticsPanel({ statistics }: { statistics: Statistics }) {
  return (
    <dl className="statistics">
      {ROWS.map(({ key, label }) => (
        <div key={key} className="statistic">
          <dt>{label}</dt>
          <dd>{statistics[key].toLocaleString('en-US')}</dd>
        </div>
      ))}
    </dl>
  )
}
