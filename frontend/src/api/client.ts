import type { AnalysisReport, AnalyzeResult, ApiError } from './types'

const DEFAULT_API_URL = 'http://localhost:8000'

export const API_BASE_URL = (import.meta.env.VITE_API_URL || DEFAULT_API_URL).replace(/\/+$/, '')

/** A cold free-tier server can take about a minute to answer. */
export const HEALTH_TIMEOUT_MS = 90_000

/** Returns true when GET /api/v1/health answers {"status": "ok"}. */
export async function checkHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/health`, { signal })
    if (!response.ok) return false
    const body: unknown = await response.json()
    return isObject(body) && body.status === 'ok'
  } catch {
    return false
  }
}

/** POST the source to /api/v1/analyze. Never throws. */
export async function analyze(
  source: string,
  rules?: Record<string, boolean>,
  signal?: AbortSignal,
): Promise<AnalyzeResult> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rules ? { language: 'c', source, rules } : { language: 'c', source }),
      signal,
    })
  } catch {
    return failure(
      'NETWORK_ERROR',
      'Could not reach the CodeGuard server. Check your connection and try again.',
    )
  }
  const body: unknown = await response.json().catch(() => null)
  if (response.ok && isReport(body)) return { ok: true, report: body }
  if (isObject(body) && isApiError(body.error)) return { ok: false, error: body.error }
  return failure('UNEXPECTED_RESPONSE', `The server answered with status ${response.status}.`)
}

export function failure(code: string, message: string): AnalyzeResult & { ok: false } {
  return { ok: false, error: { code, message, analysis_id: null } }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isApiError(value: unknown): value is ApiError {
  return isObject(value) && typeof value.code === 'string' && typeof value.message === 'string'
}

function isReport(value: unknown): value is AnalysisReport {
  return (
    isObject(value) &&
    Array.isArray(value.status) &&
    Array.isArray(value.diagnostics) &&
    Array.isArray(value.tokens) &&
    isObject(value.statistics)
  )
}
