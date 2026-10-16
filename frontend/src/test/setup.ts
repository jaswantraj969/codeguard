import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { shownRanges } from './editorSpy'

// Monaco needs a real browser; every test uses the textarea double instead.
vi.mock('../components/CodeEditor', () => import('./MockCodeEditor'))

afterEach(() => {
  cleanup()
  shownRanges.length = 0
  vi.unstubAllGlobals()
  vi.useRealTimers()
})
