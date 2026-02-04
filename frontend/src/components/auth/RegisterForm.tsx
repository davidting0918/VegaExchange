import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Input } from '../common'
import { GoogleLoginButton } from './GoogleLoginButton'
import { isValidEmail, isValidPassword, getPasswordStrength } from '../../utils'

interface RegisterFormProps {
  onEmailRegister: (email: string, password: string, userName?: string) => Promise<void>
  onGoogleLogin: (googleId: string) => Promise<void>
  error?: string | null
  isLoading?: boolean
}

export const RegisterForm: React.FC<RegisterFormProps> = ({
  onEmailRegister,
  onGoogleLogin,
  error,
  isLoading = false,
}) => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [userName, setUserName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  const passwordStrength = getPasswordStrength(password)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setValidationError(null)

    // Validation
    if (!email || !password || !confirmPassword) {
      setValidationError('Please fill in all required fields')
      return
    }

    if (!isValidEmail(email)) {
      setValidationError('Please enter a valid email address')
      return
    }

    if (!isValidPassword(password)) {
      setValidationError('Password must be at least 8 characters with uppercase, lowercase, and number')
      return
    }

    if (password !== confirmPassword) {
      setValidationError('Passwords do not match')
      return
    }

    try {
      await onEmailRegister(email, password, userName || undefined)
    } catch (err) {
      // Error is handled by parent
    }
  }

  const handleGoogleSuccess = async (googleId: string) => {
    try {
      await onGoogleLogin(googleId)
    } catch (err) {
      // Error is handled by parent
    }
  }

  const displayError = validationError || error

  const strengthColors = {
    weak: 'bg-accent-red',
    medium: 'bg-accent-yellow',
    strong: 'bg-accent-green',
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Google Login */}
      <GoogleLoginButton
        onSuccess={handleGoogleSuccess}
        onError={(err) => setValidationError(err)}
        isLoading={isLoading}
      />

      {/* Divider */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-border-default" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="px-4 bg-bg-secondary text-text-tertiary">or register with email</span>
        </div>
      </div>

      {/* Error message */}
      {displayError && (
        <div className="p-3 rounded-lg bg-accent-red/10 border border-accent-red/20">
          <p className="text-sm text-accent-red">{displayError}</p>
        </div>
      )}

      {/* Username input (optional) */}
      <Input
        type="text"
        label="Username (optional)"
        placeholder="Choose a username"
        value={userName}
        onChange={(e) => setUserName(e.target.value)}
        autoComplete="username"
        disabled={isLoading}
      />

      {/* Email input */}
      <Input
        type="email"
        label="Email"
        placeholder="Enter your email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        autoComplete="email"
        disabled={isLoading}
      />

      {/* Password input */}
      <div>
        <Input
          type={showPassword ? 'text' : 'password'}
          label="Password"
          placeholder="Create a password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          disabled={isLoading}
          rightIcon={
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="text-text-tertiary hover:text-text-primary transition-colors"
            >
              {showPassword ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              )}
            </button>
          }
        />
        {/* Password strength indicator */}
        {password && (
          <div className="mt-2">
            <div className="flex gap-1 mb-1">
              <div className={`h-1 flex-1 rounded ${password.length > 0 ? strengthColors[passwordStrength.strength] : 'bg-border-default'}`} />
              <div className={`h-1 flex-1 rounded ${passwordStrength.strength !== 'weak' ? strengthColors[passwordStrength.strength] : 'bg-border-default'}`} />
              <div className={`h-1 flex-1 rounded ${passwordStrength.strength === 'strong' ? strengthColors[passwordStrength.strength] : 'bg-border-default'}`} />
            </div>
            <p className="text-xs text-text-tertiary">{passwordStrength.message}</p>
          </div>
        )}
      </div>

      {/* Confirm password input */}
      <Input
        type={showPassword ? 'text' : 'password'}
        label="Confirm Password"
        placeholder="Confirm your password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        autoComplete="new-password"
        disabled={isLoading}
        error={confirmPassword && password !== confirmPassword ? 'Passwords do not match' : undefined}
      />

      {/* Submit button */}
      <Button type="submit" fullWidth isLoading={isLoading}>
        Create Account
      </Button>

      {/* Login link */}
      <p className="text-center text-sm text-text-secondary">
        Already have an account?{' '}
        <Link to="/login" className="text-accent-blue hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  )
}
