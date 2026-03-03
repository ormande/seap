import React, { useMemo, useState } from 'react';
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table';

import type {
  Stage2Confidence,
  Stage2Data,
  Stage2Divergencia,
  Stage2Item,
} from '../../types/extraction';
import { ConfidenceBadge } from './ConfidenceBadge';

type Stage2ContentProps = {
  data: Stage2Data | null;
  confidence: Stage2Confidence | null;
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

export const Stage2Content: React.FC<Stage2ContentProps> = ({
  data,
  confidence,
}) => {
  const [showDivergences, setShowDivergences] = useState(false);

  const items: Stage2Item[] = data?.itens ?? [];
  const divergencias: Stage2Divergencia[] =
    data?.verificacao_calculos?.divergencias ?? [];

  const totalFromItems = useMemo(() => {
    return items.reduce((acc, item) => acc + (item.valor_total ?? 0), 0);
  }, [items]);

  const columns = useMemo<ColumnDef<Stage2Item>[]>(
    () => [
      {
        header: 'Item',
        accessorKey: 'item',
        cell: (info) => info.getValue<number | null>() ?? '—',
        size: 50,
      },
      {
        header: 'CatMat/CatServ',
        accessorKey: 'catmat',
        cell: (info) => info.getValue<string | null>() ?? '—',
        size: 120,
      },
      {
        header: 'Descrição',
        accessorKey: 'descricao_resumida',
        cell: ({ row }) => {
          const full =
            row.original.descricao_completa ?? row.original.descricao_resumida ?? '';
          const display =
            full.length > 20 ? `${full.slice(0, 20)}...` : full || '—';
          return (
            <span className="text-xs" title={full || undefined}>
              {display}
            </span>
          );
        },
      },
      {
        header: 'Unidade',
        accessorKey: 'unidade',
        cell: (info) => info.getValue<string | null>() ?? '—',
        size: 70,
      },
      {
        header: 'QTD',
        accessorKey: 'quantidade',
        cell: (info) => {
          const v = info.getValue<number | null>();
          if (v === null || v === undefined) return '—';
          return new Intl.NumberFormat('pt-BR', {
            maximumFractionDigits: 3,
          }).format(v);
        },
        size: 80,
      },
      {
        header: 'ND/SI',
        accessorKey: 'nd_si',
        cell: ({ row }) => {
          const norm = row.original.nd_si;
          const original = row.original.nd_si_original;
          if (!norm && !original) return '—';
          const display = norm ?? original ?? '—';
          const title =
            original && norm && original !== norm
              ? `Valor original: ${original}`
              : undefined;
          return (
            <span className="text-xs" title={title}>
              {display}
            </span>
          );
        },
        size: 80,
      },
      {
        header: 'V. Unit',
        accessorKey: 'valor_unitario',
        cell: (info) => (
          <span className="tabular-nums">
            {formatCurrencyBRL(info.getValue<number | null>())}
          </span>
        ),
        size: 120,
        meta: { align: 'right' },
      },
      {
        header: 'V. Total',
        accessorKey: 'valor_total',
        cell: (info) => (
          <span className="tabular-nums font-medium">
            {formatCurrencyBRL(info.getValue<number | null>())}
          </span>
        ),
        size: 130,
        meta: { align: 'right' },
      },
    ],
    [],
  );

  const table = useReactTable({
    data: items,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="space-y-4">
      {/* Seção superior: dados gerais */}
      <div className="space-y-3 rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/40 p-3">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-medium text-[var(--text-secondary)]">
                Instrumento
              </p>
              <p className="mt-1 text-sm text-[var(--text-primary)]">
                {data?.instrumento
                  ? `${data.instrumento.tipo ?? ''}${
                      data.instrumento.numero
                        ? ` nº ${data.instrumento.numero}`
                        : ''
                    }`.trim() || 'Não identificado'
                  : 'Não identificado'}
              </p>
            </div>
            <ConfidenceBadge value={confidence?.instrumento ?? null} />
          </div>

          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-medium text-[var(--text-secondary)]">
                UASG / UG Gerenciadora
              </p>
              <p className="mt-1 text-sm text-[var(--text-primary)]">
                {data?.uasg ? (
                  <>
                    <span className="font-semibold">
                      {data.uasg.codigo ?? '—'}
                    </span>
                    {data.uasg.nome && (
                      <span className="ml-1 text-[var(--text-secondary)]">
                        {'– '}
                        {data.uasg.nome}
                      </span>
                    )}
                  </>
                ) : (
                  'Não identificado'
                )}
              </p>
            </div>
            <ConfidenceBadge value={confidence?.uasg ?? null} />
          </div>

          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-medium text-[var(--text-secondary)]">
                Tipo de empenho
              </p>
              <p className="mt-1 text-sm text-[var(--text-primary)]">
                {data?.tipo_empenho ?? 'Não identificado'}
              </p>
            </div>
            <ConfidenceBadge value={confidence?.tipo_empenho ?? null} />
          </div>

          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-medium text-[var(--text-secondary)]">
                Fornecedor
              </p>
              <p className="mt-1 text-sm">
                <span
                  className={
                    data?.fornecedor
                      ? 'text-[var(--text-primary)]'
                      : 'text-[var(--text-secondary)]'
                  }
                >
                  {data?.fornecedor ?? 'Não encontrado'}
                </span>
              </p>
            </div>
            <ConfidenceBadge value={confidence?.fornecedor ?? null} />
          </div>

          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-medium text-[var(--text-secondary)]">
                CNPJ
              </p>
              <p className="mt-1 text-sm">
                <span
                  className={
                    data?.cnpj
                      ? 'text-[var(--text-primary)]'
                      : 'text-[var(--text-secondary)]'
                  }
                >
                  {data?.cnpj ?? 'Não encontrado'}
                </span>
              </p>
            </div>
            <ConfidenceBadge value={confidence?.cnpj ?? null} />
          </div>

          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-medium text-[var(--text-secondary)]">
                Valor total
              </p>
              <p className="mt-1 text-base font-semibold text-emerald-600 dark:text-emerald-300">
                {formatCurrencyBRL((data?.valor_total ?? totalFromItems) || 0)}
              </p>
            </div>
            <ConfidenceBadge value={confidence?.valor_total ?? null} />
          </div>
        </div>
      </div>

      {/* Seção central: tabela de itens */}
      <div className="space-y-2 rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/40 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <p className="text-xs font-medium text-[var(--text-secondary)]">
              Itens da requisição
            </p>
            {data?.extracted_by_ai && (
              <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200">
                Extraído por IA
              </span>
            )}
          </div>
          <span className="text-[11px] text-[var(--text-secondary)]">
            {items.length > 0
              ? `${items.length} item(ns) encontrados`
              : 'Nenhum item identificado'}
          </span>
        </div>

        <div className="overflow-hidden rounded-lg border border-[var(--border-subtle)]/80">
          <div className="max-h-80 overflow-auto">
            <table className="min-w-full border-collapse text-xs">
              <thead className="bg-[var(--bg-main)]/60">
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <th
                        key={header.id}
                        className={[
                          'border-b border-[var(--border-subtle)] px-2 py-1 text-left text-[11px] font-semibold text-[var(--text-secondary)]',
                          (header.column.columnDef.meta as any)?.align === 'right'
                            ? 'text-right'
                            : '',
                        ].join(' ')}
                        style={{ width: header.getSize() || undefined }}
                      >
                        {header.isPlaceholder
                          ? null
                          : flexRender(
                              header.column.columnDef.header,
                              header.getContext(),
                            )}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row, idx) => (
                  <tr
                    key={row.id}
                    className={[
                      'transition-colors',
                      idx % 2 === 0
                        ? 'bg-[var(--bg-main)]/40'
                        : 'bg-[var(--bg-main)]/20',
                      'hover:bg-emerald-500/5',
                    ].join(' ')}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        className={[
                          'border-b border-[var(--border-subtle)]/60 px-2 py-1 align-top text-[11px] text-[var(--text-primary)]',
                          (cell.column.columnDef.meta as any)?.align === 'right'
                            ? 'text-right'
                            : '',
                        ].join(' ')}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td
                      colSpan={columns.length}
                      className="px-3 py-4 text-center text-[11px] text-[var(--text-secondary)]"
                    >
                      Nenhuma tabela de itens pôde ser identificada na peça da
                      requisição.
                    </td>
                  </tr>
                )}
              </tbody>
              {items.length > 0 && (
                <tfoot>
                  <tr>
                    <td
                      colSpan={columns.length - 1}
                      className="px-2 py-2 text-right text-[11px] font-semibold text-[var(--text-secondary)]"
                    >
                      Total calculado
                    </td>
                    <td className="px-2 py-2 text-right text-[11px] font-semibold text-emerald-700 dark:text-emerald-200">
                      {formatCurrencyBRL(totalFromItems)}
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      </div>

      {/* Seção inferior: verificações */}
      <div className="space-y-3 rounded-xl border border-[var(--border-subtle)]/80 bg-[var(--bg-main)]/40 p-3">
        <div className="flex flex-wrap items-center gap-2">
          {data?.verificacao_calculos ? (
            data.verificacao_calculos.correto ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-3 py-1 text-[11px] font-semibold text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200">
                ✓ Cálculos conferidos
              </span>
            ) : (
              <button
                type="button"
                onClick={() => setShowDivergences((prev) => !prev)}
                className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-3 py-1 text-[11px] font-semibold text-rose-700 transition hover:bg-rose-500/20 dark:bg-rose-500/20 dark:text-rose-100"
              >
                ✗ Divergências encontradas
                <span className="text-[10px]">
                  ({divergencias.length} ocorrência(s))
                </span>
              </button>
            )
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-500/10 px-3 py-1 text-[11px] font-semibold text-slate-700 dark:bg-slate-500/20 dark:text-slate-200">
              Cálculos não puderam ser verificados
            </span>
          )}

          <span className="inline-flex items-center gap-1 rounded-full bg-slate-500/10 px-3 py-1 text-[10px] font-semibold text-slate-700 opacity-70 dark:bg-slate-500/20 dark:text-slate-200">
            Verificação de ND — Em breve
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-500/10 px-3 py-1 text-[10px] font-semibold text-slate-700 opacity-70 dark:bg-slate-500/20 dark:text-slate-200">
            Máscara personalizada — Em breve
          </span>
        </div>

        {!data?.verificacao_calculos?.correto && divergencias.length > 0 && (
          <div
            className={[
              'overflow-hidden rounded-lg border border-rose-500/40 bg-rose-500/5 text-[11px] text-rose-900 dark:border-rose-500/60 dark:bg-rose-950/40 dark:text-rose-50',
              showDivergences ? 'max-h-64 p-3' : 'max-h-0 p-0',
              'transition-[max-height,padding] duration-300 ease-out',
            ].join(' ')}
          >
            <p className="mb-2 font-semibold">Divergências encontradas:</p>
            <ul className="space-y-1">
              {divergencias.map((d, idx) => {
                const esperado = formatCurrencyBRL(d.esperado);
                const encontrado = formatCurrencyBRL(d.encontrado);
                if (d.tipo === 'item') {
                  return (
                    <li key={idx}>
                      Item {d.item ?? '—'}: esperado {esperado}, encontrado{' '}
                      {encontrado}.
                    </li>
                  );
                }
                return (
                  <li key={idx}>
                    Total geral: esperado {esperado}, encontrado {encontrado}.
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

