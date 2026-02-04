import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { RegisterForm } from './RegisterForm'
import { useAuth } from '../../hooks'
import { Card } from '../common'
import { authService } from '../../api'

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate()
  const { googleLogin, error: authError, isLoading, clearAuthError } = useAuth()
  const [registerError, setRegisterError] = useState<string | null>(null)
  const [isRegistering, setIsRegistering] = useState(false)

  // Note: Email registration requires API key/secret which is typically
  // provided by backend or obtained through a different flow.
  // For demo purposes, we'll show an error or allow if keys are configured
  const handleEmailRegister = async (email: string, password: string, userName?: string) => {
    clearAuthError()
    setRegisterError(null)
    setIsRegistering(true)

    try {
      // Check if API keys are configured (for demo/testing)
      const apiKey = import.meta.env.VITE_API_KEY || ''
      const apiSecret = import.meta.env.VITE_API_SECRET || ''

      if (!apiKey || !apiSecret) {
        setRegisterError('Email registration is currently disabled. Please use Google sign-in.')
        setIsRegistering(false)
        return
      }

      const response = await authService.registerWithEmail(
        { email, password, user_name: userName },
        apiKey,
        apiSecret
      )

      if (response.success && response.data) {
        localStorage.setItem('vega_access_token', response.data.access_token)
        localStorage.setItem('vega_refresh_token', response.data.refresh_token)
        navigate('/dashboard')
      } else {
        setRegisterError(response.message || 'Registration failed')
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Registration failed'
      setRegisterError(message)
    } finally {
      setIsRegistering(false)
    }
  }

  const handleGoogleLogin = async (googleId: string) => {
    clearAuthError()
    setRegisterError(null)
    try {
      await googleLogin(googleId)
      navigate('/dashboard')
    } catch {
      // Error handled by auth hook
    }
  }

  const displayError = registerError || authError

  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 mb-4">
            <svg className="w-10 h-10" viewBox="0 0 100 100">
              <defs>
                <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style={{ stopColor: '#58A6FF' }} />
                  <stop offset="100%" style={{ stopColor: '#3FB950' }} />
                </linearGradient>
              </defs>
              <polygon points="50,10 90,85 10,85" fill="url(#logoGrad)" />
              <text x="50" y="65" fontFamily="Arial, sans-serif" fontSize="24" fontWeight="bold" fill="white" textAnchor="middle">V</text>
            </svg>
            <span className="text-2xl font-bold text-text-primary">Vega Exchange</span>
          </div>
          <p className="text-text-secondary">Create your account</p>
        </div>

        {/* Register Card */}
        <Card padding="lg">
          <RegisterForm
            onEmailRegister={handleEmailRegister}
            onGoogleLogin={handleGoogleLogin}
            error={displayError}
            isLoading={isLoading || isRegistering}
          />
        </Card>

        {/* Footer */}
        <p className="text-center text-xs text-text-tertiary mt-8">
          By creating an account, you agree to our Terms of Service and Privacy Policy
        </p>
      </div>
    </div>
  )
}
