import type { StageName, StageState, StageStatus } from '../api/types'

const STAGES: { stage: StageName; label: string }[] = [
  { stage: 'lexical', label: 'Lexical' },
  { stage: 'syntax', label: 'Syntax' },
  { stage: 'semantic', label: 'Semantic' },
  { stage: 'optimizer', label: 'Optimizer' },
]

const ICONS: Record<StageState | 'pending', string> = {
  passed: '✔',
  failed: '✖',
  skipped: '–',
  pending: '○',
}

/** The four pipeline stages, each with an icon and a text status. */
export default function StageStatusBar({ status }: { status: StageStatus[] | null }) {
  return (
    <ol className="stages" aria-label="Analysis stages">
      {STAGES.map(({ stage, label }) => {
        const entry = status?.find((s) => s.stage === stage)
        const state = entry?.status ?? 'pending'
        return (
          <li key={stage} className={`stage stage-${state}`}>
            <span aria-hidden="true" className="stage-icon">
              {ICONS[state]}
            </span>
            <span className="stage-name">{label}</span>
            <span className="stage-state">{state === 'pending' ? 'not run' : state}</span>
            {entry?.detail && <span className="stage-detail">{entry.detail}</span>}
          </li>
        )
      })}
    </ol>
  )
}
