import React, { useState, useRef, useEffect } from 'react'
import clsx from 'clsx'
import type { Symbol } from '../../types'

interface TokenSelectorProps {
  symbols: Symbol[]
  selectedSymbol: string | null
  onSelect: (symbol: string) => void
  disabled?: boolean
}

export const TokenSelector: React.FC<TokenSelectorProps> = ({
  symbols,
  selectedSymbol,
  onSelect,
  disabled = false,
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setSearchTerm('')
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Focus input when dropdown opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isOpen])

  const selectedSymbolData = symbols.find((s) => s.symbol === selectedSymbol)

  const filteredSymbols = symbols.filter(
    (s) =>
      s.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.base.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.quote.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleSelect = (symbol: string) => {
    onSelect(symbol)
    setIsOpen(false)
    setSearchTerm('')
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={clsx(
          'w-full flex items-center justify-between px-4 py-3 rounded-lg border transition-colors',
          'bg-bg-tertiary border-border-default',
          disabled
            ? 'cursor-not-allowed opacity-50'
            : 'hover:border-border-hover cursor-pointer',
          isOpen && 'border-accent-blue ring-1 ring-accent-blue'
        )}
      >
        <div className="flex items-center gap-3">
          {selectedSymbolData ? (
            <>
              <div className="flex items-center">
                <span className="font-semibold text-text-primary">
                  {selectedSymbolData.base}
                </span>
                <span className="text-text-tertiary mx-1">/</span>
                <span className="text-text-secondary">{selectedSymbolData.quote}</span>
              </div>
            </>
          ) : (
            <span className="text-text-tertiary">Select a trading pair</span>
          )}
        </div>
        <svg
          className={clsx(
            'w-5 h-5 text-text-tertiary transition-transform',
            isOpen && 'rotate-180'
          )}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-2 bg-bg-secondary border border-border-default rounded-lg shadow-card animate-fade-in">
          {/* Search Input */}
          <div className="p-3 border-b border-border-default">
            <input
              ref={inputRef}
              type="text"
              placeholder="Search pairs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-2 bg-bg-tertiary border border-border-default rounded-lg text-text-primary placeholder-text-tertiary text-sm focus:outline-none focus:border-accent-blue"
            />
          </div>

          {/* Options */}
          <div className="max-h-64 overflow-y-auto">
            {filteredSymbols.length > 0 ? (
              filteredSymbols.map((symbol) => (
                <button
                  key={symbol.symbol}
                  type="button"
                  onClick={() => handleSelect(symbol.symbol)}
                  className={clsx(
                    'w-full flex items-center justify-between px-4 py-3 hover:bg-bg-tertiary transition-colors',
                    symbol.symbol === selectedSymbol && 'bg-accent-blue/10'
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-accent-blue/20 flex items-center justify-center">
                      <span className="text-xs font-medium text-accent-blue">
                        {symbol.base.charAt(0)}
                      </span>
                    </div>
                    <div className="text-left">
                      <div className="flex items-center">
                        <span className="font-medium text-text-primary">{symbol.base}</span>
                        <span className="text-text-tertiary mx-1">/</span>
                        <span className="text-text-secondary">{symbol.quote}</span>
                      </div>
                      <span className="text-xs text-text-tertiary">{symbol.symbol}</span>
                    </div>
                  </div>
                  {symbol.symbol === selectedSymbol && (
                    <svg className="w-5 h-5 text-accent-blue" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </button>
              ))
            ) : (
              <div className="px-4 py-8 text-center text-text-tertiary">
                No trading pairs found
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
