// Response types for POST /api/v1/analyze (SRS addendum §8.2).

export type Severity = 'error' | 'warning' | 'suggestion'
export type StageName = 'lexical' | 'syntax' | 'semantic' | 'optimizer'
export type StageState = 'passed' | 'failed' | 'skipped'

export interface StageStatus {
  stage: StageName
  status: StageState
  detail: string | null
}

export interface Diagnostic {
  rule_id: string
  severity: Severity
  stage: StageName
  message: string
  line: number
  column: number
  end_line: number | null
  end_column: number | null
  explanation: string
  fix_hint: string | null
}

export interface Statistics {
  variables: number
  functions: number
  errors: number
  warnings: number
  suggestions: number
  tokens: number
  lines: number
  duration_ms: number
}

export interface TokenInfo {
  type: string
  lexeme: string
  line: number
  column: number
}

export interface AstNode {
  type: string
  label: string
  role: string | null
  line: number
  column: number
  end_line: number
  end_column: number
  children: AstNode[]
}

export interface SymbolInfo {
  name: string
  kind: 'variable' | 'parameter' | 'function' | 'define'
  type: string
  line: number
  column: number
  reads: number
  writes: number
}

export interface ScopeInfo {
  id: number
  kind: 'file' | 'function' | 'block' | 'for'
  name: string | null
  line: number
  symbols: SymbolInfo[]
  children: ScopeInfo[]
}

export interface AnalysisReport {
  analysis_id: string
  status: StageStatus[]
  diagnostics: Diagnostic[]
  statistics: Statistics
  tokens: TokenInfo[]
  ast: AstNode | null
  symbols: ScopeInfo | null
  truncated: { tokens: boolean; ast: boolean }
}

/** The error envelope's body, plus codes the frontend raises itself. */
export interface ApiError {
  code: string
  message: string
  analysis_id: string | null
}

export type AnalyzeResult = { ok: true; report: AnalysisReport } | { ok: false; error: ApiError }

/** A source range to show in the editor (1-based, end column exclusive). */
export interface SourceRange {
  line: number
  column: number
  endLine: number
  endColumn: number
}
