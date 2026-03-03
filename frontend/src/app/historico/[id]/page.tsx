'use client';

import { ArrowLeft, Timer, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import React, { useCallback, useEffect, useState } from 'react';

import { StageCard } from '../../../components/analysis/StageCard';
import { Stage1Content } from '../../../components/analysis/Stage1Content';
import { Stage2Content } from '../../../components/analysis/Stage2Content';
import { Stage3Content } from '../../../components/analysis/Stage3Content';
import { Stage4Content } from '../../../components/analysis/Stage4Content';
import { Stage5Content } from '../../../components/analysis/Stage5Content';
import { Stage6Content } from '../../../components/Stage6Content';
import {
  deleteAnalysis,
  getAnalysisById,
  type AnalysisFull,
} from '../../../lib/api';
import type { AnalyzeResult } from '../../../types/extraction';

function formatTimer(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '—';
    return new Intl.DateTimeFormat('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d);
  } catch {
    return '—';
  }
}

export default function HistoricoDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = typeof params.id === 'string' ? params.id : '';
  const [analysis, setAnalysis] = useState<AnalysisFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getAnalysisById(id);
      setAnalysis(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar análise');
      setAnalysis(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (!id) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">ID não informado.</p>
        <Link
          href="/historico"
          className="inline-flex items-center gap-2 text-sm font-medium text-emerald-600 dark:text-emerald-400"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar ao histórico
        </Link>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-sm text-[var(--text-secondary)]">Carregando análise...</p>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-rose-600 dark:text-rose-400">{error ?? 'Análise não encontrada.'}</p>
        <Link
          href="/historico"
          className="inline-flex items-center gap-2 text-sm font-medium text-emerald-600 dark:text-emerald-400"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar ao histórico
        </Link>
      </div>
    );
  }

  const result = analysis.dados_completos as unknown as AnalyzeResult;
  const stage1 = result.stages?.stage1;
  const stage2 = (result.stages?.stage2 as any) ?? null;
  const stage3 = (result.stages?.stage3 as any) ?? null;
  const stage4 = (result.stages?.stage4 as any) ?? null;
  const stage5 = (result.stages?.stage5 as any) ?? null;
  const stage6 = (result.stages?.stage6 as any) ?? null;
  const metadata = result.metadata ?? { total_paginas: 0, paginas_com_texto: 0 };

  return (
    <div className="space-y-4">
      {toast && (
        <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-xl border border-emerald-500/40 bg-emerald-500/90 px-4 py-2 text-sm font-medium text-white shadow-lg dark:bg-emerald-600/95">
          {toast}
        </div>
      )}

      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4 shadow-xl">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              Excluir análise?
            </h2>
            <p className="mt-2 text-xs text-[var(--text-secondary)]">
              A análise do NUP{' '}
              <span className="font-semibold">
                {analysis?.nup ?? '—'}
              </span>{' '}
              será removida permanentemente.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowDeleteModal(false)}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-main)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] transition hover:bg-[var(--bg-main)]/80"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!analysis || deleting) return;
                  setDeleting(true);
                  try {
                    await deleteAnalysis(analysis.id);
                    setToast('Análise excluída');
                    setTimeout(() => {
                      setToast(null);
                      router.push('/historico');
                    }, 2000);
                  } catch (e) {
                    setToast(
                      e instanceof Error
                        ? e.message
                        : 'Erro ao excluir análise',
                    );
                    setTimeout(() => setToast(null), 2500);
                    setDeleting(false);
                  }
                }}
                className="rounded-lg border border-rose-500/60 bg-rose-500/10 px-3 py-1.5 text-xs font-semibold text-rose-700 transition hover:bg-rose-500/20 dark:text-rose-200"
              >
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/historico"
          className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-primary)] transition hover:bg-[var(--bg-main)]"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar ao histórico
        </Link>
        <button
          type="button"
          onClick={() => setShowDeleteModal(true)}
          className="inline-flex items-center gap-2 rounded-lg border border-rose-500/60 bg-transparent px-3 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-500/10 dark:text-rose-300"
        >
          <Trash2 className="h-4 w-4" />
          Excluir análise
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
        <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
          <Timer className="h-4 w-4" />
          <span>Tempo de análise: {formatTimer(analysis.tempo_analise ?? 0)}</span>
        </div>
        <div className="text-xs text-[var(--text-secondary)]">
          Data: {formatDate(analysis.data_analise)}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-[var(--text-secondary)]">
            Resultado da análise
          </p>
          <p className="text-sm text-[var(--text-secondary)]">
            {metadata.total_paginas} página(s), {metadata.paginas_com_texto} com texto extraído.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        <StageCard
          title="Estágio 1 — Identificação"
          subtitle="NUP, Requisição e OM a partir da primeira página"
          confidence={stage1?.confidence?.geral ?? null}
          defaultOpen
        >
          <Stage1Content
            data={stage1?.data}
            confidence={stage1?.confidence}
            method={stage1?.method}
          />
        </StageCard>

        <StageCard
          title="Estágio 2 — Análise"
          subtitle="Análise da peça da requisição (instrumento, UASG, fornecedor e itens)"
          confidence={stage2?.confidence?.geral ?? null}
          defaultOpen={false}
        >
          {stage2?.data ? (
            <Stage2Content data={stage2.data} confidence={stage2.confidence} />
          ) : (
            <p className="text-xs text-[var(--text-secondary)]">
              Não foi possível identificar a peça da requisição neste PDF.
            </p>
          )}
        </StageCard>

        <StageCard
          title="Estágio 3 — Nota de Crédito"
          subtitle="Notas de Crédito (NC) vinculadas ao processo"
          confidence={stage3?.ncs?.[0]?.confidence?.geral ?? null}
          defaultOpen={false}
        >
          {stage3?.ncs?.length ? (
            <Stage3Content data={stage3} />
          ) : (
            <p className="text-xs text-[var(--text-secondary)]">
              Nenhuma Nota de Crédito foi identificada neste PDF.
            </p>
          )}
        </StageCard>

        <StageCard
          title="Estágio 4 — Documentação"
          subtitle="CADIN, TCU, SICAF e cruzamento de CNPJ"
          confidence={stage4?.confidence?.geral ?? null}
          defaultOpen={false}
        >
          {stage4 ? (
            <Stage4Content data={stage4} />
          ) : (
            <p className="text-xs text-[var(--text-secondary)]">Nenhum resultado do Estágio 4.</p>
          )}
        </StageCard>

        <StageCard
          title="Estágio 5 — Despachos"
          subtitle="Encaminhamentos, exigências e pendências dos despachos"
          confidence={stage5?.confidence?.geral ?? null}
          defaultOpen={false}
        >
          {stage5 ? (
            <Stage5Content data={stage5} />
          ) : (
            <p className="text-xs text-[var(--text-secondary)]">Nenhum resultado do Estágio 5.</p>
          )}
        </StageCard>

        <StageCard
          title="Estágio 6 — Decisão Final"
          subtitle="Veredicto consolidado e despacho sugerido"
          confidence={stage6?.confidence?.geral ?? null}
          defaultOpen={false}
        >
          {stage6 ? (
            <Stage6Content data={stage6} />
          ) : (
            <p className="text-xs text-[var(--text-secondary)]">Nenhum resultado do Estágio 6.</p>
          )}
        </StageCard>
      </div>
    </div>
  );
}
