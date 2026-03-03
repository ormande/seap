'use client';

import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { History, Search, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useCallback, useEffect, useMemo, useState } from 'react';

import {
  deleteAnalysis,
  getAnalyses,
  type AnalysisSummary,
} from '../../lib/api';

function formatCurrency(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
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
    }).format(d);
  } catch {
    return '—';
  }
}

function instrumentoLabel(row: AnalysisSummary): string {
  const t = row.instrumento_tipo ?? '';
  const n = row.instrumento_numero ?? '';
  if (!t && !n) return '—';
  return `${t} ${n}`.trim() || '—';
}

function veredictoBadge(veredicto: string | null | undefined) {
  if (!veredicto) return <span className="text-[var(--text-secondary)]">—</span>;
  const v = String(veredicto).toLowerCase();
  if (v === 'aprovado') {
    return (
      <span className="inline-flex rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
        Aprovado
      </span>
    );
  }
  if (v === 'aprovado_com_ressalva') {
    return (
      <span className="inline-flex rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
        Ressalva
      </span>
    );
  }
  if (v === 'reprovado') {
    return (
      <span className="inline-flex rounded-full bg-rose-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-700 dark:text-rose-300">
        Reprovado
      </span>
    );
  }
  return <span className="text-xs text-[var(--text-secondary)]">{veredicto}</span>;
}

function ConfirmModal({
  open,
  title,
  children,
  cancelLabel,
  confirmLabel,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  title: string;
  children: React.ReactNode;
  cancelLabel: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4 shadow-xl">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
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
            className="rounded-lg border border-rose-500/60 bg-rose-500/10 px-3 py-1.5 text-xs font-semibold text-rose-700 transition hover:bg-rose-500/20 dark:text-rose-200"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function HistoricoPage() {
  const router = useRouter();
  const [list, setList] = useState<AnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [veredictoFilter, setVeredictoFilter] = useState<string>('todos');
  const [sorting, setSorting] = useState<SortingState>([]);
  const [selectedForDelete, setSelectedForDelete] =
    useState<AnalysisSummary | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getAnalyses();
      setList(data);
    } catch {
      setList([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    let out = list;
    const q = search.trim().toLowerCase();
    if (q) {
      out = out.filter(
        (r) =>
          (r.nup?.toLowerCase().includes(q)) ||
          (r.requisicao?.toLowerCase().includes(q)) ||
          (r.fornecedor?.toLowerCase().includes(q)),
      );
    }
    if (veredictoFilter !== 'todos') {
      out = out.filter((r) => String(r.veredicto ?? '').toLowerCase() === veredictoFilter);
    }
    return out;
  }, [list, search, veredictoFilter]);

  const columns = useMemo<ColumnDef<AnalysisSummary>[]>(
    () => [
      {
        id: 'nup',
        header: 'NUP',
        accessorFn: (r) => r.nup ?? '—',
        cell: ({ getValue }) => (
          <span className="text-xs font-medium text-[var(--text-primary)]">{getValue()}</span>
        ),
      },
      {
        id: 'requisicao',
        header: 'Req',
        accessorFn: (r) => r.requisicao ?? '—',
        cell: ({ getValue }) => (
          <span className="text-xs text-[var(--text-secondary)]">{getValue()}</span>
        ),
      },
      {
        id: 'om_sigla',
        header: 'OM',
        accessorFn: (r) => r.om_sigla ?? r.om ?? '—',
        cell: ({ getValue }) => (
          <span className="text-xs text-[var(--text-secondary)]">{getValue()}</span>
        ),
      },
      {
        id: 'instrumento',
        header: 'Instrumento',
        accessorFn: instrumentoLabel,
        cell: ({ getValue }) => (
          <span className="text-xs text-[var(--text-secondary)]">{getValue()}</span>
        ),
      },
      {
        id: 'valor_total',
        header: 'Valor Total',
        accessorFn: (r) => r.valor_total ?? 0,
        cell: ({ getValue }) => (
          <span className="text-xs tabular-nums text-[var(--text-primary)]">
            {formatCurrency(getValue() as number)}
          </span>
        ),
      },
      {
        id: 'qtd_itens',
        header: 'Itens',
        accessorFn: (r) => r.qtd_itens ?? 0,
        cell: ({ getValue }) => (
          <span className="text-xs text-[var(--text-secondary)]">{String(getValue())}</span>
        ),
      },
      {
        id: 'veredicto',
        header: 'Veredicto',
        accessorFn: (r) => r.veredicto ?? '',
        cell: ({ row }) => veredictoBadge(row.original.veredicto),
      },
      {
        id: 'data_analise',
        header: 'Data',
        accessorFn: (r) => r.data_analise ?? '',
        cell: ({ getValue }) => (
          <span className="text-xs text-[var(--text-secondary)]">
            {formatDate(getValue() as string)}
          </span>
        ),
      },
      {
        id: 'actions',
        header: '',
        enableSorting: false,
        cell: ({ row }) => (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setSelectedForDelete(row.original);
            }}
            className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-transparent text-[var(--text-secondary)] transition hover:border-rose-500/40 hover:text-rose-600 dark:hover:text-rose-300"
            aria-label="Excluir análise"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        ),
      },
    ],
    [],
  );

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="space-y-4">
      {toast && (
        <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-xl border border-emerald-500/40 bg-emerald-500/90 px-4 py-2 text-sm font-medium text-white shadow-lg dark:bg-emerald-600/95">
          {toast}
        </div>
      )}

      <ConfirmModal
        open={!!selectedForDelete}
        title="Excluir análise?"
        cancelLabel="Cancelar"
        confirmLabel="Excluir"
        onCancel={() => setSelectedForDelete(null)}
        onConfirm={async () => {
          if (!selectedForDelete) return;
          const id = selectedForDelete.id;
          setSelectedForDelete(null);
          try {
            await deleteAnalysis(id);
            setDeletingId(id);
            setTimeout(() => {
              setList((prev) => prev.filter((item) => item.id !== id));
              setDeletingId(null);
            }, 200);
            setToast('Análise excluída');
            setTimeout(() => setToast(null), 2500);
          } catch (e) {
            setToast(
              e instanceof Error ? e.message : 'Erro ao excluir análise',
            );
            setTimeout(() => setToast(null), 2500);
          }
        }}
      >
        {selectedForDelete && (
          <>
            A análise do NUP{' '}
            <span className="font-semibold">
              {selectedForDelete.nup ?? '—'}
            </span>{' '}
            será removida permanentemente.
          </>
        )}
      </ConfirmModal>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Histórico de análises</h1>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-secondary)]" />
          <input
            type="search"
            placeholder="Buscar por NUP, requisição ou fornecedor..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] py-2 pl-9 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          />
        </div>
        <select
          value={veredictoFilter}
          onChange={(e) => setVeredictoFilter(e.target.value)}
          className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-emerald-500 focus:outline-none"
        >
          <option value="todos">Todos</option>
          <option value="aprovado">Aprovado</option>
          <option value="aprovado_com_ressalva">Ressalva</option>
          <option value="reprovado">Reprovado</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)]">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <p className="text-sm text-[var(--text-secondary)]">Carregando...</p>
          </div>
        ) : list.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <History className="h-6 w-6" />
            </div>
            <p className="text-sm font-medium text-[var(--text-primary)]">
              Nenhuma análise salva ainda
            </p>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              Salve uma análise na página de análise para que ela apareça aqui.
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-8 text-center text-sm text-[var(--text-secondary)]">
            Nenhum resultado para o filtro informado.
          </div>
        ) : (
          <table className="w-full min-w-[800px] border-collapse text-left">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-[var(--border-subtle)]">
                  {hg.headers.map((h) => (
                    <th
                      key={h.id}
                      className="cursor-pointer select-none px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] hover:bg-[var(--bg-main)]/50"
                      onClick={h.column.getToggleSortingHandler()}
                    >
                      <div className="flex items-center gap-1">
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {{
                          asc: ' ↑',
                          desc: ' ↓',
                        }[h.column.getIsSorted() as string] ?? null}
                      </div>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="cursor-pointer border-b border-[var(--border-subtle)]/60 transition hover:bg-emerald-500/5"
                  onClick={() => router.push(`/historico/${row.original.id}`)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
