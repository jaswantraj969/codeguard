import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

function mockFetch(response: Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn(() => response))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('shows the server as online when /health answers ok', async () => {
    mockFetch(Promise.resolve(new Response(JSON.stringify({ status: 'ok' }), { status: 200 })))

    render(<App />)

    expect(await screen.findByText('Server online')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/v1/health', expect.anything())
  })

  it('shows the server as unavailable when the request fails', async () => {
    mockFetch(Promise.reject(new TypeError('network down')))

    render(<App />)

    expect(await screen.findByText('Server unavailable')).toBeInTheDocument()
  })

  it('shows the server as unavailable on a non-ok status', async () => {
    mockFetch(Promise.resolve(new Response('', { status: 502 })))

    render(<App />)

    expect(await screen.findByText('Server unavailable')).toBeInTheDocument()
  })
})
