import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import type { AnalysisReport } from './api/types'
import { SRS_DEMO } from './lib/examples'
import { MAX_SOURCE_BYTES } from './lib/limits'
import { shownRanges } from './test/editorSpy'
import { markupReport, mixedReport, srsDemoReport, syntaxErrorsReport } from './test/fixtures'
import { fakeServer } from './test/server'

async function renderApp() {
  const user = userEvent.setup({ applyAccept: false })
  render(<App />)
  const editor = await screen.findByLabelText('C source code editor')
  return { user, editor }
}

async function analyzeWith(report: AnalysisReport, source = 'int main(void) { return 0; }') {
  const server = fakeServer(() => report)
  const { user, editor } = await renderApp()
  fireEvent.change(editor, { target: { value: source } })
  await user.click(screen.getByRole('button', { name: 'Analyze' }))
  await screen.findByText(/^Analysis complete/)
  return { user, editor, server }
}

const announcer = () => screen.getByTestId('announcer')

describe('editor and Analyze', () => {
  it('sends the source and shows the results', async () => {
    const { server } = await analyzeWith(srsDemoReport(), SRS_DEMO.source)

    expect(server.analyzeBodies).toEqual([{ language: 'c', source: SRS_DEMO.source }])
    expect(announcer()).toHaveTextContent('Analysis complete: 0 errors, 2 warnings, 0 suggestions.')
    const stages = screen.getByRole('list', { name: 'Analysis stages' })
    expect(within(stages).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      '✔Lexicalpassed',
      '✔Syntaxpassed',
      '✔Semanticpassed',
      '✔Optimizerpassed',
    ])
  })

  it('shows errors, warnings and suggestions in separate tabs', async () => {
    const { user } = await analyzeWith(srsDemoReport())
    const tabs = screen.getByRole('tablist', { name: 'Diagnostics' })
    expect(within(tabs).getAllByRole('tab').map((t) => t.textContent)).toEqual([
      'Errors (0)',
      'Warnings (2)',
      'Suggestions (0)',
    ])
    // The first non-empty tab is selected.
    expect(within(tabs).getByRole('tab', { selected: true })).toHaveTextContent('Warnings (2)')
    const panel = screen.getAllByRole('tabpanel').find((p) => !p.hidden)!
    expect(within(panel).getByText("Variable 'unused' is declared but its value is never read.")).toBeVisible()
    // Icon plus a text label, and the explanation for students.
    expect(within(panel).getAllByText('Warning')).toHaveLength(2)
    expect(within(panel).getByText(/has no effect on the program/)).toBeVisible()
    expect(within(panel).getByText('Line 5, column 9 · SEM-UNUSED')).toBeVisible()

    await user.click(within(tabs).getByRole('tab', { name: 'Errors (0)' }))
    expect(screen.getByText('No errors.')).toBeVisible()
  })

  it('separates syntax errors from later stages', async () => {
    const { user } = await analyzeWith(syntaxErrorsReport())
    expect(screen.getByRole('heading', { name: 'Lexical and syntax errors' })).toBeVisible()
    expect(screen.getByText(/later analysis stages are skipped/)).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Semantic errors' })).toBeNull()
    expect(screen.getByText('Missing \';\' at the end of this statement.')).toBeVisible()
    const stages = screen.getByRole('list', { name: 'Analysis stages' })
    expect(within(stages).getByText('Semantic').parentElement).toHaveTextContent('skipped')

    await user.click(screen.getByRole('tab', { name: 'Syntax tree' }))
    expect(screen.getByText('No syntax tree: fix the lexical and syntax errors first.')).toBeVisible()
    await user.click(screen.getByRole('tab', { name: 'Symbols' }))
    expect(screen.getByText('No symbol table: the semantic stage did not run.')).toBeVisible()
  })

  it('groups semantic errors on their own', async () => {
    await analyzeWith(mixedReport())
    expect(screen.getByRole('heading', { name: 'Semantic errors' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Lexical and syntax errors' })).toBeNull()
    expect(screen.getByRole('tab', { name: 'Warnings (1)' })).toBeVisible()
    expect(screen.getByRole('tab', { name: 'Suggestions (1)' })).toBeVisible()
  })

  it('jumps to the line of a diagnostic when it is clicked', async () => {
    const { user } = await analyzeWith(srsDemoReport())
    await user.click(screen.getByRole('button', { name: /declared but its value is never read/ }))
    expect(shownRanges).toEqual([{ line: 5, column: 9, endLine: 5, endColumn: 15 }])
    expect(screen.getByLabelText('C source code editor')).toHaveFocus()
  })

  it('shows statistics', async () => {
    await analyzeWith(srsDemoReport())
    const term = screen.getByText('Variables')
    expect(term.nextElementSibling).toHaveTextContent('2')
    expect(screen.getByText('Lines').nextElementSibling).toHaveTextContent('11')
  })

  it('analyzes with Ctrl+Enter from the editor', async () => {
    const server = fakeServer(() => srsDemoReport())
    const { user, editor } = await renderApp()
    fireEvent.change(editor, { target: { value: 'int x;' } })
    editor.focus()
    await user.keyboard('{Control>}{Enter}{/Control}')
    await screen.findByText(/^Analysis complete/)
    expect(server.analyzeBodies).toHaveLength(1)
  })

  it('notes when the results are out of date', async () => {
    const { editor } = await analyzeWith(srsDemoReport())
    expect(screen.queryByText(/The code has changed/)).toBeNull()
    fireEvent.change(editor, { target: { value: 'int changed;' } })
    expect(screen.getByText(/The code has changed since this analysis/)).toBeVisible()
  })
})

describe('Clear', () => {
  it('empties the editor and the results', async () => {
    const { user, editor } = await analyzeWith(srsDemoReport())
    await user.click(screen.getByRole('button', { name: 'Clear' }))
    expect(editor).toHaveValue('')
    expect(screen.queryByRole('tablist', { name: 'Diagnostics' })).toBeNull()
    expect(screen.getByText('Write or load some C code, then choose Analyze.')).toBeVisible()
    expect(announcer()).toHaveTextContent('Cleared the editor and the results.')
    expect(editor).toHaveFocus()
  })
})

describe('input checks in the browser', () => {
  it('reports empty input without calling the analyzer', async () => {
    const server = fakeServer(() => srsDemoReport())
    const { user, editor } = await renderApp()
    fireEvent.change(editor, { target: { value: '   \n ' } })
    await user.click(screen.getByRole('button', { name: 'Analyze' }))
    expect(screen.getByRole('alert')).toHaveTextContent('INPUT_EMPTY')
    expect(server.analyzeBodies).toEqual([])
  })

  it('reports oversized input without calling the analyzer', async () => {
    const server = fakeServer(() => srsDemoReport())
    const { user, editor } = await renderApp()
    fireEvent.change(editor, { target: { value: 'é'.repeat(MAX_SOURCE_BYTES / 2) + 'x' } })
    await user.click(screen.getByRole('button', { name: 'Analyze' }))
    expect(screen.getByRole('alert')).toHaveTextContent(
      'INPUT_TOO_LARGE: The source is 512,001 bytes; the limit is 512,000 bytes.',
    )
    expect(server.analyzeBodies).toEqual([])
  })

  it('rejects uploads that are not .c files', async () => {
    fakeServer(() => srsDemoReport())
    const { user, editor } = await renderApp()
    const file = new File(['print("hi")'], 'notes.txt', { type: 'text/plain' })
    await user.upload(screen.getByTestId('file-input'), file)
    expect(screen.getByRole('alert')).toHaveTextContent(
      'INPUT_UNSUPPORTED_TYPE: "notes.txt" is not a .c file. CodeGuard accepts C source files only.',
    )
    expect(editor).toHaveValue('')
  })

  it('loads an uploaded .c file into the editor', async () => {
    fakeServer(() => srsDemoReport())
    const { user, editor } = await renderApp()
    await user.upload(screen.getByTestId('file-input'), new File(['int main(void) { return 1; }'], 'Main.C'))
    expect(editor).toHaveValue('int main(void) { return 1; }')
    expect(announcer()).toHaveTextContent('Loaded Main.C.')
  })

  it('rejects an oversized upload', async () => {
    fakeServer(() => srsDemoReport())
    const { user, editor } = await renderApp()
    await user.upload(screen.getByTestId('file-input'), new File(['x'.repeat(MAX_SOURCE_BYTES + 1)], 'big.c'))
    expect(screen.getByRole('alert')).toHaveTextContent('INPUT_TOO_LARGE')
    expect(editor).toHaveValue('')
  })

  it('loads the SRS demo from the Examples menu', async () => {
    fakeServer(() => srsDemoReport())
    const { user, editor } = await renderApp()
    await user.selectOptions(screen.getByRole('combobox', { name: 'Examples' }), SRS_DEMO.id)
    expect(editor).toHaveValue(SRS_DEMO.source)
    expect(SRS_DEMO.source).toContain('int unused = 50;')
    expect(SRS_DEMO.source).toContain('if (10 > 5)')
  })
})

describe('API problems', () => {
  it('shows the error envelope with its reference', async () => {
    fakeServer(() => ({
      httpStatus: 503,
      body: {
        error: {
          code: 'ANALYSIS_TIMEOUT',
          message: 'The analysis took longer than 5 seconds and was stopped.',
          analysis_id: 'abc-123',
        },
      },
    }))
    const { user, editor } = await renderApp()
    fireEvent.change(editor, { target: { value: 'int x;' } })
    await user.click(screen.getByRole('button', { name: 'Analyze' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('ANALYSIS_TIMEOUT: The analysis took longer than 5 seconds and was stopped.')
    expect(alert).toHaveTextContent('Reference: abc-123')
  })

  it('explains a network failure', async () => {
    fakeServer(() => 'network-error')
    const { user, editor } = await renderApp()
    fireEvent.change(editor, { target: { value: 'int x;' } })
    await user.click(screen.getByRole('button', { name: 'Analyze' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('NETWORK_ERROR: Could not reach the CodeGuard server.')
  })
})

describe('teaching views', () => {
  it('shows the AST as a collapsible tree linked to the editor', async () => {
    const { user } = await analyzeWith(srsDemoReport())
    await user.click(screen.getByRole('tab', { name: 'Syntax tree' }))
    const tree = screen.getByRole('list', { name: 'Abstract syntax tree' })
    expect(within(tree).getByText('TranslationUnit')).toBeVisible()
    expect(within(tree).getByText('FunctionDef main')).toBeVisible()
    expect(within(tree).queryByText('VarDecl unused')).toBeNull() // collapsed below level 2

    await user.click(within(tree).getByRole('button', { name: 'Expand Block' }))
    await user.click(within(tree).getAllByRole('button', { name: 'Expand Declaration' })[0])
    await user.click(within(tree).getByRole('button', { name: 'VarDecl x, line 4, column 9' }))
    expect(shownRanges.at(-1)).toEqual({ line: 4, column: 9, endLine: 4, endColumn: 15 })

    const collapse = within(tree).getByRole('button', { name: 'Collapse FunctionDef main' })
    expect(collapse).toHaveAttribute('aria-expanded', 'true')
    await user.click(collapse)
    expect(within(tree).queryByText('Block')).toBeNull()
  })

  it('shows the symbol table grouped by scope', async () => {
    const { user } = await analyzeWith(mixedReport())
    await user.click(screen.getByRole('tab', { name: 'Symbols' }))
    const fileScope = screen.getByRole('region', { name: 'File scope' })
    const main = within(fileScope).getByRole('region', { name: 'Function main (line 2)' })
    expect(within(main).getByRole('rowheader', { name: 'total' })).toBeVisible()
    const loop = within(main).getByRole('region', { name: 'for loop (line 4)' })
    const row = within(loop).getByRole('rowheader', { name: 'i' }).closest('tr')!
    expect(Array.from(row.cells).map((c) => c.textContent)).toEqual(['i', 'variable', 'int', '4', '2', '1'])
  })

  it('shows the token table', async () => {
    const { user } = await analyzeWith(srsDemoReport())
    await user.click(screen.getByRole('tab', { name: 'Tokens' }))
    const first = screen.getAllByRole('row')[1]
    expect(Array.from((first as HTMLTableRowElement).cells).map((c) => c.textContent)).toEqual([
      '1',
      'KEYWORD',
      'int',
      '3',
      '1',
    ])
  })
})

describe('safe rendering', () => {
  it('renders markup in diagnostics and tokens as plain text', async () => {
    const report = markupReport()
    report.diagnostics[0].message = '<img src=x onerror="alert(1)"> injected'
    report.diagnostics[0].explanation = '<b>bold?</b>'
    const { user } = await analyzeWith(report)
    expect(screen.getByText('<img src=x onerror="alert(1)"> injected')).toBeVisible()
    expect(screen.getByText('<b>bold?</b>')).toBeVisible()
    await user.click(screen.getByRole('tab', { name: 'Tokens' }))
    expect(screen.getByText('"<img src=x onerror=alert(1)>"')).toBeVisible()
    expect(document.querySelector('img, b')).toBeNull()
  })
})

describe('server wake-up', () => {
  it('shows the wake-up message when /health is slow, then hides it', async () => {
    vi.useFakeTimers()
    const server = fakeServer(() => srsDemoReport(), { health: 'hang' })
    render(<App />)
    expect(screen.queryByText(/Waking up the server/)).toBeNull()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_900)
    })
    expect(screen.queryByText(/Waking up the server/)).toBeNull()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200)
    })
    expect(screen.getByText('Waking up the server, this can take about a minute.')).toBeVisible()
    // The health check gives up after 90 s and offers a retry.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(90_000)
    })
    expect(screen.getByRole('alert')).toHaveTextContent('The CodeGuard server is not responding.')
    server.health = 'ok'
    vi.useRealTimers()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText(/Server: online/)).toBeVisible()
    expect(screen.queryByText(/Waking up the server/)).toBeNull()
  })

  it('shows no wake-up message when the server answers quickly', async () => {
    fakeServer(() => srsDemoReport())
    await renderApp()
    expect(await screen.findByText(/Server: online/)).toBeVisible()
    expect(screen.queryByText(/Waking up the server/)).toBeNull()
  })
})

describe('keyboard', () => {
  it('reaches every main control with Tab and analyzes with Enter', async () => {
    const server = fakeServer(() => srsDemoReport())
    const { user, editor } = await renderApp()
    fireEvent.change(editor, { target: { value: 'int x;' } })

    await user.tab()
    expect(screen.getByRole('button', { name: 'Analyze' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Clear' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Upload .c' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('combobox', { name: 'Examples' })).toHaveFocus()
    await user.tab()
    expect(editor).toHaveFocus()

    await user.tab({ shift: true })
    await user.tab({ shift: true })
    await user.tab({ shift: true })
    await user.tab({ shift: true })
    expect(screen.getByRole('button', { name: 'Analyze' })).toHaveFocus()
    await user.keyboard('{Enter}')
    await screen.findByText(/^Analysis complete/)
    expect(server.analyzeBodies).toHaveLength(1)

    // Into the results: the diagnostics tabs, then their panel.
    const selectedTab = screen.getByRole('tab', { name: 'Warnings (2)' })
    selectedTab.focus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Suggestions (0)' })).toHaveFocus()
    expect(screen.getByRole('tab', { name: 'Suggestions (0)' })).toHaveAttribute('aria-selected', 'true')
  })

  it('announces results in a live region', async () => {
    await analyzeWith(srsDemoReport())
    expect(announcer()).toHaveAttribute('aria-live', 'polite')
    expect(announcer()).toHaveAttribute('role', 'status')
  })

  it('shows how to move focus out of the editor', async () => {
    await renderApp()
    expect(screen.getByText(/so that Tab moves focus out instead/)).toBeVisible()
  })
})
