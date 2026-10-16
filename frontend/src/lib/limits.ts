/** Same limit as the API (SRS addendum §7): bytes of UTF-8, not characters. */
export const MAX_SOURCE_BYTES = 512_000

export function utf8ByteLength(text: string): number {
  return new TextEncoder().encode(text).length
}

export function formatBytes(bytes: number): string {
  return `${bytes.toLocaleString('en-US')} bytes`
}

/** True for file names ending in .c (any case). */
export function isCFileName(name: string): boolean {
  return /\.c$/i.test(name)
}
