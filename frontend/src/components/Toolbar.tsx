import { useRef, type ChangeEvent } from 'react'
import { EXAMPLES, type Example } from '../lib/examples'

interface ToolbarProps {
  analyzing: boolean
  onAnalyze(): void
  onClear(): void
  onUpload(file: File): void
  onExample(example: Example): void
}

export default function Toolbar({ analyzing, onAnalyze, onClear, onUpload, onExample }: ToolbarProps) {
  const fileInput = useRef<HTMLInputElement>(null)

  function onFileChosen(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = '' // allow choosing the same file again
    if (file) onUpload(file)
  }

  function onExampleChosen(event: ChangeEvent<HTMLSelectElement>) {
    const example = EXAMPLES.find((e) => e.id === event.target.value)
    event.target.value = ''
    if (example) onExample(example)
  }

  return (
    <div className="toolbar" role="toolbar" aria-label="Source actions">
      <button type="button" className="primary" onClick={onAnalyze} disabled={analyzing}>
        {analyzing ? 'Analyzing…' : 'Analyze'}
      </button>
      <button type="button" onClick={onClear} disabled={analyzing}>
        Clear
      </button>
      <button type="button" onClick={() => fileInput.current?.click()} disabled={analyzing}>
        Upload .c
      </button>
      <input
        ref={fileInput}
        type="file"
        accept=".c"
        className="visually-hidden"
        tabIndex={-1}
        aria-label="Upload a .c file"
        onChange={onFileChosen}
        data-testid="file-input"
      />
      <label className="examples">
        <span>Examples</span>
        <select defaultValue="" onChange={onExampleChosen} disabled={analyzing}>
          <option value="" disabled>
            Choose an example…
          </option>
          {EXAMPLES.map((example) => (
            <option key={example.id} value={example.id}>
              {example.title}
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}
