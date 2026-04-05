"""
Pydantic models for VegaExchange API

Models are organized by domain:
- common.py  — APIResponse, PaginatedResponse (shared)
- enums.py   — EngineType, OrderSide, OrderStatus, etc. (shared)
- admin.py   — CreateSymbolRequest, CreatePoolRequest
- auth.py    — GoogleAuthRequest, EmailRegisterRequest, etc.
- market.py  — KLINE_INTERVALS
- orderbook.py — PlaceOrderRequest
- pool.py    — SwapRequest, AddLiquidityRequest, RemoveLiquidityRequest, symbol parsing
- user.py    — UserResponse, BalanceResponse
"""
