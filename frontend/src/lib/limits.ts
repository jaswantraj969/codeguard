// The size limit itself comes from the API (GET /api/v1/config), so the browser
// and the server always agree; it is configurable on the server (MAX_SOURCE_BYTES).

/** Size as the API measures it: bytes of UTF-8, not characters. */
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
