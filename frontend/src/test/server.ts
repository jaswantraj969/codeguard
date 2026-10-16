// A fake fetch for the two API routes, so tests control every response.
import { vi } from 'vitest'
import type { AnalysisReport } from '../api/types'

export interface FakeServer {
  analyzeBodies: unknown[]
  health: 'ok' | 'down' | 'hang'
}

type AnalyzeReply = AnalysisReport | { httpStatus: number; body: unknown } | 'network-error'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** Install a fetch stub. `reply` decides the answer to each analyze request. */
export function fakeServer(
  reply: (source: string) => AnalyzeReply,
  options: { health?: FakeServer['health'] } = {},
): FakeServer {
  const server: FakeServer = { analyzeBodies: [], health: options.health ?? 'ok' }
  const fetchStub = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/api/v1/health')) {
      if (server.health === 'hang') {
        return new Promise<Response>((_, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
        })
      }
      if (server.health === 'down') throw new TypeError('Failed to fetch')
      return json({ status: 'ok' })
    }
    if (url.endsWith('/api/v1/analyze')) {
      const body = JSON.parse(String(init?.body))
      server.analyzeBodies.push(body)
      const answer = reply(body.source)
      if (answer === 'network-error') throw new TypeError('Failed to fetch')
      if ('httpStatus' in answer) return json(answer.body, answer.httpStatus)
      return json(answer)
    }
    return json({ detail: 'Not Found' }, 404)
  })
  vi.stubGlobal('fetch', fetchStub)
  return server
}
