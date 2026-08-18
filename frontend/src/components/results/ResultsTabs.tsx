import {
  AlertCircle,
  CheckCircle2,
  Download,
  TriangleAlert,
} from 'lucide-react';
import React, { useMemo, useState } from 'react';
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';

import type {
  DispatchAnalysis,
  FullExtractionDados,
  ItemRow,
  VerificationResult,
} from '../../types/extraction';

type ResultsTabsProps = {
  dados: FullExtractionDados | null;
  verification: VerificationResult | null | undefined;
};

type TabId = 'resumo' | 'itens' | 'despachos' | 'confianca';

const tabLabels: Record<TabId, string> = {
  resumo: 'Resumo',
  itens: 'Itens',
  despachos: 'Despachos',
  confianca: 'Confiança',
};

const TabButton: React.FC<{
  id: TabId;
  active: boolean;
  onClick: () => void;
}> = ({ id, active, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className={[
      'relative flex-1 px-3 py-2 text-center text-xs font-medium uppercase tracking-wide transition',
      active
        ? 'bg-emerald-900/80 text-emerald-50 shadow-inner shadow-emerald-900/80'
        : 'bg-emerald-950/40 text-emerald-300/80 hover:bg-emerald-900/40',
    ].join(' ')}
  >
    {tabLabels[id]}
    {active && (
      <span className="absolute inset-x-3 -bottom-0.5 h-0.5 rounded-full bg-gradient-to-r from-emerald-400 via-amber-300 to-emerald-500" />
    )}
  </button>
);

const ItemsTab: React.FC<{ dados: FullExtractionDados | null }> = ({ dados }) => {
  const itens = dados?.itens?.itens ?? [];

  const [sorting, setSorting] = useState<SortingState>([]);

  const columns = useMemo<ColumnDef<ItemRow>[]>(
    () => [
      {
        header: 'Descrição',
        accessorKey: 'descricao',
        cell: (info) => info.getValue<string | null>() ?? '—',
      },
      {
        header: 'Qtd',
        accessorKey: 'quantidade',
        cell: (info) => info.getValue<number | null>() ?? '—',
      },
      {
        header: 'Unidade',
        accessorKey: 'unidade',
        cell: (info) => info.getValue<string | null>() ?? '—',
      },
      {
        header: 'Valor Unitário',
        accessorKey: 'valor_unitario',
        cell: (info) => {
          const v = info.getValue<number | null>();
          return v == null ? '—' : v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        },
      },
      {
        header: 'Valor Total',
        accessorKey: 'valor_total',
        cell: (info) => {
          const v = info.getValue<number | null>();
          return v == null ? '—' : v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        },
      },
    ],
    [],
  );

  const table = useReactTable({
    data: itens,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (!itens.length) {
    return (
      <p className="text-xs text-emerald-300/80">
        Nenhuma tabela de itens foi identificada neste documento.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="overflow-hidden rounded-lg border border-emerald-800/80 bg-emerald-950/40">
        <table className="min-w-full border-collapse text-xs text-emerald-50 sm:text-sm">
          <thead className="bg-emerald-950/80 text-[11px] uppercase tracking-wide text-emerald-300/80">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    className="cursor-pointer px-3 py-2 text-left font-semibold"
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                      {{
                        asc: '▲',
                        desc: '▼',
                      }[header.column.getIsSorted() as string] ?? null}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row, idx) => (
              <tr
                key={row.id}
                className={
                  idx % 2 === 0 ? 'bg-emerald-950/70' : 'bg-emerald-950/40'
                }
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2 align-top">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-emerald-400/80">
        Clique nos cabeçalhos para ordenar os itens.
      </p>
    </div>
  );
};

const StatusBadge: React.FC<{ status: string | null | undefined }> = ({
  status,
}) => {
  const normalized = status?.toLowerCase();
  if (normalized === 'aprovado') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-900/70 px-2 py-0.5 text-[10px] font-semibold uppercase text-emerald-300">
        <CheckCircle2 className="h-3 w-3" />
        Aprovado
      </span>
    );
  }
  if (normalized === 'pendente') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-900/70 px-2 py-0.5 text-[10px] font-semibold uppercase text-amber-300">
        <AlertCircle className="h-3 w-3" />
        Pendente
      </span>
    );
  }
  if (normalized === 'com_ressalvas' || normalized === 'com ressalvas') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-800/70 px-2 py-0.5 text-[10px] font-semibold uppercase text-amber-200">
        <TriangleAlert className="h-3 w-3" />
        Com ressalvas
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-800/70 px-2 py-0.5 text-[10px] font-semibold uppercase text-slate-200">
      Indefinido
    </span>
  );
};

const DispatchesTab: React.FC<{ dados: FullExtractionDados | null }> = ({
  dados,
}) => {
  const despacho = (dados?.despacho ?? null) as DispatchAnalysis | null;

  if (!despacho) {
    return (
      <p className="text-xs text-emerald-300/80">
        Nenhum despacho foi identificado neste documento.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-emerald-800/80 bg-emerald-950/40 p-4">
        <div className="mb-2 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-emerald-50">
            Análise do despacho
          </h3>
          <StatusBadge status={despacho.status} />
        </div>
        <p className="text-xs text-emerald-100/90">{despacho.resumo}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-emerald-800/80 bg-emerald-950/40 p-3">
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-300">
            Problemas identificados
          </h4>
          {despacho.problemas_identificados?.length ? (
            <ul className="list-disc space-y-1 pl-4 text-xs text-emerald-100/90">
              {despacho.problemas_identificados.map((p, idx) => (
                <li key={idx}>{p}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-emerald-300/80">Nenhum problema listado.</p>
          )}
        </div>
        <div className="rounded-lg border border-emerald-800/80 bg-emerald-950/40 p-3">
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-emerald-300">
            Ações necessárias
          </h4>
          {despacho.acoes_necessarias?.length ? (
            <ul className="list-disc space-y-1 pl-4 text-xs text-emerald-100/90">
              {despacho.acoes_necessarias.map((a, idx) => (
                <li key={idx}>{a}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-emerald-300/80">
              Nenhuma ação adicional indicada.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

const ConfidenceTab: React.FC<{
  verification: VerificationResult | null | undefined;
}> = ({ verification }) => {
  if (!verification) {
    return (
      <p className="text-xs text-emerald-300/80">
        Nenhuma verificação de confiança foi retornada pelo backend.
      </p>
    );
  }

  const scorePct = Math.round(verification.score_confianca * 100);

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-emerald-800/80 bg-emerald-950/40 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-300">
          Score geral de confiança
        </p>
        <div className="mt-2 flex items-end gap-3">
          <p className="text-3xl font-semibold text-emerald-100">
            {scorePct}
            <span className="text-lg text-emerald-400/80">%</span>
          </p>
          <div className="flex-1">
            <div className="h-2 w-full overflow-hidden rounded-full bg-emerald-950/80">
              <div
                className="h-full rounded-full bg-gradient-to-r from-amber-300 via-emerald-400 to-emerald-500"
                style={{ width: `${scorePct}%` }}
              />
            </div>
            <p className="mt-1 text-[11px] text-emerald-300/80">
              Quanto mais próximo de 100%, maior a aderência entre o texto
              original e os dados extraídos.
            </p>
          </div>
        </div>
      </div>
      <div className="rounded-lg border border-emerald-800/80 bg-emerald-950/40 p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-300">
            Correções sugeridas
          </p>
          <span className="text-[11px] text-emerald-300/80">
            {verification.correcoes.length} registro(s)
          </span>
        </div>
        {verification.correcoes.length === 0 ? (
          <p className="text-xs text-emerald-300/80">
            Nenhuma correção sugerida pela IA.
          </p>
        ) : (
          <div className="space-y-2 text-xs text-emerald-100/90">
            {verification.correcoes.map((c, idx) => (
              <div
                key={idx}
                className="rounded-md border border-emerald-800/70 bg-emerald-950/60 p-2"
              >
                <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-300">
                  {c.campo}
                </p>
                <p className="mt-1 text-[11px] text-emerald-300/90">
                  Atual:{' '}
                  <span className="font-mono text-amber-200">
                    {c.valor_atual || '—'}
                  </span>
                </p>
                <p className="text-[11px] text-emerald-300/90">
                  Sugestão:{' '}
                  <span className="font-mono text-emerald-200">
                    {c.sugestao || '—'}
                  </span>
                </p>
                <p className="mt-1 text-[11px] text-emerald-300/70">
                  Motivo: {c.motivo || '—'}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export const ResultsTabs: React.FC<ResultsTabsProps> = ({
  dados,
  verification,
}) => {
  const [active, setActive] = useState<TabId>('resumo');

  return (
    <section className="mt-6 space-y-3 rounded-xl border border-emerald-800/80 bg-[#020806]/90 p-4 shadow-lg shadow-black/50">
      <div className="mb-1 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-emerald-50">
            Resultado da extração
          </h2>
          <p className="text-[11px] text-emerald-300/80">
            Visualize o cabeçalho, itens, despachos e a confiança da IA.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            // O botão de exportar em si será controlado pela página principal,
            // aqui deixamos apenas um estilo base para quando for usado em conjunto.
          }}
          className="inline-flex items-center gap-1 rounded-md border border-amber-400/60 bg-gradient-to-r from-[#2D4A22] to-[#4A6B35] px-3 py-1.5 text-xs font-medium text-amber-100 shadow-md shadow-black/40 hover:from-[#3D5A2E] hover:to-[#4A6B35]/90 active:scale-95"
          disabled
        >
          <Download className="h-3 w-3" />
          Exportar
        </button>
      </div>
      <div className="flex overflow-hidden rounded-lg border border-emerald-800/80 bg-emerald-950/60">
        {(Object.keys(tabLabels) as TabId[]).map((t) => (
          <TabButton
            key={t}
            id={t}
            active={active === t}
            onClick={() => setActive(t)}
          />
        ))}
      </div>
      <div className="mt-3">
        {active === 'resumo' && (
          // Resumo simples usando cabeçalho
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-xs text-emerald-100/90">
            <div className="rounded-md border border-emerald-800/80 bg-emerald-950/40 p-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-400">
                Processo
              </p>
              <p className="mt-1">
                {dados?.cabecalho?.numero_processo ?? '—'}
              </p>
            </div>
            <div className="rounded-md border border-emerald-800/80 bg-emerald-950/40 p-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-400">
                Órgão
              </p>
              <p className="mt-1">{dados?.cabecalho?.orgao ?? '—'}</p>
            </div>
            <div className="rounded-md border border-emerald-800/80 bg-emerald-950/40 p-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-400">
                Modalidade
              </p>
              <p className="mt-1">{dados?.cabecalho?.modalidade ?? '—'}</p>
            </div>
            <div className="sm:col-span-2 lg:col-span-3 rounded-md border border-emerald-800/80 bg-emerald-950/40 p-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-400">
                Objeto
              </p>
              <p className="mt-1">{dados?.cabecalho?.objeto ?? '—'}</p>
            </div>
          </div>
        )}
        {active === 'itens' && <ItemsTab dados={dados} />}
        {active === 'despachos' && <DispatchesTab dados={dados} />}
        {active === 'confianca' && <ConfidenceTab verification={verification} />}
      </div>
    </section>
  );
};

