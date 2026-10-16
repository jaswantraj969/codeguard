import { useState } from 'react'
import type { AstNode, SourceRange } from '../api/types'

/** Levels expanded when the tree first appears. */
const INITIAL_EXPANDED_DEPTH = 2

interface AstViewProps {
  ast: AstNode | null
  truncated: boolean
  syntaxPassed: boolean
  onShowRange(range: SourceRange): void
}

function AstTreeNode({
  node,
  depth,
  onShowRange,
}: {
  node: AstNode
  depth: number
  onShowRange(range: SourceRange): void
}) {
  const [expanded, setExpanded] = useState(depth < INITIAL_EXPANDED_DEPTH)
  const hasChildren = node.children.length > 0
  return (
    <li className="ast-node">
      <div className="ast-row">
        {hasChildren ? (
          <button
            type="button"
            className="ast-toggle"
            aria-expanded={expanded}
            aria-label={`${expanded ? 'Collapse' : 'Expand'} ${node.label}`}
            onClick={() => setExpanded(!expanded)}
          >
            <span aria-hidden="true">{expanded ? '▾' : '▸'}</span>
          </button>
        ) : (
          <span className="ast-leaf" aria-hidden="true">
            •
          </span>
        )}
        <button
          type="button"
          className="ast-label"
          aria-label={`${node.role ? `${node.role}: ` : ''}${node.label}, line ${node.line}, column ${node.column}`}
          onClick={() =>
            onShowRange({
              line: node.line,
              column: node.column,
              endLine: node.end_line,
              endColumn: node.end_column,
            })
          }
        >
          {node.role && <span className="ast-role">{node.role}: </span>}
          {node.label}
          <span className="ast-location">
            {' '}
            (line {node.line}, column {node.column})
          </span>
        </button>
      </div>
      {hasChildren && expanded && (
        <ul className="ast-children">
          {node.children.map((child, index) => (
            <AstTreeNode key={index} node={child} depth={depth + 1} onShowRange={onShowRange} />
          ))}
        </ul>
      )}
    </li>
  )
}

/** The parser's abstract syntax tree as a collapsible tree. */
export default function AstView({ ast, truncated, syntaxPassed, onShowRange }: AstViewProps) {
  if (ast === null) {
    if (truncated) {
      return (
        <p className="note">
          The syntax tree is too large to display (more than 20,000 nodes or 400 levels deep).
        </p>
      )
    }
    return (
      <p className="empty">
        {syntaxPassed ? 'No syntax tree.' : 'No syntax tree: fix the lexical and syntax errors first.'}
      </p>
    )
  }
  return (
    <div className="ast-view">
      <p className="note">Select a node to highlight its code in the editor.</p>
      <ul className="ast-tree" aria-label="Abstract syntax tree">
        <AstTreeNode node={ast} depth={0} onShowRange={onShowRange} />
      </ul>
    </div>
  )
}
