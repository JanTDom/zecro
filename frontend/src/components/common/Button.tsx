import React from 'react';
import { clsx } from 'clsx';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'editorial';
  size?: 'sm' | 'md' | 'lg' | 'icon';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'secondary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  className = '',
  disabled,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-medium transition-all duration-150 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none disabled:active:scale-100 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-editorial-crimson/35 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-950 select-none';

  const sizeStyles = {
    sm: 'text-xs px-2.5 py-1.5 rounded-md gap-1.5',
    md: 'text-sm px-3.5 py-2 rounded-lg gap-2',
    lg: 'text-base px-5 py-2.5 rounded-lg gap-2.5 font-semibold',
    icon: 'p-2 rounded-lg',
  };

  const variantStyles = {
    primary: 'bg-ink-100 text-white hover:bg-ink-200 font-semibold shadow-xs',
    secondary: 'bg-white text-ink-100 hover:bg-ink-950 border border-ink-800 hover:border-ink-700 shadow-xs',
    outline: 'bg-transparent text-ink-200 border border-ink-700 hover:bg-white hover:text-ink-100',
    ghost: 'bg-transparent text-ink-300 hover:bg-ink-950 hover:text-ink-100',
    danger: 'bg-red-50 text-red-700 hover:bg-red-100 border border-red-200',
    editorial: 'bg-editorial-crimson text-white hover:bg-[#173ed0] shadow-[0_8px_18px_rgba(36,81,245,0.2)] font-semibold tracking-wide text-xs',
  };

  return (
    <button
      className={clsx(baseStyles, sizeStyles[size], variantStyles[variant], className)}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <svg className="animate-spin h-4 w-4 text-current" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      ) : (
        leftIcon
      )}
      {children}
      {!isLoading && rightIcon}
    </button>
  );
};
