import React from 'react';
import { clsx } from 'clsx';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'accent' | 'outline' | 'score';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  icon?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  className = '',
  icon,
}) => {
  const baseStyles = 'inline-flex items-center font-medium font-sans uppercase tracking-wider transition-colors';

  const sizeStyles = {
    sm: 'text-[10px] px-1.5 py-0.5 rounded gap-1',
    md: 'text-xs px-2.5 py-1 rounded-md gap-1.5',
    lg: 'text-sm px-3 py-1.5 rounded-lg gap-2',
  };

  const variantStyles = {
    default: 'bg-ink-950 text-ink-200 border border-ink-800',
    success: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
    warning: 'bg-amber-50 text-amber-700 border border-amber-200',
    danger: 'bg-red-50 text-red-700 border border-red-200',
    accent: 'bg-blue-50 text-editorial-crimson border border-blue-100',
    outline: 'bg-transparent text-ink-300 border border-ink-700',
    score: 'bg-white text-editorial-ochre border border-amber-200 font-mono font-bold',
  };

  return (
    <span className={clsx(baseStyles, sizeStyles[size], variantStyles[variant], className)}>
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </span>
  );
};
