import { describe, expect, it, vi } from 'vitest'
import { srsDemoReport } from '../test/fixtures'
import { analyze, checkHealth, fetchConfig } from './client'

function stubFetch(response: Response | Error) {
  const fetchStub = vi.fn((_url: string, _init?: RequestInit) =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  )
  vi.stubGlobal('fetch', fetchStub)
  return fetchStub
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('analyze', () => {
  it('posts the source, and the rules only when given', async () => {
    const fetchStub = stubFetch(json(srsDemoReport()))
    await analyze('int x;')
    await analyze('int x;', { 'SEM-SHADOW': false })
    const bodies = fetchStub.mock.calls.map(([, init]) => JSON.parse(String(init?.body)))
    expect(bodies).toEqual([
      { language: 'c', source: 'int x;' },
      { language: 'c', source: 'int x;', rules: { 'SEM-SHADOW': false } },
    ])
  })

  it('returns the report', async () => {
    stubFetch(json(srsDemoReport()))
    const result = await analyze('int x;')
    expect(result.ok && result.report.analysis_id).toBe('fixture-srs-demo')
  })

  it('returns the error envelope', async () => {
    stubFetch(json({ error: { code: 'INPUT_EMPTY', message: 'The source is empty.', analysis_id: 'id-1' } }, 400))
    expect(await analyze(' ')).toEqual({
      ok: false,
      error: { code: 'INPUT_EMPTY', message: 'The source is empty.', analysis_id: 'id-1' },
    })
  })

  it('handles an unexpected response', async () => {
    stubFetch(new Response('<html>Bad gateway</html>', { status: 502 }))
    const result = await analyze('int x;')
    expect(result).toEqual({
      ok: false,
      error: { code: 'UNEXPECTED_RESPONSE', message: 'The server answered with status 502.', analysis_id: null },
    })
  })

  it('handles a network failure', async () => {
    stubFetch(new TypeError('Failed to fetch'))
    const result = await analyze('int x;')
    expect(!result.ok && result.error.code).toBe('NETWORK_ERROR')
  })
})

describe('checkHealth', () => {
  it('is true only for {"status": "ok"}', async () => {
    stubFetch(json({ status: 'ok' }))
    expect(await checkHealth()).toBe(true)
    stubFetch(json({ status: 'starting' }))
    expect(await checkHealth()).toBe(false)
    stubFetch(new Response('', { status: 502 }))
    expect(await checkHealth()).toBe(false)
    stubFetch(new TypeError('offline'))
    expect(await checkHealth()).toBe(false)
  })
})

describe('fetchConfig', () => {
  it('returns the server limit', async () => {
    const fetchStub = stubFetch(json({ max_source_bytes: 200_000 }))
    expect(await fetchConfig()).toEqual({ max_source_bytes: 200_000 })
    expect(fetchStub.mock.calls[0][0]).toBe('http://localhost:8000/api/v1/config')
  })

  it.each([
    ['a missing field', json({})],
    ['a non-integer', json({ max_source_bytes: 1.5 })],
    ['zero', json({ max_source_bytes: 0 })],
    ['an error status', json({ detail: 'Not Found' }, 404)],
  ])('returns null for %s', async (_, response) => {
    stubFetch(response)
    expect(await fetchConfig()).toBeNull()
  })

  it('returns null when the server is unreachable', async () => {
    stubFetch(new TypeError('offline'))
    expect(await fetchConfig()).toBeNull()
  })
})
