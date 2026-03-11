// Tipos compartilhados entre frontend e backend (espelhando os modelos Pydantic).

export type AnchorPageResult = {
  page_number: number;
  text: string;
  tables: string[][][];
};

export type AnchorConfig = {
  anchors: Record<string, string[]>;
};

export type ExtractionResult = {
  processed_pages: number;
  ignored_pages: number;
  anchor_config: AnchorConfig;
  results: Record<string, AnchorPageResult[]>;
};

export type HeaderData = {
  numero_processo: string | null;
  uasg: string | null;
  orgao: string | null;
  modalidade: string | null;
  objeto: string | null;
  data: string | null;
};

export type ItemRow = {
  descricao: string | null;
  quantidade: number | null;
  unidade: string | null;
  valor_unitario: number | null;
  valor_total: number | null;
};

export type ItemsData = {
  itens: ItemRow[];
};

export type DispatchAnalysis = {
  resumo: string | null;
  status: 'aprovado' | 'pendente' | 'com_ressalvas' | string | null;
  problemas_identificados: string[];
  acoes_necessarias: string[];
};

export type FornecedorData = {
  cnpj: string | null;
  razao_social: string | null;
  nome_fantasia: string | null;
  endereco: string | null;
  municipio: string | null;
  uf: string | null;
};

export type CorrecaoItem = {
  campo: string;
  valor_atual: string;
  sugestao: string;
  motivo: string;
};

export type VerificationResult = {
  score_confianca: number;
  correcoes: CorrecaoItem[];
};

export type FullExtractionDados = {
  cabecalho?: HeaderData;
  itens?: ItemsData;
  despacho?: DispatchAnalysis;
  fornecedor?: FornecedorData;
  // Campos adicionais podem ser adicionados no backend sem quebrar o frontend.
  [key: string]: unknown;
};

export type FullExtractionResult = {
  processed_pages: number;
  ignored_pages: number;
  dados: FullExtractionDados;
  verification?: VerificationResult | null;
};

// ---- Tipos para o novo endpoint /api/analyze (Estágio 1) ----

export type Stage1Requisicao = {
  numero: number | null;
  ano: number | null;
  texto_original: string | null;
};

export type Stage1OM = {
  nome: string | null;
  sigla: string | null;
  validada: boolean;
  confianca: number;
};

export type Stage1Data = {
  nup: string | null;
  requisicao: Stage1Requisicao | null;
  om: Stage1OM | null;
};

export type Stage1Confidence = {
  nup: number;
  requisicao: number;
  om: number;
  geral: number;
};

export type Stage1Result = {
  status: 'success' | 'partial' | 'error' | string;
  method: 'regex' | 'ai' | 'hybrid' | string;
  data: Stage1Data | null;
  confidence: Stage1Confidence | null;
};

export type Stage2Instrument = {
  tipo: string | null;
  numero: string | null;
  confidence: number | null;
  source: string | null;
  matched_text: string | null;
  normalized_text: string | null;
  resolution_reason: string | null;
  candidates: Record<string, unknown>[];
};

export type Stage2TipoEmpenho = {
  value: string | null;
  confidence: number | null;
  source: string | null;
  matched_text: string | null;
  normalized_text: string | null;
  resolution_reason: string | null;
  candidates: Record<string, unknown>[];
};

export type Stage2CNPJDetails = {
  value: string | null;
  formatted_value: string | null;
  confidence: number | null;
  source: string | null;
  matched_text: string | null;
  normalized_text: string | null;
  resolution_reason: string | null;
  candidates: Record<string, unknown>[];
};

export type Stage2UASG = {
  codigo: string | null;
  nome: string | null;
};

export type Stage2UASGDetails = {
  codigo: string | null;
  nome: string | null;
  confidence: number | null;
  source: string | null;
  matched_text: string | null;
  normalized_text: string | null;
  resolution_reason: string | null;
  candidates: Record<string, unknown>[];
};

export type Stage2Item = {
  item: number | null;
  catmat: string | null;
  descricao_completa: string | null;
  descricao_resumida: string | null;
  unidade: string | null;
  quantidade: number | null;
  nd_si: string | null;
  nd_si_display: string | null;
  nd_si_original: string | null;
  nd_si_raw: string | null;
  nd_si_candidates: Record<string, unknown>[];
  nd_si_resolution_reason: string | null;
  nd_si_ambigua: boolean | null;
  valor_unitario: number | null;
  valor_total: number | null;
};

export type Stage2Divergencia = {
  tipo: string;
  item: number | null;
  esperado: number;
  encontrado: number;
};

export type Stage2VerificacaoCalculos = {
  correto: boolean;
  divergencias: Stage2Divergencia[];
  valor_total_calculado: number;
};

export type Stage2Data = {
  instrumento: Stage2Instrument | null;
  uasg: Stage2UASG | null;
  uasg_details: Stage2UASGDetails | null;
  tipo_empenho: string | null;
  tipo_empenho_details: Stage2TipoEmpenho | null;
  fornecedor: string | null;
  cnpj: string | null;
  cnpj_details: Stage2CNPJDetails | null;
  valor_total: number | null;
  nd_req: string | null;
  itens: Stage2Item[];
  verificacao_calculos: Stage2VerificacaoCalculos | null;
  extracted_by_ai: boolean;
};

export type Stage2Confidence = {
  instrumento: number;
  uasg: number;
  tipo_empenho: number;
  fornecedor: number;
  cnpj: number;
  valor_total: number;
  itens: number;
  geral: number;
};

export type Stage2Result = {
  status: 'success' | 'partial' | 'error' | string;
  method: 'regex' | 'ai' | 'hybrid' | string;
  data: Stage2Data | null;
  confidence: Stage2Confidence | null;
  inactive_fields: string[];
};

export type Stage3Destination = {
  esfera: string | null;
  ptres: string | null;
  fonte: string | null;
  nd: string | null;
  ugr: string | null;
  pi: string | null;
  valor: number | null;
  evento: string | null;
};

export type Stage3NCConfidence = {
  geral: number;
};

export type Stage3NC = {
  numero_nc: string | null;
  formato_detectado: string | null;
  ug_emitente: string | null;
  valor_total: number | null;
  destinos: Stage3Destination[];
  campos_faltantes: string[];
  complementado_pela_requisicao: boolean;
  confidence: Stage3NCConfidence;
};

export type Stage3NDCrossItem = {
  item: number | null;
  descricao: string | null;
  unidade: string | null;
  nd_nc: string | null;
  nd_req: string | null;
  classificacao_sugerida: string | null;
  classificacao_label: string | null;
  subelemento_sugerido: string | null;
  nome_subelemento: string | null;
  nd_nc_compativel: boolean | null;
  nd_req_compativel: boolean | null;
  compativel: boolean | null;
  metodo: string | null;
  justificativa: string | null;
  confianca: number | null;
};

export type Stage3NDCrosscheck = {
  cruzamentos: Stage3NDCrossItem[];
  todos_compativeis: boolean;
  inconsistencias: Stage3NDCrossItem[];
};

export type Stage3Result = {
  status: 'success' | 'partial' | 'error' | string;
  ncs: Stage3NC[];
  nd_crosscheck?: Stage3NDCrosscheck | null;
};

// ---- Estágio 5 — Despachos ----

export type Stage5Exigencia = {
  descricao: string;
  categoria: string | null;
  urgente: boolean;
  despacho_origem: string;
};

export type Stage5ExigenciaStatus = {
  descricao: string;
  despacho_origem: string;
  status: 'atendida' | 'pendente' | string;
  despacho_resolucao: string | null;
  evidencia: string | null;
};

export type Stage5Dispatch = {
  numero: string | null;
  data: string | null;
  assunto: string | null;
  autor_secao: string | null;
  tipo: 'encaminhamento' | 'exigencia' | 'informativo' | string;
  resumo: string | null;
  exigencias: Stage5Exigencia[];
  palavras_chave: string[];
  confianca: number | null;
  pages?: number[];
};

export type Stage5Result = {
  status: 'sa' | 'com_pendencias' | string;
  total_despachos: number;
  despachos: Stage5Dispatch[];
  exigencias_pendentes: Stage5ExigenciaStatus[];
  exigencias_atendidas: Stage5ExigenciaStatus[];
  resultado: string;
  confidence?: { geral?: number };
};

// ---- Estágio 6 — Decisão Final ----

export type Stage6Issue = {
  estagio: number;
  tipo: 'reprovacao' | 'ressalva' | 'pendencia_despacho' | string;
  descricao: string;
  detalhes: string | null;
};

export type Stage6Result = {
  status: 'aprovado' | 'aprovado_com_ressalva' | 'reprovado' | string;
  veredicto: string;
  problemas: Stage6Issue[];
  reprovacoes: Stage6Issue[];
  ressalvas: Stage6Issue[];
  pendencias_despachos: Stage6Issue[];
  despacho: string;
  confidence?: { geral?: number };
};

export type AnalyzeMetadata = {
  total_paginas: number;
  paginas_com_texto: number;
  paginas_sem_texto: number;
  paginas_escaneadas: number[];
};

// ---- Estágio 4 — Documentação (CADIN, TCU, SICAF) ----

export type Stage4Verificacao = {
  cadastro?: string;
  orgao?: string;
  resultado?: string;
  aprovado?: boolean;
};

export type Stage4Nivel = {
  nivel?: string;
  validade?: string;
  vencido?: boolean;
  tipo?: string;
};

export type Stage4Cadin = {
  encontrado?: boolean;
  cnpj?: string | null;
  situacao?: string | null;
  data_emissao?: string | null;
  aprovado?: boolean;
};

export type Stage4Tcu = {
  encontrado?: boolean;
  cnpj?: string | null;
  data_consulta?: string | null;
  verificacoes?: Stage4Verificacao[];
  aprovado?: boolean;
};

export type Stage4Sicaf = {
  encontrado?: boolean;
  cnpj?: string | null;
  razao_social?: string | null;
  situacao_fornecedor?: string | null;
  data_emissao?: string | null;
  niveis?: Stage4Nivel[];
  ocorrencias?: Record<string, string>;
  aprovado?: boolean;
  motivos_reprovacao?: string[];
  itens_vencidos?: string[];
};

export type Stage4CnpjCruzamento = {
  cnpj_referencia?: string | null;
  consistente?: boolean;
  divergencias?: Array<{ doc?: string; cnpj_doc?: string; esperado?: string }>;
};

export type Stage4Complementar = {
  descricao?: string;
  documento_encontrado?: boolean;
  documento_descricao?: string;
  pagina?: number | null;
  anula_reprovacao?: boolean;
  confianca?: number;
};

export type Stage4Result = {
  status: 'approved' | 'rejected' | 'partial' | string;
  cadin?: Stage4Cadin;
  tcu?: Stage4Tcu;
  sicaf?: Stage4Sicaf;
  cnpj_cruzamento?: Stage4CnpjCruzamento;
  complementares?: Stage4Complementar[];
  confidence?: { geral?: number };
};

export type AnalyzeStages = {
  stage1: Stage1Result;
  stage2?: Stage2Result;
  stage3?: Stage3Result;
  stage4?: Stage4Result;
  stage5?: Stage5Result;
  stage6?: Stage6Result;
  [key: string]: unknown;
};

export type AnalyzeSummaryResult = {
  metadata: AnalyzeMetadata;
  stages: AnalyzeStages;
};

export type AnalyzeFullResult = AnalyzeSummaryResult & {
  extraction: Record<string, string>;
};

export type AnalyzeResult = AnalyzeSummaryResult;

