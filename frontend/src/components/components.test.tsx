import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { TokenInfo } from '../api/types'
import { mixedReport } from '../test/fixtures'
import AstView from './AstView'
import StageStatusBar from './StageStatusBar'
import Tabs from './Tabs'
import TokenTable, { TOKEN_PAGE_SIZE } from './TokenTable'

describe('Tabs', () => {
  const tabs = ['One', 'Two', 'Three'].map((name) => ({ id: name, label: name, panel: <p>{name} panel</p> }))

  it('moves between tabs with arrow keys, Home and End', async () => {
    const user = userEvent.setup()
    render(<Tabs label="Example" tabs={tabs} />)
    const tab = (name: string) => screen.getByRole('tab', { name })
    tab('One').focus()
    await user.keyboard('{ArrowRight}')
    expect(tab('Two')).toHaveFocus()
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Two panel')
    await user.keyboard('{End}')
    expect(tab('Three')).toHaveAttribute('aria-selected', 'true')
    await user.keyboard('{ArrowRight}') // wraps
    expect(tab('One')).toHaveFocus()
    await user.keyboard('{ArrowLeft}') // wraps back
    expect(tab('Three')).toHaveFocus()
    await user.keyboard('{Home}')
    expect(tab('One')).toHaveFocus()
  })

  it('keeps only the selected tab in the Tab order and links tabs to panels', () => {
    render(<Tabs label="Example" tabs={tabs} initialTab="Two" />)
    const [one, two] = screen.getAllByRole('tab')
    expect(one).toHaveAttribute('tabindex', '-1')
    expect(two).toHaveAttribute('tabindex', '0')
    const panel = screen.getByRole('tabpanel')
    expect(panel).toHaveAttribute('aria-labelledby', two.id)
    expect(two).toHaveAttribute('aria-controls', panel.id)
  })
})

describe('TokenTable', () => {
  const tokens: TokenInfo[] = Array.from({ length: 450 }, (_, i) => ({
    type: 'IDENTIFIER',
    lexeme: `t${i}`,
    line: 1,
    column: i + 1,
  }))

  it('adds rows a page at a time', async () => {
    const user = userEvent.setup()
    render(<TokenTable tokens={tokens} total={450} truncated={false} />)
    expect(screen.getAllByRole('row')).toHaveLength(TOKEN_PAGE_SIZE + 1) // + header
    await user.click(screen.getByRole('button', { name: 'Show 200 more tokens' }))
    await user.click(screen.getByRole('button', { name: 'Show 50 more tokens' }))
    expect(screen.getAllByRole('row')).toHaveLength(451)
    expect(screen.queryByRole('button', { name: /more tokens/ })).toBeNull()
  })

  it('says when the token view is truncated', () => {
    render(<TokenTable tokens={tokens} total={12_345} truncated />)
    expect(screen.getByRole('note')).toHaveTextContent('Showing the first 450 of 12,345 tokens.')
  })
})

describe('AstView', () => {
  it('labels the parts of control statements', async () => {
    const user = userEvent.setup()
    const report = mixedReport()
    render(<AstView ast={report.ast} truncated={false} syntaxPassed onShowRange={vi.fn()} />)
    const tree = screen.getByRole('list', { name: 'Abstract syntax tree' })
    // FunctionDef main starts expanded (the first two levels are open).
    await user.click(within(tree).getByRole('button', { name: 'Expand Block' }))
    await user.click(within(tree).getByRole('button', { name: 'Expand For' }))
    for (const role of ['init', 'condition', 'update', 'body']) {
      expect(within(tree).getByRole('button', { name: new RegExp(`^${role}: `) })).toBeVisible()
    }
  })

  it('explains a truncated tree', () => {
    render(<AstView ast={null} truncated syntaxPassed onShowRange={vi.fn()} />)
    expect(screen.getByText(/too large to display/)).toBeVisible()
  })
})

describe('StageStatusBar', () => {
  it('shows every stage as not run before the first analysis', () => {
    render(<StageStatusBar status={null} />)
    expect(screen.getAllByText('not run')).toHaveLength(4)
  })

  it('shows a stage detail', () => {
    render(
      <StageStatusBar
        status={[
          { stage: 'lexical', status: 'passed', detail: null },
          { stage: 'syntax', status: 'failed', detail: 'Stopped after 20 syntax errors.' },
          { stage: 'semantic', status: 'skipped', detail: null },
          { stage: 'optimizer', status: 'skipped', detail: null },
        ]}
      />,
    )
    expect(screen.getByText('Stopped after 20 syntax errors.')).toBeVisible()
    expect(screen.getAllByText('skipped')).toHaveLength(2)
  })
})
