import { useCallback, useEffect, useState } from 'react'
import { HEALTH_TIMEOUT_MS, checkHealth } from '../api/client'

export type ServerState = 'checking' | 'waking' | 'online' | 'offline'

/** After this long without an answer, tell the user the server is waking up. */
export const WAKE_MESSAGE_DELAY_MS = 2_000

/**
 * Pings /health on load. A sleeping free-tier server can take about a minute to
 * start, so a slow answer shows a wake-up message instead of an error.
 */
export function useServerStatus(): { state: ServerState; retry(): void } {
  const [state, setState] = useState<ServerState>('checking')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false // set when this attempt is replaced or the page unmounts
    const controller = new AbortController()
    const wakeTimer = setTimeout(
      () => setState((current) => (current === 'checking' ? 'waking' : current)),
      WAKE_MESSAGE_DELAY_MS,
    )
    const giveUpTimer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS)
    checkHealth(controller.signal).then((ok) => {
      if (cancelled) return
      clearTimeout(wakeTimer)
      clearTimeout(giveUpTimer)
      setState(ok ? 'online' : 'offline')
    })
    return () => {
      cancelled = true
      clearTimeout(wakeTimer)
      clearTimeout(giveUpTimer)
      controller.abort()
    }
  }, [attempt])

  const retry = useCallback(() => {
    setState('checking')
    setAttempt((n) => n + 1)
  }, [])

  return { state, retry }
}
