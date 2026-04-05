import { useNavigate } from 'react-router-dom'
import { GoogleLogin, type CredentialResponse } from '@react-oauth/google'
import { useAuth } from '@/contexts/AuthContext'

export function LoginPage() {
  const { login, error, clearError, isLoading } = useAuth()
  const navigate = useNavigate()

  const handleGoogleSuccess = async (response: CredentialResponse) => {
    if (!response.credential) return
    clearError()
    try {
      await login(response.credential)
      navigate('/dashboard', { replace: true })
    } catch {
      // Error is set in AuthContext
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-bg-primary">
      <div className="w-full max-w-sm p-8 space-y-6">
        {/* Logo */}
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-semibold text-text-primary">VegaExchange</h1>
          <p className="text-sm text-text-tertiary">Admin Dashboard</p>
        </div>

        {/* Divider */}
        <div className="border-t border-border-default" />

        {/* Error message */}
        {error && (
          <div className="p-3 text-sm text-accent-red bg-accent-red/10 border border-accent-red/20 rounded-lg">
            {error}
          </div>
        )}

        {/* Google login */}
        <div className="flex justify-center">
          {isLoading ? (
            <div className="w-6 h-6 border-2 border-text-tertiary border-t-accent-blue rounded-full animate-spin" />
          ) : (
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={() => {}}
              theme="filled_black"
              size="large"
              width="320"
              text="signin_with"
            />
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-text-tertiary">
          Only whitelisted admin accounts can sign in.
        </p>
      </div>
    </div>
  )
}
