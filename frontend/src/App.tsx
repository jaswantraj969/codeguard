import { Suspense, lazy, useRef, useState } from 'react'
import { analyze, failure } from './api/client'
import type { AnalysisReport, ApiError, Diagnostic, SourceRange } from './api/types'
import AstView from './components/AstView'
import type { CodeEditorHandle } from './components/CodeEditor'
import DiagnosticsPanel from './components/DiagnosticsPanel'
import StageStatusBar from './components/StageStatusBar'
import StatisticsPanel from './components/StatisticsPanel'
import SymbolView from './components/SymbolView'
import Tabs from './components/Tabs'
import TokenTable from './components/TokenTable'
import Toolbar from './components/Toolbar'
import { useServerStatus } from './hooks/useServerStatus'
import type { Example } from './lib/examples'
import { formatBytes, isCFileName, utf8ByteLength } from './lib/limits'

// Monaco is large; load it separately so the page and the server ping start at once.
const CodeEditor = lazy(() => import('./components/CodeEditor'))

function summary(report: AnalysisReport): string {
  const { errors, warnings, suggestions } = report.statistics
  const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
  return `Analysis complete: ${plural(errors, 'error')}, ${plural(warnings, 'warning')}, ${plural(suggestions, 'suggestion')}.`
}

function tooLarge(bytes: number, limit: number): ApiError {
  return failure(
    'INPUT_TOO_LARGE',
    `The source is ${formatBytes(bytes)}; the limit is ${formatBytes(limit)}.`,
  ).error
}

export default function App() {
  const server = useServerStatus()
  const editor = useRef<CodeEditorHandle>(null)
  const [source, setSource] = useState('')
  const [report, setReport] = useState<AnalysisReport | null>(null)
  const [analyzedSource, setAnalyzedSource] = useState<string | null>(null)
  const [problem, setProblem] = useState<ApiError | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [announcement, setAnnouncement] = useState('')
  // From the server's /config. Until it loads, the API alone enforces the limit.
  const maxSourceBytes = server.config?.max_source_bytes ?? null

  function reportProblem(error: ApiError) {
    setProblem(error)
    setAnnouncement(error.message)
  }

  async function runAnalysis() {
    if (analyzing) return
    if (!source.trim()) {
      reportProblem(failure('INPUT_EMPTY', 'Write some C code or choose an example first.').error)
      return
    }
    if (maxSourceBytes !== null) {
      const bytes = utf8ByteLength(source)
      if (bytes > maxSourceBytes) {
        reportProblem(tooLarge(bytes, maxSourceBytes))
        return
      }
    }
    setProblem(null)
    setAnalyzing(true)
    setAnnouncement('Analyzing…')
    const result = await analyze(source)
    setAnalyzing(false)
    if (result.ok) {
      setReport(result.report)
      setAnalyzedSource(source)
      setAnnouncement(summary(result.report))
    } else {
      reportProblem(result.error)
    }
  }

  function loadSource(text: string) {
    setSource(text)
    setProblem(null)
  }

  async function onUpload(file: File) {
    if (!isCFileName(file.name)) {
      reportProblem(
        failure(
          'INPUT_UNSUPPORTED_TYPE',
          `"${file.name}" is not a .c file. CodeGuard accepts C source files only.`,
        ).error,
      )
      return
    }
    if (maxSourceBytes !== null && file.size > maxSourceBytes) {
      reportProblem(tooLarge(file.size, maxSourceBytes))
      return
    }
    loadSource(await file.text())
    setAnnouncement(`Loaded ${file.name}.`)
  }

  function onExample(example: Example) {
    loadSource(example.source)
    setAnnouncement(`Loaded example: ${example.title}.`)
  }

  function onClear() {
    setSource('')
    setReport(null)
    setAnalyzedSource(null)
    setProblem(null)
    setAnnouncement('Cleared the editor and the results.')
    editor.current?.focus()
  }

  function showRange(range: SourceRange) {
    editor.current?.showRange(range)
  }

  function showDiagnostic(d: Diagnostic) {
    showRange({
      line: d.line,
      column: d.column,
      endLine: d.end_line ?? d.line,
      endColumn: d.end_column ?? d.column + 1,
    })
  }

  const syntaxPassed = report?.status.find((s) => s.stage === 'syntax')?.status === 'passed'
  const stale = report !== null && analyzedSource !== source

  return (
    <div className="app">
      <header className="app-header">
        <h1>CodeGuard</h1>
        <p className="tagline">A mini static analyzer for C that shows each stage of a compiler.</p>
        <p className={`server server-${server.state}`}>
          <span aria-hidden="true">●</span> Server:{' '}
          {
            {
              checking: 'connecting…',
              waking: 'waking up…',
              online: 'online',
              offline: 'not responding',
            }[server.state]
          }
        </p>
      </header>

      {server.state === 'waking' && (
        <p className="notice" role="status">
          Waking up the server, this can take about a minute.
        </p>
      )}
      {server.state === 'offline' && (
        <div className="notice notice-error" role="alert">
          The CodeGuard server is not responding.{' '}
          <button type="button" className="link" onClick={server.retry}>
            Try again
          </button>
        </div>
      )}

      <p className="visually-hidden" role="status" aria-live="polite" data-testid="announcer">
        {announcement}
      </p>

      <main className="layout">
        <section className="pane editor-pane" aria-labelledby="source-heading">
          <h2 id="source-heading">Source code</h2>
          <Toolbar
            analyzing={analyzing}
            onAnalyze={runAnalysis}
            onClear={onClear}
            onUpload={onUpload}
            onExample={onExample}
          />
          <p className="hint" id="editor-hint">
            Inside the editor, Tab indents. Press <kbd>Ctrl</kbd>+<kbd>M</kbd> (on macOS{' '}
            <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>M</kbd>) so that Tab moves focus out instead.{' '}
            <kbd>Ctrl</kbd>+<kbd>Enter</kbd> analyzes.
            {maxSourceBytes !== null && <> Maximum size: {formatBytes(maxSourceBytes)}.</>}
          </p>
          <Suspense fallback={<div className="code-editor editor-loading">Loading the editor…</div>}>
            <CodeEditor ref={editor} value={source} onChange={setSource} onSubmit={runAnalysis} />
          </Suspense>
          {problem && (
            <div className="problem" role="alert">
              <strong>{problem.code}:</strong> {problem.message}
              {problem.analysis_id && <span className="reference"> Reference: {problem.analysis_id}</span>}
            </div>
          )}
        </section>

        <section className="pane results-pane" aria-labelledby="results-heading">
          <h2 id="results-heading">Results</h2>
          {stale && (
            <p className="note">The code has changed since this analysis. Analyze again to update the results.</p>
          )}
          <StageStatusBar status={report?.status ?? null} />
          {report ? (
            <>
              <h3>Diagnostics</h3>
              <DiagnosticsPanel key={report.analysis_id} diagnostics={report.diagnostics} onSelect={showDiagnostic} />
              <h3>Statistics</h3>
              <StatisticsPanel statistics={report.statistics} />
              <h3>How the compiler sees your code</h3>
              <Tabs
                key={report.analysis_id}
                label="Compiler stages"
                tabs={[
                  {
                    id: 'tokens',
                    label: 'Tokens',
                    panel: (
                      <TokenTable
                        tokens={report.tokens}
                        total={report.statistics.tokens}
                        truncated={report.truncated.tokens}
                      />
                    ),
                  },
                  {
                    id: 'ast',
                    label: 'Syntax tree',
                    panel: (
                      <AstView
                        ast={report.ast}
                        truncated={report.truncated.ast}
                        syntaxPassed={syntaxPassed}
                        onShowRange={showRange}
                      />
                    ),
                  },
                  { id: 'symbols', label: 'Symbols', panel: <SymbolView symbols={report.symbols} /> },
                ]}
              />
            </>
          ) : (
            <p className="empty">Write or load some C code, then choose Analyze.</p>
          )}
        </section>
      </main>
    </div>
  )
}
