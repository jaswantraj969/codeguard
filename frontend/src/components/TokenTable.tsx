import { useState } from 'react'
import type { TokenInfo } from '../api/types'

export const TOKEN_PAGE_SIZE = 200

interface TokenTableProps {
  tokens: TokenInfo[]
  total: number
  truncated: boolean
}

/** The lexer's output. Rows are added a page at a time to keep the page responsive. */
export default function TokenTable({ tokens, total, truncated }: TokenTableProps) {
  const [shown, setShown] = useState(TOKEN_PAGE_SIZE)
  if (tokens.length === 0) return <p className="empty">No tokens.</p>
  const visible = tokens.slice(0, shown)
  return (
    <div className="token-view">
      {truncated && (
        <p className="note" role="note">
          Showing the first {tokens.length.toLocaleString('en-US')} of {total.toLocaleString('en-US')} tokens.
        </p>
      )}
      <div className="table-scroll">
        <table className="data-table">
          <caption className="visually-hidden">Tokens produced by the lexer</caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Type</th>
              <th scope="col">Lexeme</th>
              <th scope="col">Line</th>
              <th scope="col">Column</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((token, index) => (
              <tr key={index}>
                <td>{index + 1}</td>
                <td>{token.type}</td>
                <td>
                  <code>{token.lexeme}</code>
                </td>
                <td>{token.line}</td>
                <td>{token.column}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {shown < tokens.length && (
        <button type="button" className="secondary" onClick={() => setShown(shown + TOKEN_PAGE_SIZE)}>
          Show {Math.min(TOKEN_PAGE_SIZE, tokens.length - shown)} more tokens
        </button>
      )}
    </div>
  )
}
