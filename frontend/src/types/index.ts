export * from './auth'
export * from './user'
export * from './trading'

// Common API Response Type
export interface ApiResponse<T> {
  success: boolean
  data: T
  message?: string
}

// Pagination
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}
