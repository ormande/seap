'use client';

import React from 'react';
import { CheckCircle2, XCircle, AlertTriangle, FileText } from 'lucide-react';

// Rótulos com acentuação para as ocorrências do SICAF (mesmo ordem do backend)
const OCORRENCIAS_LABELS: Record<string, string> = {
  ocorrencia: 'Ocorrência',
  impedimento_licitar: 'Impedimento de Licitar',
  vinculo_servico_publico: 'Vínculo com Serviço Público',
  ocorrencias_impeditivas: 'Ocorrências Impeditivas Indiretas',
};
import type {
  Stage4Result,
  Stage4Cadin,
  Stage4Tcu,
  Stage4Sicaf,
  Stage4CnpjCruzamento,
  Stage4Complementar,
  Stage4Nivel,
  Stage4Verificacao,
} from '../../types/extraction';

type Stage4ContentProps = {
  data: Stage4Result | null;
};

// Veredicto geral no topo
const VeredictBadge: React.FC<{ status: string }> = ({ status }) => {
  if (status === 'approved') {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3">
        <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
        <span className="text-sm font-semibold text-emerald-800 dark:text-emerald-100">
          APROVADO
        </span>
      </div>
    );
  }
  if (status === 'partial') {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3">
        <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
        <span className="text-sm font-semibold text-amber-800 dark:text-amber-100">
          APROVADO COM RESSALVA
        </span>
        <span className="text-xs text-amber-700 dark:text-amber-200">
          (documento complementar pode anular reprovação)
        </span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3">
      <XCircle className="h-5 w-5 text-rose-600 dark:text-rose-400" />
      <span className="text-sm font-semibold text-rose-800 dark:text-rose-100">
        REPROVADO
      </span>
    </div>
  );
};

// Seção 1 — Cruzamento CNPJ
const CnpjCruzamentoSection: React.FC<{
  cnpj: Stage4CnpjCruzamento | undefined;
}> = ({ cnpj }) => {
  if (!cnpj) return null;
  const consistente = cnpj.consistente !== false;
  return (
    <div
      className={
        consistente
          ? 'rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3'
          : 'rounded-xl border border-rose-500/30 bg-rose-500/5 p-3'
      }
    >
      {consistente ? (
        <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-200">
          <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
          <span className="text-sm font-medium">
            CNPJ consistente em todos os documentos
          </span>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-rose-700 dark:text-rose-200">
            <XCircle className="h-4 w-4 flex-shrink-0" />
            <span className="text-sm font-medium">CNPJ divergente</span>
          </div>
          <ul className="list-inside list-disc text-xs text-rose-800 dark:text-rose-100">
            {(cnpj.divergencias ?? []).map((d, i) => (
              <li key={i}>
                {d.doc} possui {d.cnpj_doc}, esperado {d.esperado}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

// Seção 2 — CADIN
const CadinSection: React.FC<{ cadin: Stage4Cadin | undefined }> = ({
  cadin,
}) => {
  if (!cadin) return null;
  const encontrado = cadin.encontrado === true;
  const aprovado = cadin.aprovado === true;
  return (
    <div
      className={`rounded-xl border p-3 ${
        encontrado
          ? aprovado
            ? 'border-emerald-500/30 bg-emerald-500/5'
            : 'border-rose-500/30 bg-rose-500/5'
          : 'border-[var(--border-subtle)] bg-[var(--bg-main)]/40'
      }`}
    >
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
        CADIN
      </p>
      {!encontrado ? (
        <p className="text-xs text-[var(--text-secondary)]">Documento não encontrado</p>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div>
              <span className="text-[var(--text-secondary)]">CNPJ: </span>
              <span className="font-mono text-[var(--text-primary)]">
                {cadin.cnpj ?? '—'}
              </span>
            </div>
            <div>
              <span className="text-[var(--text-secondary)]">Emissão: </span>
              <span className="text-[var(--text-primary)]">
                {cadin.data_emissao ?? '—'}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {aprovado ? (
              <>
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-sm font-semibold text-emerald-700 dark:text-emerald-200">
                  REGULAR
                </span>
              </>
            ) : (
              <>
                <XCircle className="h-4 w-4 text-rose-500" />
                <span className="rounded-full bg-rose-500/20 px-2 py-0.5 text-sm font-semibold text-rose-700 dark:text-rose-200">
                  {cadin.situacao ?? 'Irregular'}
                </span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// Seção 3 — TCU
const TcuSection: React.FC<{ tcu: Stage4Tcu | undefined }> = ({ tcu }) => {
  if (!tcu) return null;
  const encontrado = tcu.encontrado === true;
  const aprovado = tcu.aprovado === true;
  const verificacoes: Stage4Verificacao[] = tcu.verificacoes ?? [];
  return (
    <div
      className={`rounded-xl border p-3 ${
        encontrado
          ? aprovado
            ? 'border-emerald-500/30 bg-emerald-500/5'
            : 'border-rose-500/30 bg-rose-500/5'
          : 'border-[var(--border-subtle)] bg-[var(--bg-main)]/40'
      }`}
    >
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
        TCU — Consulta Consolidada
      </p>
      {!encontrado ? (
        <p className="text-xs text-[var(--text-secondary)]">Documento não encontrado</p>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div>
              <span className="text-[var(--text-secondary)]">CNPJ: </span>
              <span className="font-mono text-[var(--text-primary)]">
                {tcu.cnpj ?? '—'}
              </span>
            </div>
            <div>
              <span className="text-[var(--text-secondary)]">Emissão: </span>
              <span className="text-[var(--text-primary)]">
                {tcu.data_consulta ?? '—'}
              </span>
            </div>
          </div>
          <ul className="space-y-1">
            {verificacoes.map((v, i) => (
              <li
                key={i}
                className="flex items-center justify-between gap-2 rounded px-2 py-1 text-xs"
              >
                <span className="text-[var(--text-primary)]">
                  {v.cadastro || v.orgao || `Verificação ${i + 1}`}
                </span>
                {v.aprovado ? (
                  <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Nada Consta
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-rose-600 dark:text-rose-400">
                    <XCircle className="h-3.5 w-3.5" />
                    {v.resultado || '—'}
                  </span>
                )}
              </li>
            ))}
          </ul>
          {aprovado && verificacoes.length > 0 && (
            <div className="flex items-center gap-1 pt-1 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4" />
              <span className="text-xs font-medium">Nada consta em todos os cadastros</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// Seção 4 — SICAF
const SicafSection: React.FC<{ sicaf: Stage4Sicaf | undefined }> = ({
  sicaf,
}) => {
  if (!sicaf) return null;
  const encontrado = sicaf.encontrado === true;
  const aprovado = sicaf.aprovado === true;
  const niveis: Stage4Nivel[] = sicaf.niveis ?? [];
  const ocorrencias = sicaf.ocorrencias ?? {};
  const motivos = sicaf.motivos_reprovacao ?? sicaf.itens_vencidos ?? [];

  return (
    <div
      className={`rounded-xl border p-3 ${
        encontrado
          ? aprovado
            ? 'border-emerald-500/30 bg-emerald-500/5'
            : 'border-rose-500/30 bg-rose-500/5'
          : 'border-[var(--border-subtle)] bg-[var(--bg-main)]/40'
      }`}
    >
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
        SICAF
      </p>
      {!encontrado ? (
        <p className="text-xs text-[var(--text-secondary)]">Documento não encontrado</p>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div>
              <span className="text-[var(--text-secondary)]">CNPJ: </span>
              <span className="font-mono text-[var(--text-primary)]">
                {sicaf.cnpj ?? '—'}
              </span>
            </div>
            <div>
              <span className="text-[var(--text-secondary)]">Emissão: </span>
              <span className="text-[var(--text-primary)]">
                {sicaf.data_emissao ?? '—'}
              </span>
            </div>
            <div className="col-span-2">
              <span className="text-[var(--text-secondary)]">Razão Social: </span>
              <span className="text-[var(--text-primary)]">
                {sicaf.razao_social ?? '—'}
              </span>
            </div>
            <div className="col-span-2">
              <span className="text-[var(--text-secondary)]">Situação: </span>
              <span className="text-[var(--text-primary)]">
                {sicaf.situacao_fornecedor ?? '—'}
              </span>
            </div>
          </div>
          {niveis.length > 0 && (
            <div className="overflow-hidden rounded-lg border border-[var(--border-subtle)]/60">
              <table className="min-w-full text-xs">
                <thead>
                  <tr className="bg-[var(--bg-main)]/60">
                    <th className="px-2 py-1.5 text-left font-medium text-[var(--text-secondary)]">
                      Nível
                    </th>
                    <th className="px-2 py-1.5 text-left font-medium text-[var(--text-secondary)]">
                      Validade
                    </th>
                    <th className="px-2 py-1.5 text-left font-medium text-[var(--text-secondary)]">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {niveis.map((n, i) => (
                    <tr
                      key={i}
                      className={
                        n.vencido
                          ? 'bg-rose-500/10 text-rose-800 dark:text-rose-200'
                          : 'bg-[var(--bg-main)]/20'
                      }
                    >
                      <td className="px-2 py-1">{n.nivel ?? '—'}</td>
                      <td className="px-2 py-1">{n.validade ?? '—'}</td>
                      <td className="px-2 py-1">
                        {n.vencido ? (
                          <span className="flex items-center gap-1">
                            <XCircle className="h-3.5 w-3.5" />
                            Vencido
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            OK
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {Object.keys(ocorrencias).length > 0 && (
            <div>
              <p className="mb-1 text-[11px] font-medium text-[var(--text-secondary)]">
                Ocorrências
              </p>
              <ul className="space-y-0.5">
                {Object.entries(ocorrencias).map(([k, v]) => {
                  const label = OCORRENCIAS_LABELS[k] ?? k.replace(/_/g, ' ');
                  const val = (v ?? '').trim();
                  const isNadaConsta =
                    val.toLowerCase().includes('nada consta') ||
                    val.toLowerCase() === 'não se aplica';
                  const isNaoIdentificado =
                    !val || val === '—' || val === 'Não identificado';
                  const statusIcon = isNadaConsta ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  ) : isNaoIdentificado ? (
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 text-rose-500" />
                  );
                  return (
                    <li key={k} className="flex items-center gap-2 text-xs">
                      {statusIcon}
                      <span>{label}:</span>
                      <span>{val || '—'}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
          {motivos.length > 0 && (
            <ul className="list-inside list-disc text-xs text-rose-700 dark:text-rose-200">
              {motivos.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

// Seção 5 — Documentos complementares (só se houver reprovações)
const ComplementaresSection: React.FC<{
  complementares: Stage4Complementar[] | undefined;
  status: string;
}> = ({ complementares, status }) => {
  const list = complementares ?? [];
  if (list.length === 0 || status === 'approved') return null;
  const withDoc = list.filter((c) => c.documento_encontrado && c.anula_reprovacao);
  if (withDoc.length === 0) return null;
  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
      <p className="mb-2 flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-amber-800 dark:text-amber-200">
        <FileText className="h-3.5 w-3.5" />
        Documentos complementares
      </p>
      <ul className="space-y-2">
        {withDoc.map((c, i) => (
          <li
            key={i}
            className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-2 py-2 text-xs"
          >
            <p className="font-medium text-amber-900 dark:text-amber-100">
              Possível regularização encontrada
              {c.pagina != null ? ` (pág. ${c.pagina})` : ''}
            </p>
            {c.documento_descricao && (
              <p className="mt-1 text-amber-800 dark:text-amber-200">
                {c.documento_descricao}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};

export const Stage4Content: React.FC<Stage4ContentProps> = ({ data }) => {
  if (!data) {
    return (
      <p className="text-xs text-[var(--text-secondary)]">
        Nenhum dado de documentação disponível.
      </p>
    );
  }

  const status = data.status ?? 'rejected';
  const confidence = data.confidence?.geral;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <VeredictBadge status={status} />
        {typeof confidence === 'number' && (
          <span className="text-xs text-[var(--text-secondary)]">
            Confiança: {Math.round(confidence)}%
          </span>
        )}
      </div>

      <CnpjCruzamentoSection cnpj={data.cnpj_cruzamento} />
      <CadinSection cadin={data.cadin} />
      <TcuSection tcu={data.tcu} />
      <SicafSection sicaf={data.sicaf} />
      <ComplementaresSection
        complementares={data.complementares}
        status={status}
      />
    </div>
  );
};
