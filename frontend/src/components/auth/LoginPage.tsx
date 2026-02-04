import React from 'react'
import { useNavigate } from 'react-router-dom'
import { LoginForm } from './LoginForm'
import { useAuth } from '../../hooks'
import { Card } from '../common'

export const LoginPage: React.FC = () => {
  const navigate = useNavigate()
  const { login, googleLogin, error, isLoading, clearAuthError } = useAuth()

  const handleEmailLogin = async (email: string, password: string) => {
    clearAuthError()
    await login({ email, password })
    navigate('/dashboard')
  }

  const handleGoogleLogin = async (googleId: string) => {
    clearAuthError()
    await googleLogin(googleId)
    navigate('/dashboard')
  }

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
          <p className="text-text-secondary">Sign in to your account</p>
        </div>

        {/* Login Card */}
        <Card padding="lg">
          <LoginForm
            onEmailLogin={handleEmailLogin}
            onGoogleLogin={handleGoogleLogin}
            error={error}
            isLoading={isLoading}
          />
        </Card>

        {/* Footer */}
        <p className="text-center text-xs text-text-tertiary mt-8">
          By signing in, you agree to our Terms of Service and Privacy Policy
        </p>
      </div>
    </div>
  )
}
