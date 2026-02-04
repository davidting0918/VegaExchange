/**
 * Validate email format
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}

/**
 * Validate password strength
 * - At least 8 characters
 * - Contains uppercase, lowercase, and number
 */
export function isValidPassword(password: string): boolean {
  if (password.length < 8) return false
  const hasUppercase = /[A-Z]/.test(password)
  const hasLowercase = /[a-z]/.test(password)
  const hasNumber = /\d/.test(password)
  return hasUppercase && hasLowercase && hasNumber
}

/**
 * Get password strength feedback
 */
export function getPasswordStrength(password: string): {
  strength: 'weak' | 'medium' | 'strong'
  message: string
} {
  if (password.length < 8) {
    return { strength: 'weak', message: 'Password must be at least 8 characters' }
  }

  const hasUppercase = /[A-Z]/.test(password)
  const hasLowercase = /[a-z]/.test(password)
  const hasNumber = /\d/.test(password)
  const hasSpecial = /[!@#$%^&*(),.?":{}|<>]/.test(password)

  const criteria = [hasUppercase, hasLowercase, hasNumber, hasSpecial].filter(Boolean).length

  if (criteria <= 2) {
    return { strength: 'weak', message: 'Add uppercase, lowercase, numbers, or special characters' }
  }
  if (criteria === 3) {
    return { strength: 'medium', message: 'Good password' }
  }
  return { strength: 'strong', message: 'Strong password' }
}

/**
 * Validate username
 * - 3-20 characters
 * - Alphanumeric and underscores only
 */
export function isValidUsername(username: string): boolean {
  const usernameRegex = /^[a-zA-Z0-9_]{3,20}$/
  return usernameRegex.test(username)
}
