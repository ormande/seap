import { FileSearch } from 'lucide-react';
import React from 'react';

type AppHeaderProps = {
  title?: string;
  subtitle?: string;
};

export const AppHeader: React.FC<AppHeaderProps> = ({
  title = 'SELIC - Sistema de Extração de Licitações',
  subtitle = 'Análise inteligente de PDFs de licitações do Exército Brasileiro',
}) => {
  return (
    <header className="border-b border-emerald-800/50 bg-gradient-to-r from-[#1b2715] via-[#111827] to-[#1b2715] px-6 py-4 shadow-lg shadow-black/40">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#2D4A22] text-amber-300 shadow-md shadow-black/60">
            <FileSearch className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-wide text-emerald-100 sm:text-xl">
              {title}
            </h1>
            <p className="text-xs text-emerald-300/70 sm:text-sm">{subtitle}</p>
          </div>
        </div>
        <div className="hidden text-right text-xs text-emerald-300/60 sm:block">
          <p className="font-mono uppercase tracking-wide text-amber-300">
            Ambiente Local
          </p>
          <p>Backend FastAPI · Gemini IA</p>
        </div>
      </div>
    </header>
  );
};

