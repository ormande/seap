'use client';

import { AlertTriangle, ArrowLeft, Loader2, Timer, Trash2 } from 'lucide-react';
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
import type { AnalyzeFullResult, AnalyzeResult } from '../../../types/extraction';

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
      // Garante que dados_completos seja objeto
      if (typeof data.dados_completos === 'string') {
        try {
          data.dados_completos = JSON.parse(data.dados_completos as string);
        } catch {
          data.dados_completos = {} as unknown as AnalyzeFullResult;
        }
      }
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

  const handleDelete = async () => {
    if (!analysis) return;
    setDeleting(true);
    try {
      await deleteAnalysis(analysis.id);
      setToast('Análise excluída com sucesso');
      setTimeout(() => {
        router.push('/historico');
      }, 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao excluir');
      setDeleting(false);
      setShowDeleteModal(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--accent-primary)]" />
        <p className="text-sm text-[var(--text-secondary)]">Carregando análise...</p>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-rose-500/10 text-rose-500">
          <AlertTriangle className="h-6 w-6" />
        </div>
        <p className="text-sm text-[var(--text-secondary)]">
          {error || 'Análise não encontrada'}
        </p>
        <Link
          href="/historico"
          className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] px-4 py-2 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Voltar ao histórico
        </Link>
      </div>
    );
  }

  const result = analysis.dados_completos as unknown as AnalyzeResult;
  const stage1 = result.stages?.stage1;
  const stage2 = result.stages?.stage2 ?? null;
  const stage3 = result.stages?.stage3 ?? null;
  const stage4 = result.stages?.stage4 ?? null;
  const stage5 = result.stages?.stage5 ?? null;
  const stage6 = result.stages?.stage6 ?? null;
  const metadata = result.metadata ?? { total_paginas: 0, paginas_com_texto: 0 };

  const hasStage4Reprovacao =
    stage6?.reprovacoes?.some((i: { estagio?: number }) => i.estagio === 4) === true;
  const hasStage4Ressalva =
    stage6?.ressalvas?.some((i: { estagio?: number }) => i.estagio === 4) === true;
  const stage4StatusOverride: 'ok' | 'warn' | 'error' | 'none' =
    hasStage4Reprovacao ? 'error' : hasStage4Ressalva ? 'warn' : 'ok';

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
                onClick={handleDelete}
                disabled={deleting}
                className="rounded-lg border border-rose-500/60 bg-rose-500/10 px-3 py-1.5 text-xs font-semibold text-rose-700 transition hover:bg-rose-500/20 disabled:opacity-50 dark:text-rose-200"
              >
                {deleting ? 'Excluindo...' : 'Excluir'}
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
            <Stage2Content
              data={stage2.data}
              confidence={stage2.confidence}
              onUasgNomeAdded={(codigo, nome) => {
                setAnalysis((prev) => {
                  if (!prev?.dados_completos?.stages?.stage2?.data) return prev;
                  return {
                    ...prev,
                    dados_completos: {
                      ...prev.dados_completos,
                      stages: {
                        ...prev.dados_completos.stages,
                        stage2: {
                          ...prev.dados_completos.stages.stage2,
                          data: {
                            ...prev.dados_completos.stages.stage2.data,
                            uasg: { codigo, nome },
                          },
                        },
                      },
                    },
                  };
                });
              }}
            />
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
          statusOverride={stage4 ? stage4StatusOverride : 'none'}
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
