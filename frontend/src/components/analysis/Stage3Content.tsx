import React, { useState } from 'react';

import type {
  Stage3Destination,
  Stage3NC,
  Stage3NDCrossItem,
  Stage3Result,
} from '../../types/extraction';
import { ConfidenceBadge } from './ConfidenceBadge';

type Stage3ContentProps = {
  data: Stage3Result | null;
};

const formatCurrencyBRL = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
};

const formatFormatoLabel = (fmt: string | null): string => {
  if (!fmt) return 'Desconhecido';
  if (fmt === 'image_siafi') return 'EXTRAÍDO POR IA (IMAGEM)';
  if (fmt.startsWith('siafi')) return 'SIAFI';
  if (fmt.startsWith('web')) return 'Web';
  return fmt;
};

const DestinosTable: React.FC<{ destinos: Stage3Destination[] }> = ({ destinos }) => {
  const total = destinos.reduce((acc, d) => acc + (d.valor ?? 0), 0);

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border-subtle)]/80">
      <div className="max-h-80 overflow-auto">
        <table className="min-w-full border-collapse text-xs">
          <thead className="bg-[var(--bg-main)]/60">
            <tr>
              <th className="border-b border-[var(--border-subtle)] px-2 py-1 text-left text-[11px] font-semibold text-[var(--text-secondary)]">
                Esfera
              </th>
              <th className="border-b border-[var(--border-subtle)] px-2 py-1 text-left text-[11px] font-semibold text-[var(--text-secondary)]">
                PTRES
              </th>
              <th className="border-b border-[var(--border-subtle)] px-2 py-1 text-left text-[11px] font-semibold text-[var(--text-secondary)]">
                Fonte
              </th>
              <th className="border-b border-[var(--border-subtle)] px-2 py-1 text-left text-[11px] font-semibold text-[var(--text-secondary)]">
                ND
              </th>
              <th className="border-b border-[var(--border-subtle)] px-2 py-1 text-left text-[11px] font-semibold text-[var(--text-secondary)]">
                UGR
              </th>
              <th className="border-b border-[var(--border-subtle)] px-2 py-1 text-left text-[11px] font-semibold text-[var(--text-secondary)]">
                PI
              </th>
              <th className="border-b border-[var(--border-subtle)] px-2 py-1 text-right text-[11px] font-semibold text-[var(--text-secondary)]">
                Valor
              </th>
              <th className="border-b border-[var(--border-subtle)] px-2 py-1 text-right text-[11px] font-semibold text-[var(--text-secondary)]">
                Evento
              </th>
            </tr>
          </thead>
          <tbody>
            {destinos.map((d, idx) => (
              <tr
                key={idx}
                className={[
                  'transition-colors',
                  idx % 2 === 0
                    ? 'bg-[var(--bg-main)]/40'
                    : 'bg-[var(--bg-main)]/20',
                  'hover:bg-emerald-500/5',
                ].join(' ')}
              >
                <td className="border-b border-[var(--border-subtle)]/60 px-2 py-1 align-top text-[11px] text-[var(--text-primary)]">
                  {d.esfera ?? '—'}
                </td>
                <td className="border-b border-[var(--border-subtle)]/60 px-2 py-1 align-top text-[11px] text-[var(--text-primary)]">
                  {d.ptres ?? '—'}
                </td>
                <td className="border-b border-[var(--border-subtle)]/60 px-2 py-1 align-top text-[11px] text-[var(--text-primary)]">
                  {d.fonte ?? '—'}
                </td>
                <td className="border-b border-[var(--border-subtle)]/60 px-2 py-1 align-top text-[11px] text-[var(--text-primary)]">
                  {d.nd ?? '—'}
                </td>
                <td className="border-b border-[var(--border-subtle)]/60 px-2 py-1 align-top text-[11px] text-[var(--text-primary)]">
                  {d.ugr ?? '—'}
                </td>
                <td className="border-b border-[var(--border-subtle)]/60 px-2 py-1 align-top text-[11px] text-[var(--text-primary)]">
                  {d.pi ?? '—'}
                </td>
                <td className="border-b border-[var(--border-subtle)]/60 px-2 py-1 text-right align-top text-[11px] text-[var(--text-primary)]">
                  <span className="tabular-nums font-medium">
                    {formatCurrencyBRL(d.valor)}
                  </span>
                </td>
                <td className="border-b border-[var(--border-subtle)]/60 px-2 py-1 text-right align-top text-[11px] text-[var(--text-secondary)]">
                  {d.evento ? (
                    <span className="inline-flex items-center rounded-full bg-slate-500/10 px-2 py-0.5 text-[10px] font-semibold text-slate-700 dark:bg-slate-500/20 dark:text-slate-200">
                      Evento {d.evento}
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            ))}
          </tbody>
          {destinos.length > 0 && (
            <tfoot>
              <tr>
                <td
                  colSpan={6}
                  className="px-2 py-2 text-right text-[11px] font-semibold text-[var(--text-secondary)]"
                >
                  Total
                </td>
                <td className="px-2 py-2 text-right text-[11px] font-semibold text-emerald-700 dark:text-emerald-200">
                  {formatCurrencyBRL(total)}
                </td>
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
};

const DestinoSingle: React.FC<{ destino: Stage3Destination }> = ({ destino }) => {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div>
        <p className="text-xs font-medium text-[var(--text-secondary)]">Esfera</p>
        <p className="mt-1 text-sm text-[var(--text-primary)]">
          {destino.esfera ?? '—'}
        </p>
      </div>
      <div>
        <p className="text-xs font-medium text-[var(--text-secondary)]">PTRES</p>
        <p className="mt-1 text-sm text-[var(--text-primary)]">
          {destino.ptres ?? '—'}
        </p>
      </div>
      <div>
        <p className="text-xs font-medium text-[var(--text-secondary)]">Fonte</p>
        <p className="mt-1 text-sm text-[var(--text-primary)]">
          {destino.fonte ?? '—'}
        </p>
      </div>
      <div>
        <p className="text-xs font-medium text-[var(--text-secondary)]">ND</p>
        <p className="mt-1 text-sm text-[var(--text-primary)]">
          {destino.nd ?? '—'}
        </p>
      </div>
      <div>
        <p className="text-xs font-medium text-[var(--text-secondary)]">UGR</p>
        <p className="mt-1 text-sm text-[var(--text-primary)]">
          {destino.ugr ?? '—'}
        </p>
      </div>
      <div>
        <p className="text-xs font-medium text-[var(--text-secondary)]">PI</p>
        <p className="mt-1 text-sm text-[var(--text-primary)]">
          {destino.pi ?? '—'}
        </p>
      </div>
      <div className="md:col-span-2">
        <p className="text-xs font-medium text-[var(--text-secondary)]">Valor</p>
        <p className="mt-1 text-sm font-semibold text-emerald-600 dark:text-emerald-300">
          {formatCurrencyBRL(destino.valor)}
        </p>
      </div>
    </div>
  );
};

export const Stage3Content: React.FC<Stage3ContentProps> = ({ data }) => {
  const ncs: Stage3NC[] = data?.ncs ?? [];
  const [activeIdx, setActiveIdx] = useState(0);

  if (!data || ncs.length === 0) {
    return (
      <p className="text-xs text-[var(--text-secondary)]">
        Nenhuma Nota de Crédito foi identificada neste PDF.
      </p>
    );
  }

  const activeNc = ncs[Math.min(activeIdx, ncs.length - 1)];
  const ndCross = data?.nd_crosscheck ?? null;
  const ndInconsistencias: Stage3NDCrossItem[] = ndCross?.inconsistencias ?? [];
  const ndCruzamentos: Stage3NDCrossItem[] = ndCross?.cruzamentos ?? [];
  const ndTodosCompativeis = ndCross?.todos_compativeis ?? false;

  return (
    <div className="space-y-4">
      {ncs.length > 1 && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/40 p-1">
          {ncs.map((nc, idx) => {
            const isActive = idx === activeIdx;
            const label = nc.numero_nc
              ? nc.numero_nc
              : `NC ${idx + 1}`;
            return (
              <button
                key={idx}
                type="button"
                onClick={() => setActiveIdx(idx)}
                className={[
                  'rounded-lg px-3 py-1 text-xs font-medium transition',
                  isActive
                    ? 'bg-emerald-500 text-white shadow-sm shadow-emerald-500/40'
                    : 'bg-transparent text-[var(--text-secondary)] hover:bg-emerald-500/10',
                ].join(' ')}
              >
                {label}
              </button>
            );
          })}
        </div>
      )}

      {/* Seção superior: dados gerais da NC ativa */}
      <div className="space-y-3 rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/40 p-3">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-medium text-[var(--text-secondary)]">
                Número da NC
              </p>
              <p className="mt-1 text-sm text-[var(--text-primary)]">
                {activeNc.numero_nc ?? 'Não identificado'}
              </p>
            </div>
            <ConfidenceBadge value={activeNc.confidence?.geral ?? null} />
          </div>

          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-medium text-[var(--text-secondary)]">
                UG Emitente
              </p>
              <p className="mt-1 text-sm text-[var(--text-primary)]">
                {activeNc.ug_emitente ?? 'Não identificado'}
              </p>
            </div>
          </div>

          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-medium text-[var(--text-secondary)]">
                Valor total
              </p>
              <p className="mt-1 text-base font-semibold text-emerald-600 dark:text-emerald-300">
                {formatCurrencyBRL(activeNc.valor_total ?? null)}
              </p>
            </div>
          </div>

          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-medium text-[var(--text-secondary)]">
                Formato detectado
              </p>
              <p className="mt-1 text-sm">
                <span className="inline-flex items-center rounded-full bg-slate-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-700 dark:bg-slate-500/20 dark:text-slate-200">
                  {formatFormatoLabel(activeNc.formato_detectado ?? null)}
                </span>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Seção central: destinos */}
      <div className="space-y-3 rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/40 p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-medium text-[var(--text-secondary)]">
            Destinos do crédito (NDs)
          </p>
          <span className="text-[11px] text-[var(--text-secondary)]">
            {activeNc.destinos.length > 0
              ? `${activeNc.destinos.length} destino(s) encontrados`
              : 'Nenhum destino identificado'}
          </span>
        </div>

        {activeNc.destinos.length > 1 ? (
          <DestinosTable destinos={activeNc.destinos} />
        ) : activeNc.destinos.length === 1 ? (
          <DestinoSingle destino={activeNc.destinos[0]} />
        ) : (
          <p className="text-[11px] text-[var(--text-secondary)]">
            Não foi possível identificar os destinos de crédito desta Nota de
            Crédito.
          </p>
        )}
      </div>

      {/* Seção inferior: avisos */}
      <div className="space-y-2 rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/40 p-3">
        <div className="flex flex-wrap items-center gap-2">
          {activeNc.campos_faltantes.length > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-3 py-1 text-[11px] font-semibold text-amber-800 dark:bg-amber-500/20 dark:text-amber-100">
              Campos incompletos:{' '}
              <span className="font-normal">
                {activeNc.campos_faltantes.join(', ')}
              </span>
            </span>
          )}

          {activeNc.complementado_pela_requisicao && (
            <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/10 px-3 py-1 text-[11px] font-semibold text-sky-700 dark:bg-sky-500/20 dark:text-sky-100">
              Dados complementados pela requisição
            </span>
          )}
        </div>

        {/* Cruzamento ND × Itens */}
        <div className="mt-2 space-y-2">
          {ndCross ? (
            ndTodosCompativeis || ndInconsistencias.length === 0 ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-3 py-1 text-[11px] font-semibold text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-100">
                <span className="text-xs">✓</span>
                ND compatível com todos os itens analisados
              </span>
            ) : (
              <div className="rounded-lg border border-amber-400/70 bg-amber-50/80 p-2 text-[11px] text-amber-900 shadow-sm dark:border-amber-300/60 dark:bg-amber-900/20 dark:text-amber-50">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-amber-500/20 text-[10px] font-bold text-amber-800 dark:bg-amber-400/30 dark:text-amber-50">
                      !
                    </span>
                    <p className="font-semibold">
                      Inconsistências de ND entre a NC e os itens da requisição
                    </p>
                  </div>
                  <span className="text-[10px] text-amber-900/80 dark:text-amber-100/80">
                    {ndInconsistencias.length}{' '}
                    {ndInconsistencias.length === 1 ? 'item com alerta' : 'itens com alerta'}
                  </span>
                </div>

                <div className="mt-2 max-h-56 overflow-auto rounded-md border border-amber-200/70 bg-white/70 text-[11px] dark:border-amber-400/40 dark:bg-amber-950/40">
                  <table className="min-w-full border-collapse">
                    <thead className="bg-amber-100/80 text-[10px] uppercase tracking-wide text-amber-900 dark:bg-amber-900/60 dark:text-amber-50/90">
                      <tr>
                        <th className="border-b border-amber-200 px-2 py-1 text-left">Item</th>
                        <th className="border-b border-amber-200 px-2 py-1 text-left">
                          Descrição
                        </th>
                        <th className="border-b border-amber-200 px-2 py-1 text-left">ND NC</th>
                        <th className="border-b border-amber-200 px-2 py-1 text-left">
                          ND Requisição
                        </th>
                        <th className="border-b border-amber-200 px-2 py-1 text-left">
                          Classificação IA
                        </th>
                        <th className="border-b border-amber-200 px-2 py-1 text-left">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ndCruzamentos.map((row, idx) => {
                        const isInconsistent =
                          row.compativel === false ||
                          row.nd_nc_compativel === false ||
                          row.nd_req_compativel === false;

                        return (
                          <tr
                            key={`${row.item ?? idx}-${row.nd_nc ?? 'nd'}-${idx}`}
                            className={[
                              'transition-colors',
                              idx % 2 === 0 ? 'bg-amber-50/70' : 'bg-amber-50/30',
                              isInconsistent ? 'bg-amber-100/90' : '',
                            ].join(' ')}
                          >
                            <td className="border-b border-amber-100 px-2 py-1 align-top text-[11px] font-medium text-amber-900">
                              {row.item ?? '—'}
                            </td>
                            <td className="border-b border-amber-100 px-2 py-1 align-top text-[11px] text-amber-900">
                              <span
                                className="line-clamp-2"
                                title={row.descricao ?? undefined}
                              >
                                {row.descricao ?? '—'}
                              </span>
                            </td>
                            <td className="border-b border-amber-100 px-2 py-1 align-top text-[11px] text-amber-900">
                              {row.nd_nc ?? '—'}
                            </td>
                            <td className="border-b border-amber-100 px-2 py-1 align-top text-[11px] text-amber-900">
                              {row.nd_req ?? '—'}
                            </td>
                            <td
                              className="border-b border-amber-100 px-2 py-1 align-top text-[11px] text-amber-900"
                              title={row.nome_subelemento ?? undefined}
                            >
                              {row.classificacao_label ?? '—'}
                            </td>
                            <td
                              className="border-b border-amber-100 px-2 py-1 align-top text-[11px]"
                              title={row.justificativa ?? undefined}
                            >
                              {isInconsistent ? (
                                <span className="inline-flex items-center rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-800 dark:bg-amber-500/30 dark:text-amber-50">
                                  ⚠ ND possivelmente inadequada
                                </span>
                              ) : (
                                <span className="inline-flex items-center rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-500/30 dark:text-emerald-50">
                                  ✓ ND compatível
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-500/10 px-3 py-1 text-[10px] font-semibold text-slate-700 opacity-80 dark:bg-slate-500/20 dark:text-slate-200">
              Cruzamento ND × Itens não disponível para esta análise
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

