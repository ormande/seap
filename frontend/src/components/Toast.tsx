'use client';

import { CheckCircle2 } from 'lucide-react';
import React, { useEffect, useState } from 'react';

type ToastProps = {
  message: string;
  durationMs?: number;
  onClose?: () => void;
};

export const Toast: React.FC<ToastProps> = ({
  message,
  durationMs = 3000,
  onClose,
}) => {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    if (!message) return;

    setExiting(false);

    const exitTimer = setTimeout(() => {
      setExiting(true);
    }, Math.max(0, durationMs - 200));

    const closeTimer = setTimeout(() => {
      onClose?.();
    }, durationMs);

    return () => {
      clearTimeout(exitTimer);
      clearTimeout(closeTimer);
    };
  }, [message, durationMs, onClose]);

  if (!message) return null;

  return (
    <div className="pointer-events-none fixed left-1/2 top-6 z-[100] -translate-x-1/2 transform">
      <div
        className={[
          'pointer-events-auto flex items-center gap-3 rounded-xl border border-emerald-400/40 bg-[#0b1220]/95 px-6 py-4 shadow-lg shadow-emerald-500/25 backdrop-blur-md',
          exiting ? 'animate-toast-slide-up' : 'animate-toast-slide-down',
        ].join(' ')}
      >
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/10 animate-toast-scale-in">
          <CheckCircle2 className="h-5 w-5 text-emerald-400" />
        </div>
        <span className="text-sm font-medium text-slate-50">{message}</span>
      </div>
    </div>
  );
};

