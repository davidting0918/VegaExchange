# Senior Frontend Engineer — Domain Knowledge

Deep technical knowledge for building trading platform UIs.
Covers component patterns, real-time data handling, chart integration,
and exchange-specific UI/UX patterns.

---

## 1. Trading UI Layout Patterns

### Standard Exchange Layout (Desktop)

```
┌──────────────────────────────────────────────────────────────┐
│  Header: Logo | Markets | Trade | Pools | Dashboard | User  │
├────────────────────────────────┬─────────────────────────────┤
│                                │  Trade Panel               │
│  Chart Area                    │  ┌─────────────────────┐   │
│  (Candlestick / Price Line)    │  │ Buy/Sell Tabs        │   │
│                                │  │ Order Type Selector   │   │
│                                │  │ Price Input           │   │
│                                │  │ Quantity Input        │   │
│                                │  │ Leverage Slider (perp)│   │
│                                │  │ Total / Margin        │   │
│                                │  │ [Place Order] Button  │   │
│                                │  └─────────────────────┘   │
├─────────────────┬──────────────┤                             │
│  Order Book     │  Recent      │  Position Panel (perp)     │
│  Bid | Ask      │  Trades      │  Open orders / Positions   │
│                 │              │                             │
└─────────────────┴──────────────┴─────────────────────────────┘
│  Bottom Panel: Open Orders | Trade History | Positions       │
└──────────────────────────────────────────────────────────────┘
```

### AMM Swap Layout (Simpler)

```
┌──────────────────────────────────────────────────────────┐
│  Header                                                  │
├────────────────────────────────┬─────────────────────────┤
│  Chart + Pool Stats            │  Swap Panel             │
│                                │  ┌───────────────────┐  │
│  Price History                 │  │ From: [Token] [Amt]│  │
│  Volume Chart                  │  │      ↕ (flip)      │  │
│  Pool Composition              │  │ To:   [Token] [Amt]│  │
│                                │  │                    │  │
│                                │  │ Rate: 1 X = N Y    │  │
│                                │  │ Impact: 0.12%      │  │
│                                │  │ Fee: 0.3%          │  │
│                                │  │ [Swap] Button      │  │
│                                │  └───────────────────┘  │
│                                │                         │
│                                │  Liquidity Panel        │
│                                │  [Add] [Remove] Tabs    │
├────────────────────────────────┴─────────────────────────┤
│  Recent Trades | LP Position                             │
└──────────────────────────────────────────────────────────┘
```

### Perpetual Trading Layout

```
┌──────────────────────────────────────────────────────────────┐
│  Header + Funding Rate Countdown + Mark Price + Index Price  │
├────────────────────────────────┬─────────────────────────────┤
│  Chart Area                    │  Order Panel               │
│  (Candlestick)                 │  ┌─────────────────────┐   │
│                                │  │ Long / Short Tabs    │   │
│                                │  │ Margin Mode Toggle   │   │
│                                │  │ Leverage: [1x-100x]  │   │
│                                │  │ Order Type Selector   │   │
│                                │  │ Price / Quantity      │   │
│                                │  │ TP/SL (optional)      │   │
│                                │  │ Cost & Fee Preview    │   │
│                                │  │ [Open Long/Short]    │   │
│                                │  └─────────────────────┘   │
├─────────────────┬──────────────┤                             │
│  Order Book     │  Trades      │  Account Info              │
│                 │              │  Available Margin           │
│                 │              │  Margin Ratio               │
└─────────────────┴──────────────┴─────────────────────────────┘
│  Positions | Open Orders | Order History | Funding History    │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Order Book UI Implementation

### Bid/Ask Display
```typescript
interface OrderBookLevel {
  price: string        // Display as formatted number
  quantity: string     // Aggregate quantity at this level
  total: string        // Cumulative total
  percentage: number   // Bar width (% of max quantity)
}

// Render pattern:
// Asks (sells) — sorted price descending (highest at top)
// ─── Spread ───
// Bids (buys) — sorted price descending (highest at top)
```

### Visual Depth Bars
```tsx
// Background bar showing relative depth
<div className="relative">
  <div
    className="absolute inset-y-0 right-0 bg-green-500/10"
    style={{ width: `${level.percentage}%` }}
  />
  <div className="relative flex justify-between px-2">
    <span className="text-green-400">{level.price}</span>
    <span>{level.quantity}</span>
    <span className="text-secondary">{level.total}</span>
  </div>
</div>
```

### Grouping / Tick Size
- Allow users to change price grouping (e.g., 0.01, 0.1, 1, 10)
- Aggregate quantities within each tick group
- Common in Binance, dYdX, Bybit

---

## 3. Chart Integration Patterns

### TradingView Lightweight Charts

#### Candlestick Setup
```typescript
import { createChart, CandlestickSeries } from 'lightweight-charts'

const chart = createChart(container, {
  layout: {
    background: { color: '#0D1117' },
    textColor: '#8B949E',
  },
  grid: {
    vertLines: { color: '#21262D' },
    horzLines: { color: '#21262D' },
  },
  crosshair: { mode: CrosshairMode.Normal },
  rightPriceScale: { borderColor: '#30363D' },
  timeScale: { borderColor: '#30363D' },
})

const series = chart.addSeries(CandlestickSeries, {
  upColor: '#3FB950',
  downColor: '#F85149',
  borderUpColor: '#3FB950',
  borderDownColor: '#F85149',
  wickUpColor: '#3FB950',
  wickDownColor: '#F85149',
})
```

#### Real-Time Update Pattern
```typescript
// Current: fetch full dataset on interval
// Future: append new candle via WebSocket

// Append or update last candle
series.update({
  time: timestamp,
  open, high, low, close,
})
```

#### Responsive Resize
```typescript
useEffect(() => {
  const observer = new ResizeObserver(() => {
    chart.applyOptions({
      width: container.clientWidth,
      height: container.clientHeight,
    })
  })
  observer.observe(container)
  return () => observer.disconnect()
}, [])
```

### Recharts for Statistics
```typescript
// Volume bar chart with custom colors
<BarChart data={volumeData}>
  <Bar dataKey="volume" fill="#58A6FF">
    {volumeData.map((entry, i) => (
      <Cell key={i} fill={entry.isUp ? '#3FB950' : '#F85149'} />
    ))}
  </Bar>
</BarChart>
```

---

## 4. Real-Time Data Patterns

### Polling (Current)
```typescript
const { data } = useQuery({
  queryKey: ['orderbook', symbol],
  queryFn: () => MarketService.getOrderBook(symbol),
  refetchInterval: 2_000,    // 2 seconds
  staleTime: 1_000,          // Consider stale after 1s
  refetchIntervalInBackground: false,  // Stop when tab inactive
})
```

### Optimistic Updates
```typescript
const swapMutation = useMutation({
  mutationFn: TradeService.swap,
  onMutate: async (request) => {
    // Cancel outgoing refetches
    await queryClient.cancelQueries({ queryKey: ['balances'] })

    // Snapshot previous state
    const previous = queryClient.getQueryData(['balances'])

    // Optimistically update
    queryClient.setQueryData(['balances'], (old) => {
      // Deduct input amount, add output amount
      return optimisticUpdate(old, request)
    })

    return { previous }
  },
  onError: (err, req, context) => {
    // Rollback on error
    queryClient.setQueryData(['balances'], context.previous)
  },
  onSettled: () => {
    // Always refetch to sync with server
    queryClient.invalidateQueries({ queryKey: ['balances'] })
    queryClient.invalidateQueries({ queryKey: ['pool'] })
  },
})
```

### Debounced Queries (Quote Fetching)
```typescript
const [debouncedAmount] = useDebounce(inputAmount, 300)

const { data: quote } = useQuery({
  queryKey: ['quote', symbol, side, debouncedAmount],
  queryFn: () => TradeService.getQuote({ symbol, side, quantity: debouncedAmount }),
  enabled: !!debouncedAmount && parseFloat(debouncedAmount) > 0,
  staleTime: 5_000,
})
```

---

## 5. Form Patterns for Trading

### Numeric Input with Validation
```typescript
function NumericInput({ value, onChange, decimals = 8, max }) {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value
    // Allow empty, digits, single dot, limited decimals
    if (/^\d*\.?\d{0,${decimals}}$/.test(raw)) {
      onChange(raw)
    }
  }

  return (
    <input
      type="text"          // NOT type="number" — numeric inputs cause UX issues
      inputMode="decimal"  // Shows numeric keyboard on mobile
      value={value}
      onChange={handleChange}
    />
  )
}
```

### Max/Percentage Buttons
```tsx
// Common pattern: 25% / 50% / 75% / Max buttons
<div className="flex gap-1">
  {[25, 50, 75, 100].map(pct => (
    <button
      key={pct}
      onClick={() => setAmount(balance.times(pct / 100).toFixed(decimals))}
      className="px-2 py-1 text-xs bg-tertiary rounded hover:bg-border-default"
    >
      {pct === 100 ? 'Max' : `${pct}%`}
    </button>
  ))}
</div>
```

### Leverage Slider (Perpetual)
```tsx
// Discrete steps: 1x, 2x, 3x, 5x, 10x, 20x, 50x, 100x
const LEVERAGE_STEPS = [1, 2, 3, 5, 10, 20, 50, 100]

<input
  type="range"
  min={0}
  max={LEVERAGE_STEPS.length - 1}
  value={LEVERAGE_STEPS.indexOf(leverage)}
  onChange={(e) => setLeverage(LEVERAGE_STEPS[e.target.value])}
/>
```

---

## 6. Number Formatting for Trading UIs

### Display Rules
| Data Type | Format | Example |
|-----------|--------|---------|
| USD value | 2 decimals, comma separator | $1,234,567.89 |
| BTC price | 2 decimals | 50,000.00 |
| BTC quantity | up to 8 decimals, trim zeros | 0.00123 |
| Percentage | 2 decimals + % | 12.34% |
| Price impact | colored, 2 decimals | -0.12% (red) |
| PnL | colored, 2 decimals + sign | +$1,234.56 (green) |
| Funding rate | 4 decimals + % | 0.0100% |
| Leverage | integer + x | 10x |

### Color Coding
```typescript
function getPnlColor(value: number): string {
  if (value > 0) return 'text-green-400'  // accent-green
  if (value < 0) return 'text-red-400'    // accent-red
  return 'text-secondary'
}
```

### Smart Decimal Display
```typescript
// Show significant digits, not fixed decimals
function formatCryptoAmount(value: BigNumber): string {
  if (value.gte(1000)) return value.toFixed(2)
  if (value.gte(1)) return value.toFixed(4)
  if (value.gte(0.01)) return value.toFixed(6)
  return value.toFixed(8)
}
```

---

## 7. Loading & Error States

### Skeleton Loading
```tsx
function OrderBookSkeleton() {
  return (
    <div className="space-y-1">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="h-6 bg-tertiary animate-pulse rounded" />
      ))}
    </div>
  )
}
```

### Error Boundary Pattern
```tsx
function TradingErrorFallback({ error, resetErrorBoundary }) {
  return (
    <div className="flex flex-col items-center justify-center p-8">
      <p className="text-red-400 mb-4">Failed to load trading data</p>
      <Button variant="secondary" onClick={resetErrorBoundary}>
        Retry
      </Button>
    </div>
  )
}
```

### Toast Notifications for Trade Actions
```typescript
// Success: swap completed
toast.success(`Swapped ${inputAmount} ${inputToken} for ${outputAmount} ${outputToken}`)

// Error: insufficient balance
toast.error(`Insufficient ${token} balance`)

// Info: order placed
toast.info(`Limit order placed: Buy ${quantity} ${base} @ ${price}`)
```

---

## 8. Perpetual-Specific UI Components

### Position Row
```tsx
interface PositionDisplayProps {
  symbol: string
  side: 'LONG' | 'SHORT'
  entryPrice: BigNumber
  markPrice: BigNumber
  quantity: BigNumber
  leverage: number
  margin: BigNumber
  unrealizedPnl: BigNumber
  roe: BigNumber             // Return on equity
  liquidationPrice: BigNumber
}
```

### Funding Rate Display
```tsx
// Show countdown to next funding + current rate
function FundingRateBar({ rate, nextFundingTime }) {
  const isPositive = rate > 0
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-secondary">Funding:</span>
      <span className={isPositive ? 'text-green-400' : 'text-red-400'}>
        {formatPercentage(rate, 4)}
      </span>
      <span className="text-tertiary">|</span>
      <span className="text-secondary">Next: {formatCountdown(nextFundingTime)}</span>
    </div>
  )
}
```

### Margin Mode Toggle
```tsx
// Cross vs Isolated margin selector
<Tabs value={marginMode} onValueChange={setMarginMode}>
  <TabsList>
    <TabsTrigger value="cross">Cross</TabsTrigger>
    <TabsTrigger value="isolated">Isolated</TabsTrigger>
  </TabsList>
</Tabs>
```

### TP/SL (Take Profit / Stop Loss) Input
```tsx
<div className="space-y-2">
  <label className="flex items-center gap-2">
    <Checkbox checked={tpEnabled} onCheckedChange={setTpEnabled} />
    <span>Take Profit</span>
  </label>
  {tpEnabled && (
    <NumericInput
      value={tpPrice}
      onChange={setTpPrice}
      placeholder="TP Price"
    />
  )}
</div>
```

---

## 9. Performance Optimization

### Code Splitting
```typescript
// Lazy load trading pages (heavy chart dependencies)
const SpotTradingPage = lazy(() => import('./components/trading/spot/SpotTradingPage'))
const AmmTradingPage = lazy(() => import('./components/trading/amm/AmmTradingPage'))
const PerpTradingPage = lazy(() => import('./components/trading/perp/PerpTradingPage'))
```

### Memoization for Order Book
```typescript
// Order book re-renders frequently — memoize row components
const OrderBookRow = memo(function OrderBookRow({ level }: { level: OrderBookLevel }) {
  return (/* ... */)
})

// Memoize sorted/grouped data
const groupedBook = useMemo(
  () => groupOrderBook(rawBook, tickSize),
  [rawBook, tickSize]
)
```

### Virtual Scrolling for Trade History
```typescript
// For large trade lists, use virtualization
import { useVirtualizer } from '@tanstack/react-virtual'

const virtualizer = useVirtualizer({
  count: trades.length,
  getScrollElement: () => scrollRef.current,
  estimateSize: () => 32, // row height
})
```

---

## 10. Accessibility (A11Y) Essentials

### Keyboard Navigation
- Tab order follows visual layout
- Enter/Space activates buttons and controls
- Escape closes modals and dropdowns
- Arrow keys navigate order book levels

### ARIA Labels
```tsx
<button aria-label={`Buy ${base} at market price`}>
  Market Buy
</button>

<div role="table" aria-label="Order book">
  <div role="row">
    <span role="cell">Price</span>
    <span role="cell">Quantity</span>
  </div>
</div>
```

### Color Contrast
- All text meets WCAG AA contrast ratio (4.5:1 for normal text)
- Don't rely on color alone — add icons or text for buy/sell, profit/loss
- shadcn/ui components have built-in accessibility via Radix primitives

---

## 11. Exchange UI Reference (Industry Patterns)

### Binance
- Dark theme with yellow accent
- Complex but information-dense layout
- TradingView charting (full integration)
- Cross-margin toggle in header
- Fee tier display in order form

### dYdX (v4)
- Clean, minimal UI
- Order book with depth visualization
- Position panel always visible
- Funding rate countdown in header
- One-click close position

### Uniswap
- Ultra-simple swap interface
- Token selector with search + favorites
- Price impact warning (yellow/red thresholds)
- Settings gear: slippage tolerance, deadline
- Transaction pending/success/failure states

### GMX
- Pool-based perpetual UI
- Available liquidity display
- Leverage slider with position preview
- Real-time PnL on open positions
