'use client';

import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Lock,
  XCircle,
} from 'lucide-react';

type StageCardProps = {
  title: string;
  subtitle?: string;
  disabled?: boolean;
  confidence?: number | null;
  defaultOpen?: boolean;
  children?: React.ReactNode;
};

export const StageCard: React.FC<StageCardProps> = ({
  title,
  subtitle,
  disabled = false,
  confidence,
  defaultOpen = true,
  children,
}) => {
  const [open, setOpen] = useState(defaultOpen && !disabled);

  let statusIcon = (
    <XCircle className="h-4 w-4 text-slate-400 dark:text-slate-500" />
  );
  let statusColor =
    'bg-slate-100 text-slate-700 dark:bg-slate-800/80 dark:text-slate-200';

  if (!disabled && typeof confidence === 'number') {
    if (confidence > 85) {
      statusIcon = <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
      statusColor =
        'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200';
    } else if (confidence >= 50) {
      statusIcon = <AlertTriangle className="h-4 w-4 text-amber-500" />;
      statusColor =
        'bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-200';
    } else {
      statusIcon = <XCircle className="h-4 w-4 text-rose-500" />;
      statusColor =
        'bg-rose-50 text-rose-800 dark:bg-rose-500/10 dark:text-rose-200';
    }
  }

  if (disabled) {
    statusIcon = <Lock className="h-4 w-4 text-slate-400 dark:text-slate-500" />;
    statusColor =
      'bg-slate-100 text-slate-600 dark:bg-slate-800/80 dark:text-slate-300';
  }

  return (
    <section
      className={[
        'overflow-hidden rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] shadow-sm shadow-black/5 transition-opacity',
        disabled ? 'opacity-60' : 'opacity-100',
      ].join(' ')}
    >
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
        onClick={() => {
          if (!disabled) setOpen((prev) => !prev);
        }}
        aria-expanded={open}
        disabled={disabled}
      >
        <div className="flex items-center gap-3">
          <div
            className={[
              'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.16em]',
              statusColor,
            ].join(' ')}
          >
            {statusIcon}
            <span>{disabled ? 'Em breve' : 'Estágio'}</span>
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--text-primary)]">
              {title}
            </p>
            {subtitle && (
              <p className="text-xs text-[var(--text-secondary)]">{subtitle}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!disabled && typeof confidence === 'number' && (
            <span className="text-xs font-medium text-[var(--text-secondary)]">
              Confiança {Math.round(confidence)}%
            </span>
          )}
          <ChevronDown
            className={[
              'h-4 w-4 text-[var(--text-secondary)] transition-transform',
              open && !disabled ? 'rotate-180' : 'rotate-0',
              disabled ? 'opacity-40' : '',
            ].join(' ')}
          />
        </div>
      </button>
      <div
        className={[
          'grid transition-[grid-template-rows,opacity] duration-300 ease-out',
          open && !disabled
            ? 'grid-rows-[1fr] opacity-100'
            : 'grid-rows-[0fr] opacity-0',
        ].join(' ')}
      >
        <div className="min-h-0 overflow-hidden border-t border-[var(--border-subtle)]/80">
          <div className="px-4 py-4">{children}</div>
        </div>
      </div>
    </section>
  );
};

