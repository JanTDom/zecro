import React from 'react';
import { clsx } from 'clsx';

interface ToggleProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  description?: string;
  disabled?: boolean;
}

export const Toggle: React.FC<ToggleProps> = ({
  label,
  checked,
  onChange,
  description,
  disabled = false,
}) => {
  return (
    <label className={clsx('flex items-start justify-between cursor-pointer gap-3', disabled && 'opacity-50 cursor-not-allowed')}>
      <div className="space-y-0.5">
        <span className="text-sm font-medium text-ink-200 block">{label}</span>
        {description && <p className="text-xs text-ink-400 leading-tight">{description}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={clsx(
          'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-hidden',
          checked ? 'bg-editorial-crimson' : 'bg-ink-800'
        )}
      >
        <span
          className={clsx(
            'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out',
            checked ? 'translate-x-4' : 'translate-x-0'
          )}
        />
      </button>
    </label>
  );
};
