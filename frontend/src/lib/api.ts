'use client';

import { getSession } from 'next-auth/react';
import type { AnalyzeFullResult, AnalyzeResult } from '../types/extraction';

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Helper central para chamadas ao backend com autenticação.
 * Inclui automaticamente o token de sessão e metadados do usuário.
 */
export async function fetchAPI(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const session = await getSession();
  const accessToken = (session as any)?.accessToken || '';
  const userId = (session?.user as any)?.id || '';
  const email = session?.user?.email || '';
  const name = session?.user?.name || '';

  const mergedHeaders: HeadersInit = {
    ...(options.headers || {}),
    Authorization: `Bearer ${accessToken}`,
    'X-User-Email': email,
    'X-User-Name': name,
    'X-User-Id': userId,
  };

  return fetch(`${API_URL}${path}`, {
    ...options,
    headers: mergedHeaders,
  });
}

export async function analyze(pdf: File): Promise<AnalyzeResult> {
  const formData = new FormData();
  formData.append('file', pdf);

  const res = await fetchAPI('/api/analyze', {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(
      `Erro na extração (status ${res.status}): ${text || res.statusText}`,
    );
  }

  return (await res.json()) as AnalyzeResult;
}

/** Resumo de uma análise no histórico (sem dados_completos). */
export type AnalysisSummary = {
  id: string;
  nup: string | null;
  requisicao: string | null;
  om: string | null;
  om_sigla: string | null;
  instrumento_tipo: string | null;
  instrumento_numero: string | null;
  uasg_codigo: string | null;
  uasg_nome: string | null;
  fornecedor: string | null;
  cnpj: string | null;
  valor_total: number | null;
  qtd_itens: number;
  veredicto: string | null;
  despacho: string | null;
  tempo_analise: number;
  data_analise: string;
};

/** Análise completa com dados_completos (estágios 1–6). */
export type AnalysisFull = AnalysisSummary & {
  dados_completos: AnalyzeFullResult;
};

export async function saveAnalysis(
  dados_completos: AnalyzeFullResult,
  tempo_analise: number,
): Promise<{ id: string; success: boolean }> {
  const res = await fetchAPI('/api/analyses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dados_completos, tempo_analise }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Erro ao salvar (status ${res.status}): ${text || res.statusText}`);
  }
  return (await res.json()) as { id: string; success: boolean };
}

export async function getAnalyses(): Promise<AnalysisSummary[]> {
  const res = await fetchAPI('/api/analyses');
  if (!res.ok) throw new Error('Erro ao carregar histórico');
  return (await res.json()) as AnalysisSummary[];
}

export async function getAnalysisById(id: string): Promise<AnalysisFull> {
  const res = await fetchAPI(`/api/analyses/${id}`);
  if (!res.ok) {
    if (res.status === 404) throw new Error('Análise não encontrada');
    throw new Error('Erro ao carregar análise');
  }
  return (await res.json()) as AnalysisFull;
}

export async function deleteAnalysis(id: string): Promise<{ success: boolean }> {
  const res = await fetchAPI(`/api/analyses/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(
      `Erro ao excluir (status ${res.status}): ${text || res.statusText}`,
    );
  }
  const json = (await res.json()) as { success?: boolean };
  return { success: json.success ?? true };
}

/** Adiciona uma UASG ao banco do sistema (quando não reconhecida). */
export async function addUASG(
  codigo: string,
  nome: string,
): Promise<{ success: boolean; codigo: string; nome: string }> {
  const res = await fetchAPI('/api/uasgs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ codigo: codigo.trim(), nome: nome.trim() }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(
      `Erro ao cadastrar UASG (status ${res.status}): ${text || res.statusText}`,
    );
  }
  return (await res.json()) as { success: boolean; codigo: string; nome: string };
}
