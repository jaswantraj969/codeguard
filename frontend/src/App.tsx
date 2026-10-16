import { useEffect, useState } from 'react'
import { checkHealth } from './api/client'

type ServerState = 'checking' | 'online' | 'offline'

const STATE_LABEL: Record<ServerState, string> = {
  checking: 'Checking server…',
  online: 'Server online',
  offline: 'Server unavailable',
}

function App() {
  const [server, setServer] = useState<ServerState>('checking')

  useEffect(() => {
    const controller = new AbortController()
    checkHealth(controller.signal).then((ok) => {
      if (!controller.signal.aborted) setServer(ok ? 'online' : 'offline')
    })
    return () => controller.abort()
  }, [])

  return (
    <main>
      <h1>CodeGuard</h1>
      <p>A mini static analyzer for a subset of C.</p>
      <p role="status" aria-live="polite">
        {STATE_LABEL[server]}
      </p>
    </main>
  )
}

export default App
