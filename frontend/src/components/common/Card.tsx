import React from 'react';
import { clsx } from 'clsx';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  variant?: 'default' | 'elevated' | 'paper' | 'ghost';
  noPadding?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'default',
  noPadding = false,
  className = '',
  ...props
}) => {
  const base = 'rounded-xl border transition-all duration-200';
  const variants = {
    default: 'bg-white border-ink-800 shadow-[0_8px_24px_rgba(28,34,49,0.04)] text-ink-100',
    elevated: 'bg-white border-ink-700 shadow-[0_18px_42px_rgba(28,34,49,0.09)] text-ink-100',
    paper: 'bg-paper-100 border-paper-300 text-ink-950 shadow-page',
    ghost: 'bg-transparent border-ink-800 text-ink-200',
  };

  return (
    <div
      className={clsx(base, variants[variant], !noPadding && 'p-5', className)}
      {...props}
    >
      {children}
    </div>
  );
};
