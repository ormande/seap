import React, { useState } from 'react';

import type {
  Stage5Dispatch,
  Stage5ExigenciaStatus,
  Stage5Result,
} from '../../types/extraction';

type Stage5ContentProps = {
  data: Stage5Result | null;
};

const typeColor = (tipo: string): string => {
  if (tipo === 'encaminhamento') return 'bg-emerald-500';
  if (tipo === 'informativo') return 'bg-amber-400';
  if (tipo === 'exigencia') return 'bg-rose-500';
  return 'bg-slate-500';
};

const typeLabel = (tipo: string): string => {
  if (tipo === 'encaminhamento') return 'Encaminhamento';
  if (tipo === 'informativo') return 'Informativo';
  if (tipo === 'exigencia') return 'Com exigência';
  return tipo;
};

const VeredictBadge: React.FC<{ data: Stage5Result }> = ({ data }) => {
  const hasPendencias = (data.exigencias_pendentes ?? []).length > 0;
  const status = data.status ?? (hasPendencias ? 'com_pendencias' : 'sa');
  const pendingCount = data.exigencias_pendentes?.length ?? 0;
  const total = data.total_despachos ?? 0;

  if (status === 'sa' && !hasPendencias) {
    return (
      <div className="flex flex-col gap-1 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3">
        <div className="text-sm font-semibold text-emerald-800 dark:text-emerald-100">
          S/A — Sem Alteração
        </div>
        <p className="text-xs text-emerald-900/80 dark:text-emerald-100/80">
          Nenhuma exigência ou correção pendente foi identificada nos despachos.
        </p>
        {total > 0 && (
          <span className="text-[11px] text-emerald-900/70 dark:text-emerald-100/70">
            {total} despacho(s) analisado(s).
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3">
      <div className="text-sm font-semibold text-rose-800 dark:text-rose-100">
        Pendências encontradas
      </div>
      <p className="text-xs text-rose-900/80 dark:text-rose-100/80">
        {pendingCount > 0
          ? `${pendingCount} exigência(s) pendente(s) de resolução.`
          : 'Exigências foram identificadas, mas não foi possível confirmar se foram totalmente sanadas.'}
      </p>
    </div>
  );
};

const ExigenciasList: React.FC<{
  dispatch: Stage5Dispatch;
  pendentes: Stage5ExigenciaStatus[];
  atendidas: Stage5ExigenciaStatus[];
  isFinalDispatch: boolean;
}> = ({ dispatch, pendentes, atendidas, isFinalDispatch }) => {
  const all = dispatch.exigencias ?? [];
  if (all.length === 0) return null;

  const byDescricao = (descricao: string) =>
    ({
      pendente: pendentes.find((e) => e.descricao === descricao),
      atendida: atendidas.find((e) => e.descricao === descricao),
    } as const);

  return (
    <div className="mt-2 space-y-1 rounded-lg bg-[var(--bg-main)]/50 p-2">
      {all.map((ex, idx) => {
        const statusInfo = byDescricao(ex.descricao);
        const status =
          !isFinalDispatch && statusInfo.atendida
            ? 'atendida'
            : !isFinalDispatch && statusInfo.pendente
              ? 'pendente'
              : null;
        const resolucao = statusInfo.atendida?.despacho_resolucao ?? null;
        const evidencia = statusInfo.atendida?.evidencia ?? statusInfo.pendente?.evidencia ?? null;

        return (
          <div
            key={`${ex.descricao}-${idx}`}
            className="flex flex-col gap-1 rounded-md border border-[var(--border-subtle)]/70 bg-[var(--bg-main)]/60 px-2 py-1.5"
          >
            <div className="flex flex-wrap items-center justify-between gap-1">
              <p className="text-xs text-[var(--text-primary)]">{ex.descricao}</p>
              {isFinalDispatch ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-500/20 px-2 py-0.5 text-[10px] font-semibold text-slate-800 dark:bg-slate-500/30 dark:text-slate-100">
                  Instrução de análise
                </span>
              ) : (
                <>
                  {status === 'atendida' && resolucao && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200">
                      Atendida no Despacho Nº {resolucao}
                    </span>
                  )}
                  {status === 'pendente' && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/15 px-2 py-0.5 text-[10px] font-semibold text-rose-700 dark:bg-rose-500/20 dark:text-rose-100">
                      Pendente
                    </span>
                  )}
                </>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {ex.categoria && (
                <span className="inline-flex items-center rounded-full bg-slate-500/10 px-2 py-0.5 text-[10px] font-medium text-slate-700 dark:bg-slate-500/20 dark:text-slate-200">
                  {ex.categoria}
                </span>
              )}
              {ex.urgente && (
                <span className="inline-flex items-center rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-800 dark:bg-amber-500/20 dark:text-amber-100">
                  Urgente
                </span>
              )}
            </div>
            {!isFinalDispatch && evidencia && (
              <p className="text-[10px] text-[var(--text-secondary)]">
                {evidencia}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
};

const DispatchTimelineItem: React.FC<{
  dispatch: Stage5Dispatch;
  isLast: boolean;
  pendentes: Stage5ExigenciaStatus[];
  atendidas: Stage5ExigenciaStatus[];
}> = ({ dispatch, isLast, pendentes, atendidas }) => {
  const [open, setOpen] = useState(false);
  const hasExigencias = (dispatch.exigencias ?? []).length > 0;
  const circleColor = typeColor(dispatch.tipo);

  return (
    <div className="relative flex gap-4">
      {/* Linha vertical + nó */}
      <div className="flex flex-col items-center">
        <div className="relative flex h-4 w-4 items-center justify-center">
          <div className="h-3 w-3 rounded-full bg-emerald-300/20" />
          <div className={`absolute h-2.5 w-2.5 rounded-full ${circleColor} shadow shadow-emerald-500/40`} />
        </div>
        {!isLast && <div className="mt-1 h-full w-[2px] bg-emerald-400/40" />}
      </div>

      {/* Card do despacho */}
      <div className="flex-1">
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="w-full rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/60 px-3 py-2 text-left shadow-sm shadow-black/5 transition hover:border-emerald-500/60 hover:bg-emerald-500/5"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-xs font-semibold text-[var(--text-primary)]">
                  Despacho Nº {dispatch.numero ?? '—'}
                </p>
                {dispatch.data && (
                  <span className="rounded-full bg-slate-500/10 px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
                    {dispatch.data}
                  </span>
                )}
              </div>
              <p className="mt-1 line-clamp-2 text-[11px] text-[var(--text-secondary)]">
                {dispatch.resumo || dispatch.assunto || 'Sem resumo disponível para este despacho.'}
              </p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200">
                {typeLabel(dispatch.tipo)}
              </span>
              {(dispatch.autor_secao || typeof dispatch.confianca === 'number') && (
                <div className="flex w-full items-center justify-between text-[10px] text-[var(--text-secondary)]">
                  <span className="mr-2">
                    {dispatch.autor_secao ?? ''}
                  </span>
                  {typeof dispatch.confianca === 'number' && (
                    <span>{dispatch.confianca}%</span>
                  )}
                </div>
              )}
            </div>
          </div>
          {hasExigencias && (
            <p className="mt-2 text-[11px] font-medium text-emerald-700 dark:text-emerald-200">
              {open ? 'Ocultar exigências' : 'Ver exigências deste despacho'}
            </p>
          )}
        </button>

        {hasExigencias && open && (
          <ExigenciasList
            dispatch={dispatch}
            pendentes={pendentes}
            atendidas={atendidas}
            isFinalDispatch={isLast}
          />
        )}
      </div>
    </div>
  );
};

export const Stage5Content: React.FC<Stage5ContentProps> = ({ data }) => {
  if (!data) {
    return (
      <p className="text-xs text-[var(--text-secondary)]">
        Nenhuma análise de despachos disponível.
      </p>
    );
  }

  const despachos: Stage5Dispatch[] = data.despachos ?? [];
  const pendentes: Stage5ExigenciaStatus[] = data.exigencias_pendentes ?? [];
  const atendidas: Stage5ExigenciaStatus[] = data.exigencias_atendidas ?? [];

  if (despachos.length === 0) {
    return (
      <div className="space-y-3">
        <VeredictBadge data={data} />
        <p className="text-xs text-[var(--text-secondary)]">
          Nenhum despacho com o padrão &quot;Despacho Nº&quot; foi identificado neste
          processo.
        </p>
      </div>
    );
  }

  const confidence = data.confidence?.geral;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <VeredictBadge data={data} />
        {typeof confidence === 'number' && (
          <span className="text-xs text-[var(--text-secondary)]">
            Confiança: {Math.round(confidence)}%
          </span>
        )}
      </div>

      <div className="space-y-3 rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/40 p-3">
        <p className="text-xs font-medium text-[var(--text-secondary)]">
          Linha do tempo dos despachos
        </p>
        <div className="mt-2 space-y-4">
          {despachos.map((d, idx) => (
            <DispatchTimelineItem
              key={`${d.numero ?? 'desp'}-${idx}`}
              dispatch={d}
              isLast={idx === despachos.length - 1}
              pendentes={pendentes}
              atendidas={atendidas}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

