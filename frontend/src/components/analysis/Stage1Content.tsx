import React, { useState } from 'react';
import type { Stage1Data, Stage1Confidence } from '../../types/extraction';
import { ConfidenceBadge } from './ConfidenceBadge';

type Stage1ContentProps = {
  data: Stage1Data | null;
  confidence: Stage1Confidence | null;
  method: string;
};

export const Stage1Content: React.FC<Stage1ContentProps> = ({
  data,
  confidence,
  method,
}) => {
  const [editable, setEditable] = useState(() => ({
    nup: data?.nup ?? '',
    requisicaoTexto: (() => {
      const numero = data?.requisicao?.numero;
      const ano = data?.requisicao?.ano;
      if (!numero && !ano) return '';
      if (numero && ano) return `Requisição ${numero}/${ano}`;
      if (numero) return `Requisição ${numero}`;
      return data?.requisicao?.texto_original ?? '';
    })(),
    om: data?.om?.nome ?? '',
  }));

  const lowThreshold = 70;
  const nupLow = (confidence?.nup ?? 0) < lowThreshold;
  const reqLow = (confidence?.requisicao ?? 0) < lowThreshold;
  const omLow = (confidence?.om ?? 0) < lowThreshold;

  const displayMethod =
    method === 'regex'
      ? 'Regex'
      : method === 'ai'
        ? 'IA'
        : method === 'hybrid'
          ? 'Híbrido'
          : method;

  const effectiveNup = nupLow ? editable.nup : data?.nup ?? '';
  const effectiveReq = reqLow
    ? editable.requisicaoTexto
    : (() => {
        const numero = data?.requisicao?.numero;
        const ano = data?.requisicao?.ano;
        if (!numero && !ano) return '';
        if (numero && ano) return `Requisição ${numero}/${ano}`;
        if (numero) return `Requisição ${numero}`;
        return data?.requisicao?.texto_original ?? '';
      })();
  const effectiveOm = omLow ? editable.om : data?.om?.nome ?? '';

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-200">
            {displayMethod}
          </span>
          {confidence && (
            <span className="text-xs text-[var(--text-secondary)]">
              Score geral do estágio:
            </span>
          )}
        </div>
        {confidence && <ConfidenceBadge value={confidence.geral} />}
      </div>

      <div className="space-y-3 rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/40 p-3">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-medium text-[var(--text-secondary)]">
              NUP (Número Único de Protocolo)
            </p>
            {nupLow ? (
              <input
                value={effectiveNup}
                onChange={(e) =>
                  setEditable((prev) => ({ ...prev, nup: e.target.value }))
                }
                placeholder="Informe ou corrija o NUP"
                className="mt-1 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] px-2 py-1 text-sm text-[var(--text-primary)] outline-none ring-emerald-500/30 transition focus:border-emerald-500 focus:ring-2"
              />
            ) : (
              <p className="mt-1 text-sm text-[var(--text-primary)]">
                {effectiveNup || 'Não identificado'}
              </p>
            )}
          </div>
          <ConfidenceBadge value={confidence?.nup ?? null} />
        </div>

        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div className="sm:flex-1">
            <p className="text-xs font-medium text-[var(--text-secondary)]">
              Requisição
            </p>
            {reqLow ? (
              <input
                value={effectiveReq}
                onChange={(e) =>
                  setEditable((prev) => ({
                    ...prev,
                    requisicaoTexto: e.target.value,
                  }))
                }
                placeholder="Ex.: Requisição 15/2025"
                className="mt-1 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] px-2 py-1 text-sm text-[var(--text-primary)] outline-none ring-emerald-500/30 transition focus:border-emerald-500 focus:ring-2"
              />
            ) : (
              <p className="mt-1 text-sm text-[var(--text-primary)]">
                {effectiveReq || 'Não identificado'}
              </p>
            )}
          </div>
          <ConfidenceBadge value={confidence?.requisicao ?? null} />
        </div>

        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div className="sm:flex-1">
            <div className="flex items-center gap-2">
              <p className="text-xs font-medium text-[var(--text-secondary)]">
                OM (Órgão de Origem)
              </p>
              {data?.om && (
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                    data.om.validada
                      ? 'bg-emerald-500/10 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200'
                      : 'bg-amber-500/10 text-amber-700 dark:bg-amber-500/20 dark:text-amber-100'
                  }`}
                >
                  {data.om.validada ? 'Validada' : 'Não reconhecida'}
                </span>
              )}
            </div>
            {omLow ? (
              <input
                value={effectiveOm}
                onChange={(e) =>
                  setEditable((prev) => ({ ...prev, om: e.target.value }))
                }
                placeholder="Ex.: 9º Batalhão Logístico"
                className="mt-1 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] px-2 py-1 text-sm text-[var(--text-primary)] outline-none ring-emerald-500/30 transition focus:border-emerald-500 focus:ring-2"
              />
            ) : (
              <p className="mt-1 text-sm text-[var(--text-primary)]">
                {data?.om
                  ? data.om.validada
                    ? `${
                        data.om.nome ?? ''
                      }${data.om.sigla ? ` (${data.om.sigla})` : ''}`
                    : data.om.nome || 'Não identificado'
                  : 'Não identificado'}
              </p>
            )}
          </div>
          <ConfidenceBadge value={confidence?.om ?? null} />
        </div>
      </div>
    </div>
  );
};

