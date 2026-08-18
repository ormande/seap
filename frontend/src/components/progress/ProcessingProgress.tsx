import { Loader2 } from 'lucide-react';
import React from 'react';

type ProcessingProgressProps = {
  visible: boolean;
  label?: string;
};

export const ProcessingProgress: React.FC<ProcessingProgressProps> = ({
  visible,
  label = 'Processando PDF com IA...',
}) => {
  if (!visible) return null;

  return (
    <div className="mt-4 flex items-center gap-3 rounded-lg border border-emerald-700/60 bg-emerald-900/40 px-4 py-3 text-sm text-emerald-100">
      <Loader2 className="h-4 w-4 animate-spin text-amber-300" />
      <div className="flex-1">
        <p className="text-xs font-medium uppercase tracking-wide text-emerald-300">
          Em processamento
        </p>
        <p className="text-xs text-emerald-200/80">{label}</p>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-emerald-950/80">
          <div className="h-full w-1/2 animate-[pulse_1.4s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-emerald-400 via-amber-300 to-emerald-500" />
        </div>
      </div>
    </div>
  );
};

