import { describe, expect, it } from 'vitest'
import { EXAMPLES, SRS_DEMO } from './examples'
import { formatBytes, isCFileName, utf8ByteLength } from './limits'

describe('limits', () => {
  it('counts UTF-8 bytes, not characters', () => {
    expect(utf8ByteLength('abc')).toBe(3)
    expect(utf8ByteLength('é')).toBe(2)
    expect(utf8ByteLength('💡')).toBe(4)
  })

  it('formats byte counts', () => {
    expect(formatBytes(512_001)).toBe('512,001 bytes')
  })

  it.each([
    ['main.c', true],
    ['MAIN.C', true],
    ['a.b.c', true],
    ['main.cpp', false],
    ['main.h', false],
    ['notes.txt', false],
    ['c', false],
    ['main.c.txt', false],
  ])('isCFileName(%s) is %s', (name, expected) => {
    expect(isCFileName(name)).toBe(expected)
  })
})

describe('examples', () => {
  it('includes the SRS demo first', () => {
    expect(EXAMPLES[0]).toBe(SRS_DEMO)
    expect(new Set(EXAMPLES.map((e) => e.id)).size).toBe(EXAMPLES.length)
  })
})
