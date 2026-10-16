import type { ScopeInfo } from '../api/types'

function scopeTitle(scope: ScopeInfo): string {
  switch (scope.kind) {
    case 'file':
      return 'File scope'
    case 'function':
      return `Function ${scope.name ?? ''} (line ${scope.line})`
    case 'for':
      return `for loop (line ${scope.line})`
    default:
      return `Block (line ${scope.line})`
  }
}

function ScopeSection({ scope, level }: { scope: ScopeInfo; level: number }) {
  const Heading = level === 0 ? 'h4' : 'h5'
  return (
    <section className="scope" aria-label={scopeTitle(scope)}>
      <Heading className="scope-title">{scopeTitle(scope)}</Heading>
      {scope.symbols.length === 0 ? (
        <p className="empty">No symbols declared here.</p>
      ) : (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Kind</th>
                <th scope="col">Type</th>
                <th scope="col">Line</th>
                <th scope="col">Reads</th>
                <th scope="col">Writes</th>
              </tr>
            </thead>
            <tbody>
              {scope.symbols.map((symbol) => (
                <tr key={`${symbol.name}-${symbol.line}-${symbol.column}`}>
                  <th scope="row">
                    <code>{symbol.name}</code>
                  </th>
                  <td>{symbol.kind}</td>
                  <td>
                    <code>{symbol.type}</code>
                  </td>
                  <td>{symbol.line}</td>
                  <td>{symbol.reads}</td>
                  <td>{symbol.writes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {scope.children.length > 0 && (
        <div className="scope-children">
          {scope.children.map((child) => (
            <ScopeSection key={child.id} scope={child} level={level + 1} />
          ))}
        </div>
      )}
    </section>
  )
}

/** The symbol table, grouped by scope and nested like the program. */
export default function SymbolView({ symbols }: { symbols: ScopeInfo | null }) {
  if (symbols === null) {
    return <p className="empty">No symbol table: the semantic stage did not run.</p>
  }
  return (
    <div className="symbol-view">
      <ScopeSection scope={symbols} level={0} />
    </div>
  )
}
