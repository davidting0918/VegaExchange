import React from 'react'
import clsx from 'clsx'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  className,
}) => {
  const sizeStyles = {
    sm: 'w-4 h-4 border-2',
    md: 'w-8 h-8 border-3',
    lg: 'w-12 h-12 border-4',
  }

  return (
    <div
      className={clsx(
        'rounded-full border-accent-blue border-t-transparent animate-spin',
        sizeStyles[size],
        className
      )}
    />
  )
}

interface LoadingOverlayProps {
  message?: string
}

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({ message }) => {
  return (
    <div className="fixed inset-0 bg-bg-primary/80 flex items-center justify-center z-50">
      <div className="flex flex-col items-center gap-4">
        <LoadingSpinner size="lg" />
        {message && <p className="text-text-secondary">{message}</p>}
      </div>
    </div>
  )
}
