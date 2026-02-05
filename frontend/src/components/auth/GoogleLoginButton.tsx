import React from 'react'
import { GoogleLogin, type CredentialResponse } from '@react-oauth/google'

interface GoogleLoginButtonProps {
  onSuccess: (idToken: string) => void
  onError?: (error: string) => void
  isLoading?: boolean
}

export const GoogleLoginButton: React.FC<GoogleLoginButtonProps> = ({
  onSuccess,
  onError,
  isLoading = false,
}) => {
  const handleSuccess = (credentialResponse: CredentialResponse) => {
    if (credentialResponse.credential) {
      // credential is the ID token that backend can verify
      onSuccess(credentialResponse.credential)
    } else {
      onError?.('No credential received from Google')
    }
  }

  const handleError = () => {
    onError?.('Google authentication failed')
  }

  if (isLoading) {
    return (
      <div className="w-full h-10 bg-bg-tertiary rounded-lg animate-pulse flex items-center justify-center">
        <span className="text-text-secondary text-sm">Loading...</span>
      </div>
    )
  }

  return (
    <div className="w-full flex justify-center">
      <GoogleLogin
        onSuccess={handleSuccess}
        onError={handleError}
        useOneTap={false}
        theme="filled_black"
        size="large"
        width="100%"
        text="continue_with"
        shape="rectangular"
      />
    </div>
  )
}
