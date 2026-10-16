import { useEffect, useImperativeHandle, useRef, type Ref } from 'react'
import type { SourceRange } from '../api/types'
import { monaco } from '../editor/monaco'

export interface CodeEditorHandle {
  focus(): void
  /** Scroll to a range, select it and highlight its lines. */
  showRange(range: SourceRange): void
}

interface CodeEditorProps {
  value: string
  onChange(value: string): void
  /** Ctrl+Enter / Cmd+Enter inside the editor. */
  onSubmit(): void
  ref?: Ref<CodeEditorHandle>
}

const DARK_QUERY = '(prefers-color-scheme: dark)'

function systemTheme(): string {
  return window.matchMedia?.(DARK_QUERY).matches ? 'vs-dark' : 'vs'
}

export default function CodeEditor({ value, onChange, onSubmit, ref }: CodeEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null)
  const decorationsRef = useRef<monaco.editor.IEditorDecorationsCollection | null>(null)
  const callbacks = useRef({ onChange, onSubmit })
  const initialValue = useRef(value)

  useEffect(() => {
    callbacks.current = { onChange, onSubmit }
  })

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const editor = monaco.editor.create(container, {
      value: initialValue.current,
      language: 'c',
      theme: systemTheme(),
      ariaLabel: 'C source code editor',
      automaticLayout: true,
      minimap: { enabled: false },
      fontSize: 14,
      tabSize: 4,
      scrollBeyondLastLine: false,
      renderLineHighlight: 'line',
    })
    editorRef.current = editor
    decorationsRef.current = editor.createDecorationsCollection()

    const contentListener = editor.onDidChangeModelContent(() => {
      decorationsRef.current?.clear()
      callbacks.current.onChange(editor.getValue())
    })
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => callbacks.current.onSubmit())

    const media = window.matchMedia?.(DARK_QUERY)
    const onTheme = () => monaco.editor.setTheme(systemTheme())
    media?.addEventListener('change', onTheme)

    return () => {
      media?.removeEventListener('change', onTheme)
      contentListener.dispose()
      editor.dispose()
      editorRef.current = null
    }
  }, [])

  // Apply changes made outside the editor (Clear, Upload, Examples).
  useEffect(() => {
    const editor = editorRef.current
    if (editor && editor.getValue() !== value) editor.setValue(value)
  }, [value])

  useImperativeHandle(
    ref,
    () => ({
      focus: () => editorRef.current?.focus(),
      showRange: ({ line, column, endLine, endColumn }) => {
        const editor = editorRef.current
        if (!editor) return
        const range = new monaco.Range(line, column, endLine, endColumn)
        editor.revealRangeInCenter(range)
        editor.setSelection(range)
        decorationsRef.current?.set([
          { range, options: { isWholeLine: true, className: 'cg-highlight-line' } },
        ])
        editor.focus()
      },
    }),
    [],
  )

  return <div ref={containerRef} className="code-editor" data-testid="code-editor" />
}
