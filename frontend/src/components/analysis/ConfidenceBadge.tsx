import React from 'react';

type ConfidenceBadgeProps = {
  value: number | null | undefined;
  className?: string;
};

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({
  value,
  className = '',
}) => {
  const v = typeof value === 'number' ? Math.round(value) : null;

  let colorClasses =
    'bg-slate-100 text-slate-700 dark:bg-slate-800/80 dark:text-slate-200';
  if (v !== null) {
    if (v > 85) {
      colorClasses =
        'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200';
    } else if (v >= 50) {
      colorClasses =
        'bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200';
    } else {
      colorClasses =
        'bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-200';
    }
  }

  return (
    <span
      className={[
        'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.16em]',
        colorClasses,
        className,
      ].join(' ')}
    >
      {v !== null ? `${v}%` : '—'}
    </span>
  );
};

