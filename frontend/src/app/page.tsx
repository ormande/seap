'use client';

import {
  AlertCircle,
  Download,
  Save,
  Timer,
  Trash2,
  XCircle,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import React, { useCallback, useEffect, useRef, useState } from 'react';

import { StageCard } from '../components/analysis/StageCard';
import { Stage1Content } from '../components/analysis/Stage1Content';
import { Stage2Content } from '../components/analysis/Stage2Content';
import { Stage3Content } from '../components/analysis/Stage3Content';
import { Stage4Content } from '../components/analysis/Stage4Content';
import { Stage5Content } from '../components/analysis/Stage5Content';
import { Stage6Content } from '../components/Stage6Content';
import { PdfUpload } from '../components/upload/PdfUpload';
import { Toast } from '../components/Toast';
import { fetchAPI, saveAnalysis } from '../lib/api';
import type { AnalyzeFullResult, AnalyzeResult } from '../types/extraction';

function formatTimer(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/** Modal de confirmação genérico */
function ConfirmModal({
  open,
  title,
  children,
  cancelLabel,
  confirmLabel,
  confirmVariant,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  title: string;
  children: React.ReactNode;
  cancelLabel: string;
  confirmLabel: string;
  confirmVariant: 'green' | 'red';
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div
        className="w-full max-w-md rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4 shadow-xl transition-all duration-200 ease-out"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="modal-title" className="text-sm font-semibold text-[var(--text-primary)]">
          {title}
        </h2>
        <div className="mt-2 text-xs text-[var(--text-secondary)]">{children}</div>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-main)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] transition hover:bg-[var(--bg-main)]/80"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={
              confirmVariant === 'green'
                ? 'rounded-lg border border-emerald-500/40 bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-600'
                : 'rounded-lg border border-rose-500/60 bg-rose-500/10 px-3 py-1.5 text-xs font-semibold text-rose-700 transition hover:bg-rose-500/20 dark:text-rose-200'
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [fullResult, setFullResult] = useState<AnalyzeFullResult | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [progress, setProgress] = useState(0);
  const [phaseMessage, setPhaseMessage] = useState<string>('Iniciando análise...');
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [showDiscardModal, setShowDiscardModal] = useState(false);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const startTimer = useCallback(() => {
    setElapsedSeconds(0);
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setElapsedSeconds((s) => s + 1);
    }, 1000);
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (isProcessing) startTimer();
    else stopTimer();
    return () => stopTimer();
  }, [isProcessing, startTimer, stopTimer]);

  const resetState = () => {
    setIsProcessing(false);
    setResult(null);
    setFullResult(null);
    setError(null);
    setElapsedSeconds(0);
    setProgress(0);
    setPhaseMessage('Iniciando análise...');
    abortControllerRef.current = null;
  };

  const handleFileSelected = async (file: File) => {
    setError(null);
    setResult(null);
    setFullResult(null);
    setProgress(0);
    setPhaseMessage('Enviando arquivo para análise...');
    setIsProcessing(true);

    const formData = new FormData();
    formData.append('file', file);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetchAPI('/api/analyze', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
        headers: {
          Accept: 'text/event-stream',
        },
      });

      if (!response.ok || !response.body) {
        const text = await response.text().catch(() => '');
        throw new Error(
          `Erro na análise (status ${response.status}): ${
            text || response.statusText
          }`,
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // Loop de leitura do stream SSE.
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() ?? '';

        for (const event of events) {
          const line = event
            .split('\n')
            .find((l) => l.startsWith('data: '));
          if (!line) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (typeof data.progress === 'number') {
              setProgress((prev) =>
                data.progress > prev ? data.progress : prev,
              );
            }
            if (typeof data.message === 'string') {
              setPhaseMessage(data.message);
            }
            if (data.phase === 'complete' && data.result) {
              // result: summary enxuto para uso na UI e download padrão.
              setResult(data.result as AnalyzeResult);
              setFullResult((data.full as AnalyzeFullResult | undefined) ?? null);
              setIsProcessing(false);
            }
            if (data.phase === 'error') {
              setError(
                typeof data.message === 'string'
                  ? data.message
                  : 'Erro ao analisar o PDF.',
              );
              setIsProcessing(false);
            }
          } catch {
            // Ignora eventos malformados.
          }
        }
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') {
        // Cancelamento pelo usuário: apenas reseta estado.
        resetState();
        return;
      }
      console.error(e);
      setError(
        e instanceof Error
          ? e.message
          : 'Erro inesperado ao processar o PDF. Verifique o backend.',
      );
      setIsProcessing(false);
    } finally {
      abortControllerRef.current = null;
    }
  };

  const handleSaveConfirm = async () => {
    if (!result) return;
    setShowSaveModal(false);
    try {
      await saveAnalysis(
        fullResult ?? ({ ...result, extraction: {} } as AnalyzeFullResult),
        elapsedSeconds,
      );
      setToast('Análise salva com sucesso');
      // Toast controla a animação de saída e o fechamento; após fechar limpamos o estado.
    } catch (e) {
      setToast(e instanceof Error ? e.message : 'Erro ao salvar');
    }
  };

  const handleDiscardConfirm = () => {
    setShowDiscardModal(false);
    resetState();
  };

  const handleCancelConfirm = () => {
    setShowCancelModal(false);
    abortControllerRef.current?.abort();
  };

  const handleExport = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `relatorio-licitacao-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isProcessing) {
    return (
      <div className="space-y-4">
        <ConfirmModal
          open={showCancelModal}
          title="Cancelar análise?"
          cancelLabel="Voltar"
          confirmLabel="Cancelar análise"
          confirmVariant="red"
          onCancel={() => setShowCancelModal(false)}
          onConfirm={handleCancelConfirm}
        >
          Cancelar agora irá interromper o processamento e o progresso será
          perdido.
        </ConfirmModal>

        <div className="flex items-center justify-between gap-3 text-sm text-[var(--text-secondary)]">
          <div className="flex items-center gap-1.5">
            <Timer className="h-4 w-4" />
            <span className="font-mono tabular-nums">
              {formatTimer(elapsedSeconds)}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setShowCancelModal(true)}
            className="inline-flex items-center gap-1 rounded-lg border border-rose-500/60 bg-transparent px-3 py-1 text-xs font-semibold text-rose-600 transition hover:bg-rose-500/10 dark:text-rose-300"
          >
            <XCircle className="h-3 w-3" />
            Cancelar análise
          </button>
        </div>

        <div className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] px-6 py-8 shadow-sm shadow-black/5 dark:shadow-none">
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-[var(--text-secondary)]">
            Progresso da análise
          </p>
          <p className="mt-2 text-sm font-medium text-[var(--text-primary)] animate-pulse">
            {phaseMessage}
          </p>
          <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-emerald-500/10">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-emerald-500 to-emerald-600 transition-[width] duration-500 ease-out"
              style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
            />
          </div>
          <p className="mt-2 text-xs font-mono tabular-nums text-[var(--text-secondary)]">
            {Math.round(progress)}%
          </p>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-6 shadow-sm shadow-black/5 dark:shadow-none">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                Enviar PDF de requisição
              </h2>
              <p className="text-[11px] text-[var(--text-secondary)]">
                Envie um PDF de requisição para iniciar o Estágio 1 de
                identificação do processo.
              </p>
            </div>
          </div>

          <PdfUpload onFileSelected={handleFileSelected} disabled={isProcessing} />

          {error && (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800 dark:border-rose-500/80 dark:bg-rose-950/40 dark:text-rose-100">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <p>{error}</p>
            </div>
          )}

          {!error && (
            <p className="mt-3 text-[11px] text-[var(--text-secondary)]">
              Apenas PDFs de requisições são suportados neste estágio. Após o
              upload, o sistema identificará automaticamente NUP, requisição e
              OM da primeira página.
            </p>
          )}
        </div>
      </div>
    );
  }

  const stage1 = result.stages.stage1;
  const stage2 = (result.stages.stage2 as any) ?? null;
  const stage3 = (result.stages.stage3 as any) ?? null;
  const stage4 = (result.stages.stage4 as any) ?? null;
  const stage5 = (result.stages.stage5 as any) ?? null;
  const stage6 = (result.stages.stage6 as any) ?? null;

  const hasStage4Reprovacao =
    stage6?.reprovacoes?.some((i: any) => i.estagio === 4) === true;
  const hasStage4Ressalva =
    stage6?.ressalvas?.some((i: any) => i.estagio === 4) === true;
  const stage4StatusOverride: 'ok' | 'warn' | 'error' | 'none' =
    hasStage4Reprovacao ? 'error' : hasStage4Ressalva ? 'warn' : 'ok';

  return (
    <div className="space-y-4">
      {toast && (
        <Toast
          message={toast}
          durationMs={3000}
          onClose={() => {
            // Após o toast sumir, limpamos o estado e voltamos para a tela inicial
            if (toast === 'Análise salva com sucesso') {
              resetState();
              router.push('/');
            }
            setToast(null);
          }}
        />
      )}

      <ConfirmModal
        open={showSaveModal}
        title="Salvar análise?"
        cancelLabel="Cancelar"
        confirmLabel="Salvar"
        confirmVariant="green"
        onCancel={() => setShowSaveModal(false)}
        onConfirm={handleSaveConfirm}
      >
        A análise será salva no histórico e poderá ser consultada posteriormente.
      </ConfirmModal>

      <ConfirmModal
        open={showDiscardModal}
        title="Descartar análise?"
        cancelLabel="Cancelar"
        confirmLabel="Descartar"
        confirmVariant="red"
        onCancel={() => setShowDiscardModal(false)}
        onConfirm={handleDiscardConfirm}
      >
        Todos os dados extraídos serão perdidos. Esta ação não pode ser desfeita.
      </ConfirmModal>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-[var(--text-secondary)]">
              Resultado da análise
            </p>
            <p className="text-sm text-[var(--text-secondary)]">
              {result.metadata.total_paginas} página(s),{' '}
              {result.metadata.paginas_com_texto} com texto extraído.
            </p>
          </div>
          <div className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)]">
            <Timer className="h-4 w-4" />
            <span className="font-mono tabular-nums">{formatTimer(elapsedSeconds)}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={handleExport}
          className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/20 bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-white shadow-sm shadow-emerald-500/40 transition hover:bg-emerald-600"
        >
          <Download className="h-3 w-3" />
          Exportar JSON
        </button>
      </div>

      <div className="space-y-3">
        <StageCard
          title="Estágio 1 — Identificação"
          subtitle="NUP, Requisição e OM a partir da primeira página"
          confidence={stage1.confidence?.geral ?? null}
          defaultOpen
        >
          <Stage1Content
            data={stage1.data}
            confidence={stage1.confidence}
            method={stage1.method}
          />
        </StageCard>

        <StageCard
          title="Estágio 2 — Análise"
          subtitle="Análise da peça da requisição (instrumento, UASG, fornecedor e itens)"
          confidence={stage2?.confidence?.geral ?? null}
          defaultOpen={false}
        >
          {stage2 && stage2.data ? (
            <Stage2Content
              data={stage2.data}
              confidence={stage2.confidence}
              onUasgNomeAdded={(codigo, nome) => {
                setResult((prev) => {
                  if (!prev?.stages?.stage2?.data) return prev;
                  return {
                    ...prev,
                    stages: {
                      ...prev.stages,
                      stage2: {
                        ...prev.stages.stage2,
                        data: {
                          ...prev.stages.stage2.data,
                          uasg: { codigo, nome },
                        },
                      },
                    },
                  };
                });
                setFullResult((prev) => {
                  if (!prev?.stages?.stage2?.data) return prev;
                  return {
                    ...prev,
                    stages: {
                      ...prev.stages,
                      stage2: {
                        ...prev.stages.stage2,
                        data: {
                          ...prev.stages.stage2.data,
                          uasg: { codigo, nome },
                        },
                      },
                    },
                  };
                });
              }}
            />
          ) : (
            <p className="text-xs text-[var(--text-secondary)]">
              Não foi possível identificar a peça da requisição neste PDF ou o
              Estágio 2 ainda não retornou dados suficientes.
            </p>
          )}
        </StageCard>
        <StageCard
          title="Estágio 3 — Nota de Crédito"
          subtitle="Notas de Crédito (NC) vinculadas ao processo"
          confidence={stage3?.ncs?.[0]?.confidence?.geral ?? null}
          defaultOpen={false}
        >
          {stage3 && stage3.ncs && stage3.ncs.length > 0 ? (
            <Stage3Content data={stage3} />
          ) : (
            <p className="text-xs text-[var(--text-secondary)]">
              Nenhuma Nota de Crédito foi identificada neste PDF ou o Estágio 3
              ainda não retornou dados suficientes.
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
            <p className="text-xs text-[var(--text-secondary)]">
              Nenhum resultado do Estágio 4 disponível.
            </p>
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
            <p className="text-xs text-[var(--text-secondary)]">
              Nenhum resultado do Estágio 5 disponível.
            </p>
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
            <p className="text-xs text-[var(--text-secondary)]">
              Nenhum resultado do Estágio 6 disponível.
            </p>
          )}
        </StageCard>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-[var(--border-subtle)] pt-4">
        <button
          type="button"
          onClick={() => setShowSaveModal(true)}
          className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-600"
        >
          <Save className="h-4 w-4" />
          Salvar análise
        </button>
        <button
          type="button"
          onClick={() => setShowDiscardModal(true)}
          className="inline-flex items-center gap-2 rounded-lg border border-rose-500/60 bg-transparent px-4 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-500/10 dark:text-rose-400"
        >
          <Trash2 className="h-4 w-4" />
          Descartar análise
        </button>
      </div>
    </div>
  );
}
