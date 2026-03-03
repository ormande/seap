import type { AnalyzeResult } from '../types/extraction';

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function analyze(pdf: File): Promise<AnalyzeResult> {
  const formData = new FormData();
  formData.append('file', pdf);

  const res = await fetch(`${API_URL}/api/analyze`, {
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
  dados_completos: AnalyzeResult;
};

export async function saveAnalysis(
  dados_completos: AnalyzeResult,
  tempo_analise: number,
): Promise<{ id: string; success: boolean }> {
  const res = await fetch(`${API_URL}/api/analyses`, {
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
  const res = await fetch(`${API_URL}/api/analyses`);
  if (!res.ok) throw new Error('Erro ao carregar histórico');
  return (await res.json()) as AnalysisSummary[];
}

export async function getAnalysisById(id: string): Promise<AnalysisFull> {
  const res = await fetch(`${API_URL}/api/analyses/${id}`);
  if (!res.ok) {
    if (res.status === 404) throw new Error('Análise não encontrada');
    throw new Error('Erro ao carregar análise');
  }
  return (await res.json()) as AnalysisFull;
}

export async function deleteAnalysis(id: string): Promise<{ success: boolean }> {
  const res = await fetch(`${API_URL}/api/analyses/${id}`, {
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
