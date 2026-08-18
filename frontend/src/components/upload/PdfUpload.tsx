import { UploadCloud, FileText, AlertCircle } from 'lucide-react';
import React, { useCallback, useRef, useState } from 'react';

type PdfUploadProps = {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
};

export const PdfUpload: React.FC<PdfUploadProps> = ({
  onFileSelected,
  disabled,
}) => {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const file = files[0];
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setError('Apenas arquivos .pdf são aceitos.');
        return;
      }
      setError(null);
      onFileSelected(file);
    },
    [onFileSelected],
  );

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    setDragActive(false);
    handleFiles(e.dataTransfer.files);
  };

  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    setDragActive(true);
  };

  const onDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  return (
    <div className="space-y-2">
      <div
        className={[
          'group relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-6 py-10 text-center transition',
          dragActive
            ? 'border-emerald-500 bg-emerald-50/80 dark:bg-emerald-900/30'
            : 'border-[var(--border-subtle)]/80 bg-[var(--bg-card)] dark:border-emerald-800/70',
          disabled
            ? 'cursor-not-allowed opacity-60'
            : 'hover:border-emerald-500 hover:bg-emerald-50/80 dark:hover:bg-emerald-900/40',
        ].join(' ')}
        onClick={() => {
          if (!disabled) inputRef.current?.click();
        }}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
      >
        <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-600 shadow-sm shadow-emerald-500/30 transition group-hover:scale-105 group-hover:bg-emerald-500 group-hover:text-white dark:bg-emerald-500/20 dark:text-emerald-200">
          <UploadCloud className="h-7 w-7" />
        </div>
        <p className="text-sm font-medium text-[var(--text-primary)]">
          Arraste e solte um PDF aqui
        </p>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          ou clique para selecionar um arquivo (.pdf)
        </p>
        <p className="mt-3 flex items-center justify-center gap-1 text-[11px] uppercase tracking-wide text-emerald-400/80">
          <FileText className="h-3 w-3" />
          Requisições em PDF
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
          disabled={disabled}
        />
        {dragActive && (
          <div className="pointer-events-none absolute inset-0 rounded-2xl border border-emerald-500/70 bg-emerald-500/5" />
        )}
      </div>
      {error && (
        <p className="flex items-center gap-1 text-xs text-amber-700 dark:text-amber-300">
          <AlertCircle className="h-3 w-3" />
          {error}
        </p>
      )}
    </div>
  );
};

