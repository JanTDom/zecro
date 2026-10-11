import React from 'react';

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  onChange: (val: number) => void;
  description?: string;
}

export const Slider: React.FC<SliderProps> = ({
  label,
  value,
  min,
  max,
  step = 1,
  unit = '',
  onChange,
  description,
}) => {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs font-medium">
        <label className="text-ink-300 font-sans">{label}</label>
        <span className="font-mono text-xs font-bold text-editorial-ochre bg-ink-950 px-2 py-0.5 rounded border border-ink-800">
          {value}
          {unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1.5 bg-ink-800 rounded-lg appearance-none cursor-pointer accent-editorial-crimson focus:outline-none"
      />
      {description && <p className="text-[11px] text-ink-400 leading-tight">{description}</p>}
    </div>
  );
};
