'use client';

import React from 'react';
import { Loader2 } from 'lucide-react';

type AnalysisProgressProps = {
  label?: string;
};

export const AnalysisProgress: React.FC<AnalysisProgressProps> = ({
  label = 'Analisando documento...',
}) => {
  return (
    <div className="flex min-h-[320px] items-center justify-center rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] px-6 py-10">
      <div className="flex flex-col items-center text-center">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-200">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
        <p className="text-sm font-medium text-[var(--text-primary)]">
          {label}
        </p>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          Isso pode levar alguns segundos enquanto extraímos as informações da
          requisição.
        </p>
        <div className="mt-4 h-1.5 w-48 overflow-hidden rounded-full bg-emerald-500/10">
          <div className="h-full w-1/2 animate-[pulse_1.4s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-emerald-400 via-emerald-500 to-emerald-600" />
        </div>
      </div>
    </div>
  );
};

