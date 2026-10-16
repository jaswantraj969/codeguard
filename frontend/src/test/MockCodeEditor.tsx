// Test double for components/CodeEditor: Monaco cannot run in jsdom.
// Same props and handle, backed by a textarea; showRange calls are recorded.
import { useImperativeHandle, useRef, type Ref } from 'react'
import type { CodeEditorHandle } from '../components/CodeEditor'
import { shownRanges } from './editorSpy'

interface Props {
  value: string
  onChange(value: string): void
  onSubmit(): void
  ref?: Ref<CodeEditorHandle>
}

export default function MockCodeEditor({ value, onChange, onSubmit, ref }: Props) {
  const textarea = useRef<HTMLTextAreaElement>(null)
  useImperativeHandle(ref, () => ({
    focus: () => textarea.current?.focus(),
    showRange: (range) => {
      shownRanges.push(range)
      textarea.current?.focus()
    },
  }))
  return (
    <textarea
      ref={textarea}
      aria-label="C source code editor"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' && event.ctrlKey) onSubmit()
      }}
    />
  )
}
