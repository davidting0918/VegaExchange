import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

export type ChartTimeRange = '1H' | '1D' | '1W' | '1M' | '1Y' | 'ALL'
export type SwapInputType = 'base' | 'quote'

const VALID_RANGES: ChartTimeRange[] = ['1H', '1D', '1W', '1M', '1Y', 'ALL']
const DEFAULT_RANGE: ChartTimeRange = '1D'
const DEFAULT_INPUT: SwapInputType = 'base'

function parseNumber(value: string | null, defaultVal: number): number {
  if (value == null) return defaultVal
  const n = parseInt(value, 10)
  return Number.isFinite(n) && n >= 1 ? n : defaultVal
}

function parseRange(value: string | null): ChartTimeRange {
  if (value && VALID_RANGES.includes(value as ChartTimeRange)) {
    return value as ChartTimeRange
  }
  return DEFAULT_RANGE
}

function parseInput(value: string | null): SwapInputType {
  if (value === 'base' || value === 'quote') return value
  return DEFAULT_INPUT
}

function parseFlipped(value: string | null): boolean {
  return value === 'true'
}

export function usePoolPageState() {
  const [searchParams, setSearchParams] = useSearchParams()

  const page = useMemo(
    () => parseNumber(searchParams.get('page'), 1),
    [searchParams]
  )
  const range = useMemo(
    () => parseRange(searchParams.get('range')),
    [searchParams]
  )
  const input = useMemo(
    () => parseInput(searchParams.get('input')),
    [searchParams]
  )
  const flipped = useMemo(
    () => parseFlipped(searchParams.get('flipped')),
    [searchParams]
  )

  const setPage = useCallback(
    (p: number) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (p <= 1) next.delete('page')
          else next.set('page', String(p))
          return next
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  const setRange = useCallback(
    (r: ChartTimeRange) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (r === DEFAULT_RANGE) next.delete('range')
          else next.set('range', r)
          return next
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  const setInput = useCallback(
    (i: SwapInputType) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (i === DEFAULT_INPUT) next.delete('input')
          else next.set('input', i)
          return next
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  const setFlipped = useCallback(
    (f: boolean) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (!f) next.delete('flipped')
          else next.set('flipped', 'true')
          return next
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  /** Updates both flipped and input in one call to avoid race where two setSearchParams overwrite each other. */
  const setSwapDirection = useCallback(
    (f: boolean, i: SwapInputType) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (!f) next.delete('flipped')
          else next.set('flipped', 'true')
          if (i === DEFAULT_INPUT) next.delete('input')
          else next.set('input', i)
          return next
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  return {
    page,
    range,
    input,
    flipped,
    setPage,
    setRange,
    setInput,
    setFlipped,
    setSwapDirection,
  }
}
