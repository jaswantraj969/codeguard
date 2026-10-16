const DEFAULT_API_URL = 'http://localhost:8000'

export const API_BASE_URL = (import.meta.env.VITE_API_URL || DEFAULT_API_URL).replace(/\/+$/, '')

/** Returns true when GET /api/v1/health answers {"status": "ok"}. */
export async function checkHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/health`, { signal })
    if (!response.ok) return false
    const body: unknown = await response.json()
    return typeof body === 'object' && body !== null && (body as { status?: unknown }).status === 'ok'
  } catch {
    return false
  }
}
