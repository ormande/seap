import React, { useMemo, useState } from 'react';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Copy,
  Info,
  XCircle,
} from 'lucide-react';

import type { Stage6Issue, Stage6Result } from '../types/extraction';

type Stage6ContentProps = {
  data: Stage6Result | null;
};

const VerdictBanner: React.FC<{ data: Stage6Result }> = ({ data }) => {
  const status = data.status;
  const reprovacoesCount = data.reprovacoes?.length ?? 0;
  const ressalvasCount = data.ressalvas?.length ?? 0;

  if (status === 'aprovado') {
    return (
      <div className="relative overflow-hidden rounded-2xl border border-emerald-500/60 bg-gradient-to-r from-emerald-700 via-emerald-600 to-emerald-400 px-4 py-3 text-white shadow-md shadow-emerald-700/40">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-900/40">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold tracking-wide">
              APROVADO — Processo apto para prosseguimento
            </p>
            <p className="text-[11px] text-emerald-50/90">
              Nenhuma irregularidade impeditiva foi identificada.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (status === 'aprovado_com_ressalva') {
    return (
      <div className="relative overflow-hidden rounded-2xl border border-amber-500/60 bg-gradient-to-r from-amber-700 via-amber-600 to-amber-400 px-4 py-3 text-amber-50 shadow-md shadow-amber-800/40">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-950/40">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold tracking-wide">
              APROVADO COM RESSALVA
            </p>
            <p className="text-[11px] text-amber-50/90">
              {ressalvasCount > 0
                ? `${ressalvasCount} ressalva(s) identificada(s) que não impedem o prosseguimento.`
                : 'Ressalvas identificadas que não impedem o prosseguimento.'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-2xl border border-rose-500/70 bg-gradient-to-r from-rose-800 via-rose-700 to-rose-500 px-4 py-3 text-rose-50 shadow-md shadow-rose-900/40">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-rose-950/40">
          <XCircle className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-semibold tracking-wide">
            REPROVADO — Irregularidades impedem o andamento
          </p>
          <p className="text-[11px] text-rose-50/90">
            {reprovacoesCount > 0
              ? `${reprovacoesCount} problema(s) impeditivo(s) identificado(s).`
              : 'Foram identificadas irregularidades que impedem o andamento do processo.'}
          </p>
        </div>
      </div>
    </div>
  );
};

const ProblemList: React.FC<{ data: Stage6Result }> = ({ data }) => {
  const reprovacoes = data.reprovacoes ?? [];
  const ressalvas = data.ressalvas ?? [];
  const pendencias = data.pendencias_despachos ?? [];

  if (
    reprovacoes.length === 0 &&
    ressalvas.length === 0 &&
    pendencias.length === 0
  ) {
    return null;
  }

  const renderItem = (issue: Stage6Issue, color: 'red' | 'amber' | 'slate') => {
    const Icon =
      color === 'red' ? XCircle : color === 'amber' ? AlertTriangle : Info;
    const borderColor =
      color === 'red'
        ? 'border-rose-500/60'
        : color === 'amber'
          ? 'border-amber-500/60'
          : 'border-slate-500/40';
    const bgColor =
      color === 'red'
        ? 'bg-rose-500/5'
        : color === 'amber'
          ? 'bg-amber-500/5'
          : 'bg-slate-500/5';
    const textColor =
      color === 'red'
        ? 'text-rose-800 dark:text-rose-100'
        : color === 'amber'
          ? 'text-amber-800 dark:text-amber-100'
          : 'text-slate-800 dark:text-slate-100';

    return (
      <div
        key={`${issue.estagio}-${issue.descricao}-${issue.tipo}`}
        className={`flex flex-col gap-1 rounded-xl border ${borderColor} ${bgColor} px-3 py-2`}
      >
        <div className="flex items-start gap-2">
          <Icon className="mt-0.5 h-4 w-4 flex-shrink-0 text-current" />
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`text-xs font-semibold ${textColor}`}>
                Estágio {issue.estagio}
              </span>
              <span className="rounded-full bg-black/5 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--text-secondary)] dark:bg-white/5">
                {issue.tipo === 'reprovacao'
                  ? 'Reprovação'
                  : issue.tipo === 'ressalva'
                    ? 'Ressalva'
                    : 'Pendência de despacho'}
              </span>
            </div>
            <p className={`mt-0.5 text-xs ${textColor}`}>{issue.descricao}</p>
            {issue.detalhes && (
              <p className="mt-0.5 text-[11px] text-[var(--text-secondary)]">
                {issue.detalhes}
              </p>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-2 rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/40 p-3">
      <p className="text-xs font-medium text-[var(--text-secondary)]">
        Problemas identificados
      </p>
      <div className="space-y-2">
        {reprovacoes.map((i) => renderItem(i, 'red'))}
        {ressalvas.map((i) => renderItem(i, 'amber'))}
        {pendencias.map((i) => renderItem(i, 'slate'))}
      </div>
    </div>
  );
};

const DispatchSection: React.FC<{ data: Stage6Result }> = ({ data }) => {
  const [text, setText] = useState<string>(data.despacho ?? '');
  const [copied, setCopied] = useState(false);

  if (data.status === 'aprovado') {
    return (
      <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-3">
        <p className="text-xs font-medium text-emerald-800 dark:text-emerald-200">
          Processo apto para prosseguimento. Nenhum despacho automático é
          necessário.
        </p>
      </div>
    );
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="space-y-2 rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/40 p-3">
      <div className="mb-1 flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-[var(--text-secondary)]">
          Despacho sugerido
        </p>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-[11px] font-semibold text-emerald-700 shadow-sm shadow-emerald-500/20 transition hover:bg-emerald-500/20 dark:border-emerald-400/50 dark:text-emerald-200"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3" />
              Copiado!
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              Copiar
            </>
          )}
        </button>
      </div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="min-h-[160px] w-full resize-y rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-2 text-xs font-mono leading-relaxed text-[var(--text-primary)] outline-none ring-emerald-500/30 transition focus:border-emerald-500 focus:ring-2"
      />
    </div>
  );
};

const StageSummary: React.FC<{ data: Stage6Result }> = ({ data }) => {
  const status6 = data.status;

  type StageStatus = 'ok' | 'warn' | 'error' | 'info' | 'none';
  type StageChip = {
    label: string;
    desc: string;
    status: StageStatus;
  };

  const hasStage4Reprovacao =
    data.reprovacoes?.some((i) => i.estagio === 4) === true;
  const hasStage4Ressalva =
    data.ressalvas?.some((i) => i.estagio === 4) === true;

  const iconFor = useMemo(
    () =>
      (value: StageStatus): {
        icon: React.ReactNode;
        className: string;
      } => {
        switch (value) {
          case 'ok':
            return {
              icon: <Check className="h-3 w-3" />,
              className:
                'bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-200',
            };
          case 'warn':
            return {
              icon: <AlertTriangle className="h-3 w-3" />,
              className:
                'bg-amber-500/10 text-amber-600 dark:bg-amber-500/20 dark:text-amber-200',
            };
          case 'error':
            return {
              icon: <XCircle className="h-3 w-3" />,
              className:
                'bg-rose-500/10 text-rose-600 dark:bg-rose-500/20 dark:text-rose-200',
            };
          case 'info':
            return {
              icon: <Info className="h-3 w-3" />,
              className:
                'bg-sky-500/10 text-sky-600 dark:bg-sky-500/20 dark:text-sky-200',
            };
          case 'none':
          default:
            return {
              icon: <span className="h-3 w-3" />,
              className:
                'bg-slate-500/10 text-slate-500 dark:bg-slate-500/20 dark:text-slate-300',
            };
        }
      },
    [],
  );

  const chips: StageChip[] = [
    {
      label: 'Estágio 1',
      desc: 'Identificação',
      status: 'ok',
    },
    {
      label: 'Estágio 2',
      desc: 'Análise',
      status: 'info',
    },
    {
      label: 'Estágio 3',
      desc: 'Nota de Crédito',
      status: 'info' as const,
    },
    {
      label: 'Estágio 4',
      desc: 'Documentação',
      status:
        hasStage4Reprovacao ? 'error' : hasStage4Ressalva ? 'warn' : 'ok',
    },
    {
      label: 'Estágio 5',
      desc: 'Despachos',
      status:
          data.pendencias_despachos && data.pendencias_despachos.length > 0
            ? 'info'
            : 'ok',
    },
    {
      label: 'Estágio 6',
      desc: 'Decisão Final',
      status:
        status6 === 'aprovado'
          ? 'ok'
          : status6 === 'aprovado_com_ressalva'
            ? 'warn'
            : 'error',
    },
  ];

  return (
    <div className="space-y-2 rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/40 p-3">
      <p className="text-xs font-medium text-[var(--text-secondary)]">
        Resumo dos estágios
      </p>
      <div className="flex flex-wrap gap-2">
        {chips.map((chip) => {
          const conf = iconFor(chip.status);
          return (
            <div
              key={chip.label}
              className={`flex items-center gap-2 rounded-full px-2.5 py-1 text-[10px] ${conf.className}`}
            >
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-black/5 dark:bg-white/5">
                {conf.icon}
              </span>
              <span className="font-semibold">{chip.label}</span>
              <span className="text-[9px] opacity-80">{chip.desc}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const Stage6Content: React.FC<Stage6ContentProps> = ({ data }) => {
  if (!data) {
    return (
      <p className="text-xs text-[var(--text-secondary)]">
        Nenhum resultado de decisão final disponível.
      </p>
    );
  }

  const confidence = data.confidence?.geral;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <VerdictBanner data={data} />
        {typeof confidence === 'number' && (
          <span className="text-xs text-[var(--text-secondary)]">
            Confiança: {Math.round(confidence)}%
          </span>
        )}
      </div>

      <ProblemList data={data} />
      <DispatchSection data={data} />
      <StageSummary data={data} />
    </div>
  );
};

