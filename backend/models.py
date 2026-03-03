from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnchorConfig(BaseModel):
    """Configuração dos pontos âncora usados na extração."""

    anchors: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "cabecalho": [
                "processo nº",
                "processo no",
                "processo n.",
                "uasg",
                "requisição de",
            ],
            "itens": [
                "relação de itens",
                "quadro demonstrativo",
                "itens da licitação",
                "item | descrição",
                "item descrição",
            ],
            "despacho": [
                "despacho",
                "parecer",
                "determino",
                "autorizo",
                "decido",
            ],
            "fornecedor": [
                "cnpj",
                "razão social",
                "razao social",
                "fornecedor",
            ],
        }
    )


class AnchorPageResult(BaseModel):
    """Resultado de extração de uma página associada a um tipo de âncora."""

    page_number: int = Field(..., description="Número da página (1-based) no PDF.")
    text: str = Field(..., description="Texto completo extraído da página.")
    tables: List[List[List[str]]] = Field(
        default_factory=list,
        description=(
            "Lista de tabelas detectadas na página. "
            "Cada tabela é uma lista de linhas, e cada linha é uma lista de células."
        ),
    )


class ExtractionResult(BaseModel):
    """Resultado geral da extração de um PDF."""

    processed_pages: int = Field(
        ..., description="Total de páginas processadas no PDF."
    )
    ignored_pages: int = Field(
        ..., description="Total de páginas ignoradas (sem âncoras relevantes)."
    )
    anchor_config: AnchorConfig = Field(
        ..., description="Configuração de âncoras utilizada na extração."
    )
    results: Dict[str, List[AnchorPageResult]] = Field(
        default_factory=dict,
        description=(
            "Dados extraídos organizados por tipo de âncora. "
            "Chave: tipo de âncora (ex: 'cabecalho'). "
            "Valor: lista de páginas correspondentes."
        ),
    )


class CorreçãoItem(BaseModel):
    """Uma correção sugerida pela verificação de extração."""

    campo: str = Field(..., description="Nome do campo.")
    valor_atual: str = Field(..., description="Valor atualmente extraído.")
    sugestao: str = Field(..., description="Valor sugerido.")
    motivo: str = Field(..., description="Motivo da correção.")


class VerificationResult(BaseModel):
    """Resultado da verificação de segunda etapa (extração vs texto original)."""

    score_confianca: float = Field(
        ...,
        ge=0,
        le=1,
        description="Score de confiança entre 0 e 1 (1 = total aderência).",
    )
    correcoes: List[CorreçãoItem] = Field(
        default_factory=list,
        description="Lista de correções sugeridas.",
    )


class FullExtractionResult(BaseModel):
    """Resultado completo do pipeline: extração PDF + estruturação por IA + verificação."""

    processed_pages: int = Field(..., description="Total de páginas processadas.")
    ignored_pages: int = Field(..., description="Páginas ignoradas (sem âncoras).")
    dados: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Dados estruturados por tipo: cabecalho, itens, despacho, fornecedor. "
            "Cada chave contém o JSON retornado pela IA."
        ),
    )
    verification: VerificationResult | None = Field(
        default=None,
        description="Resultado da verificação de segunda passagem (score + correções).",
    )


class AnalyzeMetadata(BaseModel):
    """Metadados gerais da extração de todas as páginas."""

    total_paginas: int = Field(..., description="Total de páginas no PDF.")
    paginas_com_texto: int = Field(
        ..., description="Total de páginas com algum texto extraído."
    )
    paginas_sem_texto: int = Field(
        ..., description="Total de páginas sem texto extraível."
    )
    paginas_escaneadas: List[int] = Field(
        default_factory=list,
        description="Lista de páginas provavelmente escaneadas (imagem).",
    )


class Stage1Requisicao(BaseModel):
    """Informações estruturadas da requisição na capa."""

    numero: Optional[int] = Field(
        default=None, description="Número da requisição, se identificado."
    )
    ano: Optional[int] = Field(
        default=None, description="Ano da requisição, se identificado."
    )
    texto_original: Optional[str] = Field(
        default=None, description="Trecho original encontrado no PDF."
    )


class Stage1OM(BaseModel):
    """Informações da Organização Militar (Órgão de Origem) no estágio 1."""

    nome: Optional[str] = Field(
        default=None, description="Nome por extenso padronizado da OM."
    )
    sigla: Optional[str] = Field(
        default=None, description="Sigla da OM, se reconhecida na lista fixa."
    )
    validada: bool = Field(
        default=False,
        description="Indica se a OM foi reconhecida na lista fixa de OMs válidas.",
    )
    confianca: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Score de confiança específico da OM (0 a 100).",
    )


class Stage1Data(BaseModel):
    """Campos extraídos no estágio 1 (identificação)."""

    nup: Optional[str] = Field(default=None, description="Número Único de Protocolo.")
    requisicao: Optional[Stage1Requisicao] = Field(
        default=None, description="Dados da requisição."
    )
    om: Optional[Stage1OM] = Field(
        default=None,
        description="Organização Militar (Órgão de Origem), com validação contra lista fixa.",
    )


class Stage1Confidence(BaseModel):
    """Score de confiança por campo e geral no estágio 1."""

    nup: int = Field(..., ge=0, le=100)
    requisicao: int = Field(..., ge=0, le=100)
    om: int = Field(..., ge=0, le=100)
    geral: int = Field(..., ge=0, le=100)


class Stage1Result(BaseModel):
    """Resultado completo do estágio 1."""

    status: str = Field(
        ...,
        description="success, partial ou error, conforme preenchimento dos campos.",
    )
    method: str = Field(
        ..., description="regex, ai ou hybrid, indicando a origem dos dados."
    )
    data: Optional[Stage1Data] = Field(
        default=None, description="Campos extraídos para o estágio 1."
    )
    confidence: Optional[Stage1Confidence] = Field(
        default=None, description="Scores de confiança por campo e geral."
    )


class Stage2Instrument(BaseModel):
    """Instrumento da contratação (Pregão, Contrato, Dispensa, Inexigibilidade)."""

    tipo: Optional[str] = Field(
        default=None,
        description="Tipo do instrumento: Pregão Eletrônico, Contrato, Dispensa ou Inexigibilidade.",
    )
    numero: Optional[str] = Field(
        default=None,
        description="Número do instrumento, ex.: 90004/2025.",
    )


class Stage2UASG(BaseModel):
    """Dados da UASG/UG gerenciadora da contratação."""

    codigo: Optional[str] = Field(
        default=None,
        description="Código UASG/UG com 6 dígitos (começa com 16).",
    )
    nome: Optional[str] = Field(
        default=None,
        description="Nome da OM gerenciadora associada à UASG/UG.",
    )


class Stage2Item(BaseModel):
    """Item da tabela de materiais/serviços da requisição."""

    item: Optional[int] = Field(
        default=None, description="Número do item na tabela."
    )
    catmat: Optional[str] = Field(
        default=None, description="Código CatMat/CatServ do item, se houver."
    )
    descricao_completa: Optional[str] = Field(
        default=None, description="Descrição completa do material/serviço."
    )
    descricao_resumida: Optional[str] = Field(
        default=None,
        description=(
            "Descrição resumida (ex.: primeiros 80 caracteres) para exibição em tabela."
        ),
    )
    unidade: Optional[str] = Field(
        default=None, description="Unidade de medida (un, kg, svc, m, etc.)."
    )
    quantidade: Optional[float] = Field(
        default=None, description="Quantidade solicitada."
    )
    nd_si: Optional[str] = Field(
        default=None,
        description=(
            "Classificação ND/SI do item em formato normalizado EE.SS (ex.: 30.24)."
        ),
    )
    nd_si_original: Optional[str] = Field(
        default=None,
        description="Valor original de ND/SI encontrado no documento, sem normalização.",
    )
    valor_unitario: Optional[float] = Field(
        default=None, description="Valor unitário do item (em reais)."
    )
    valor_total: Optional[float] = Field(
        default=None, description="Valor total do item (em reais)."
    )


class Stage2Divergencia(BaseModel):
    """Divergência encontrada na verificação automática de cálculos."""

    tipo: str = Field(
        ...,
        description="Tipo de divergência: 'item' para linha individual ou 'total' para soma geral.",
    )
    item: Optional[int] = Field(
        default=None,
        description="Número do item associado à divergência, quando aplicável.",
    )
    esperado: float = Field(
        ...,
        description="Valor esperado calculado pelo sistema (em reais).",
    )
    encontrado: float = Field(
        ...,
        description="Valor encontrado no documento (em reais).",
    )


class Stage2VerificacaoCalculos(BaseModel):
    """Resultado da verificação automática dos cálculos da requisição."""

    correto: bool = Field(
        ...,
        description="Indica se todos os cálculos batem dentro da tolerância definida.",
    )
    divergencias: List[Stage2Divergencia] = Field(
        default_factory=list,
        description="Lista de divergências por item ou no total geral.",
    )
    valor_total_calculado: float = Field(
        ...,
        description="Soma calculada de todos os valores totais dos itens.",
    )


class Stage2Data(BaseModel):
    """Dados extraídos no estágio 2 (análise da peça da requisição)."""

    instrumento: Optional[Stage2Instrument] = Field(
        default=None,
        description="Instrumento da contratação (tipo e número).",
    )
    uasg: Optional[Stage2UASG] = Field(
        default=None,
        description="UASG/UG gerenciadora associada à requisição.",
    )
    tipo_empenho: Optional[str] = Field(
        default=None,
        description="Tipo de empenho: Ordinário, Estimativo ou Global.",
    )
    fornecedor: Optional[str] = Field(
        default=None,
        description="Nome da empresa fornecedora.",
    )
    cnpj: Optional[str] = Field(
        default=None,
        description="CNPJ do fornecedor, no formato XX.XXX.XXX/XXXX-XX.",
    )
    valor_total: Optional[float] = Field(
        default=None,
        description="Valor total da requisição (em reais).",
    )
    itens: List[Stage2Item] = Field(
        default_factory=list,
        description="Lista completa de itens da tabela de materiais/serviços.",
    )
    verificacao_calculos: Optional[Stage2VerificacaoCalculos] = Field(
        default=None,
        description="Resultado da verificação automática de cálculos.",
    )
    extracted_by_ai: bool = Field(
        default=False,
        description="Indica se a tabela de itens foi extraída usando IA (ex.: OCR/vision).",
    )


class Stage2Confidence(BaseModel):
    """Score de confiança por campo e geral no estágio 2."""

    instrumento: int = Field(..., ge=0, le=100)
    uasg: int = Field(..., ge=0, le=100)
    tipo_empenho: int = Field(..., ge=0, le=100)
    fornecedor: int = Field(..., ge=0, le=100)
    cnpj: int = Field(..., ge=0, le=100)
    valor_total: int = Field(..., ge=0, le=100)
    itens: int = Field(..., ge=0, le=100)
    geral: int = Field(..., ge=0, le=100)


class Stage2Result(BaseModel):
    """Resultado completo do estágio 2 (análise da peça da requisição)."""

    status: str = Field(
        ...,
        description="success, partial ou error, conforme preenchimento dos campos.",
    )
    method: str = Field(
        ...,
        description="regex, ai ou hybrid, indicando a origem predominante dos dados.",
    )
    data: Optional[Stage2Data] = Field(
        default=None, description="Campos extraídos para o estágio 2."
    )
    confidence: Optional[Stage2Confidence] = Field(
        default=None, description="Scores de confiança por campo e geral."
    )
    inactive_fields: List[str] = Field(
        default_factory=list,
        description="Lista de campos/desdobramentos ainda inativos (ex.: verificação de ND).",
    )


class Stage3Destination(BaseModel):
    """Destino orçamentário de uma Nota de Crédito (NC)."""

    esfera: Optional[str] = Field(
        default=None,
        description="Esfera orçamentária (ESF), geralmente 1 dígito.",
    )
    ptres: Optional[str] = Field(
        default=None,
        description="Código PTRES associado ao destino.",
    )
    fonte: Optional[str] = Field(
        default=None,
        description="Fonte de recursos (código numérico longo).",
    )
    nd: Optional[str] = Field(
        default=None,
        description="Natureza de Despesa (ND) com 6 dígitos, ex.: 339000, 339039.",
    )
    ugr: Optional[str] = Field(
        default=None,
        description="UGR/UG favorecida, código de 6 dígitos.",
    )
    pi: Optional[str] = Field(
        default=None,
        description="Plano Interno (PI) alfanumérico.",
    )
    valor: Optional[float] = Field(
        default=None,
        description="Valor em reais destinado a este destino.",
    )
    evento: Optional[str] = Field(
        default=None,
        description="Código do evento SIAFI associado (quando aplicável).",
    )


class Stage3NCConfidence(BaseModel):
    """Score de confiança por NC no estágio 3."""

    geral: int = Field(..., ge=0, le=100)


class Stage3NC(BaseModel):
    """Representa uma Nota de Crédito identificada no PDF."""

    numero_nc: Optional[str] = Field(
        default=None, description="Número da NC no formato XXXXNCXXXXXX."
    )
    formato_detectado: Optional[str] = Field(
        default=None,
        description=(
            "Formato detectado da NC: web_complete, siafi_complete, "
            "siafi_partial, web_standard, etc."
        ),
    )
    ug_emitente: Optional[str] = Field(
        default=None,
        description="UG emitente da NC, código de 6 dígitos.",
    )
    valor_total: Optional[float] = Field(
        default=None,
        description="Valor total da NC (soma dos destinos).",
    )
    destinos: List[Stage3Destination] = Field(
        default_factory=list,
        description="Lista de destinos orçamentários da NC (uma entrada por ND distinta).",
    )
    campos_faltantes: List[str] = Field(
        default_factory=list,
        description="Lista de campos que não puderam ser extraídos (topo ou destinos).",
    )
    complementado_pela_requisicao: bool = Field(
        default=False,
        description=(
            "Indica se algum campo desta NC foi complementado usando dados do tópico 2 "
            "da peça da requisição."
        ),
    )
    confidence: Stage3NCConfidence = Field(
        ...,
        description="Score de confiança geral desta NC.",
    )


class Stage3NDCrossItem(BaseModel):
    """
    Resultado do cruzamento ND × Itens para um item específico.

    Representa a compatibilidade entre:
    - ND da NC (destino orçamentário);
    - ND/SI informada na requisição para o item;
    - classificação correta inferida (material, serviço ou equipamento).
    """

    item: Optional[int] = Field(
        default=None,
        description="Número do item na requisição.",
    )
    descricao: Optional[str] = Field(
        default=None,
        description="Descrição (resumida) do item.",
    )
    unidade: Optional[str] = Field(
        default=None,
        description="Unidade de medida do item (un, kg, svc, etc.).",
    )
    nd_nc: Optional[str] = Field(
        default=None,
        description="ND completa utilizada na Nota de Crédito (NC), ex.: 339039.",
    )
    nd_req: Optional[str] = Field(
        default=None,
        description="ND/SI associada ao item na requisição (formato livre, ex.: 30.24).",
    )
    classificacao_sugerida: Optional[str] = Field(
        default=None,
        description="Elemento sugerido para o item: '30', '39' ou '52'.",
    )
    classificacao_label: Optional[str] = Field(
        default=None,
        description="Rótulo amigável da classificação (Material, Serviço, Equipamento).",
    )
    subelemento_sugerido: Optional[str] = Field(
        default=None,
        description="Código do subelemento sugerido (dois dígitos, ex.: '17').",
    )
    nome_subelemento: Optional[str] = Field(
        default=None,
        description="Descrição do subelemento sugerido.",
    )
    nd_nc_compativel: Optional[bool] = Field(
        default=None,
        description="Se a ND da NC é compatível com a natureza do item.",
    )
    nd_req_compativel: Optional[bool] = Field(
        default=None,
        description="Se a ND/SI da requisição é compatível com a natureza do item.",
    )
    compativel: Optional[bool] = Field(
        default=None,
        description=(
            "Compatibilidade geral do item (considerando ND da NC e da requisição). "
            "False indica alguma inconsistência relevante."
        ),
    )
    metodo: Optional[str] = Field(
        default=None,
        description="Método utilizado: 'palavras_chave' (rápido) ou 'ia' (Gemini).",
    )
    justificativa: Optional[str] = Field(
        default=None,
        description="Justificativa textual da classificação (quando fornecida pela IA).",
    )
    confianca: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Score de confiança da classificação (0 a 100), quando disponível.",
    )


class Stage3NDCrosscheck(BaseModel):
    """
    Resultado agregado do cruzamento ND × Itens.

    - cruzamentos: todos os itens analisados;
    - todos_compativeis: True se nenhum item apresentou inconsistência relevante;
    - inconsistencias: subconjunto de cruzamentos com compativel == False.
    """

    cruzamentos: List[Stage3NDCrossItem] = Field(
        default_factory=list,
        description="Lista de resultados por item no cruzamento ND × Itens.",
    )
    todos_compativeis: bool = Field(
        default=True,
        description="Indica se todas as combinações ND × Itens foram consideradas compatíveis.",
    )
    inconsistencias: List[Stage3NDCrossItem] = Field(
        default_factory=list,
        description="Lista de itens com alguma inconsistência de ND.",
    )


class Stage3Result(BaseModel):
    """Resultado completo do estágio 3 (Notas de Crédito)."""

    status: str = Field(
        ...,
        description=(
            "success, partial ou error, conforme preenchimento das NCs "
            "encontradas."
        ),
    )
    ncs: List[Stage3NC] = Field(
        default_factory=list,
        description="Lista de Notas de Crédito identificadas no PDF.",
    )
    nd_crosscheck: Optional[Stage3NDCrosscheck] = Field(
        default=None,
        description="Resultado do cruzamento ND × Itens entre a NC e a requisição.",
    )


class Stage5Exigencia(BaseModel):
    """Exigência individual identificada em um despacho."""

    descricao: str = Field(..., description="Texto da exigência.")
    categoria: Optional[str] = Field(
        default=None,
        description="Categoria da exigência: correcao|documento|acao|regularizacao.",
    )
    urgente: bool = Field(
        default=False,
        description="Indica se a exigência parece ter caráter urgente.",
    )
    despacho_origem: str = Field(
        ...,
        description="Número do despacho de origem da exigência.",
    )


class Stage5ExigenciaStatus(BaseModel):
    """Status de atendimento de uma exigência ao longo da sequência de despachos."""

    descricao: str = Field(..., description="Descrição resumida da exigência.")
    despacho_origem: str = Field(
        ...,
        description="Número do despacho em que a exigência foi feita.",
    )
    status: str = Field(
        ...,
        description="Status da exigência: atendida|pendente.",
    )
    despacho_resolucao: Optional[str] = Field(
        default=None,
        description="Número do despacho que resolveu a exigência, se houver.",
    )
    evidencia: Optional[str] = Field(
        default=None,
        description="Trecho/resumo que justifica o status atribuído.",
    )


class Stage5Dispatch(BaseModel):
    """Representa um despacho identificado no processo."""

    numero: Optional[str] = Field(
        default=None,
        description="Número completo do despacho (incluindo seção/OM).",
    )
    data: Optional[str] = Field(
        default=None,
        description="Data do despacho (preferencialmente no formato DD/MM/YYYY).",
    )
    assunto: Optional[str] = Field(
        default=None,
        description="Assunto do despacho (texto após 'Assunto:').",
    )
    autor_secao: Optional[str] = Field(
        default=None,
        description="Autor/seção inferido (ex.: Fisc Adm, CAF, OD).",
    )
    tipo: str = Field(
        ...,
        description="Tipo do despacho: encaminhamento|exigencia|informativo.",
    )
    resumo: Optional[str] = Field(
        default=None,
        description="Resumo breve (1-2 frases) do conteúdo do despacho.",
    )
    exigencias: List[Stage5Exigencia] = Field(
        default_factory=list,
        description="Lista de exigências extraídas deste despacho.",
    )
    palavras_chave: List[str] = Field(
        default_factory=list,
        description="Palavras-chave identificadas pela IA no despacho.",
    )
    confianca: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Score de confiança da classificação do despacho.",
    )
    pages: List[int] = Field(
        default_factory=list,
        description="Páginas do PDF que compõem o despacho.",
    )


class Stage5Result(BaseModel):
    """Resultado do estágio 5 — Despachos (exigências e pendências)."""

    status: str = Field(
        ...,
        description="sa (sem alteração) ou com_pendencias.",
    )
    total_despachos: int = Field(
        ...,
        description="Total de despachos identificados no processo.",
    )
    despachos: List[Stage5Dispatch] = Field(
        default_factory=list,
        description="Lista de despachos analisados em ordem cronológica.",
    )
    exigencias_pendentes: List[Stage5ExigenciaStatus] = Field(
        default_factory=list,
        description="Exigências que permanecem pendentes após o cross-check.",
    )
    exigencias_atendidas: List[Stage5ExigenciaStatus] = Field(
        default_factory=list,
        description="Exigências que foram atendidas em despachos posteriores.",
    )
    resultado: str = Field(
        ...,
        description='Resumo textual do veredicto (ex.: "S/A").',
    )
    confidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Mapa de scores de confiança (ex.: {'geral': 90}).",
    )


class Stage6Issue(BaseModel):
    """Problema ou pendência identificado na decisão final."""

    estagio: int = Field(..., description="Número do estágio de origem (1 a 6).")
    tipo: str = Field(
        ...,
        description="Tipo do problema: reprovacao|ressalva|pendencia_despacho.",
    )
    descricao: str = Field(..., description="Descrição resumida do problema.")
    detalhes: Optional[str] = Field(
        default=None,
        description="Detalhes adicionais relevantes (valores, datas, etc.).",
    )


class Stage6Result(BaseModel):
    """Resultado do estágio 6 — Decisão Final."""

    status: str = Field(
        ...,
        description="aprovado|aprovado_com_ressalva|reprovado.",
    )
    veredicto: str = Field(
        ...,
        description="Texto legível do veredicto (ex.: 'Aprovado com Ressalva').",
    )
    problemas: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lista de todos os problemas agregados (reprovações, ressalvas e pendências informativas).",
    )
    reprovacoes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lista de reprovações (problemas graves).",
    )
    ressalvas: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lista de ressalvas (problemas menores que não impedem o prosseguimento).",
    )
    pendencias_despachos: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Pendências oriundas de despachos (Estágio 5), apenas informativas.",
    )
    despacho: str = Field(
        ...,
        description="Texto do despacho sugerido (pode ser vazio quando veredicto for 'aprovado').",
    )
    confidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Mapa com score de confiança geral para a decisão.",
    )


class Stage4Result(BaseModel):
    """Resultado do estágio 4 — Documentação (CADIN, TCU, SICAF)."""

    status: str = Field(
        ...,
        description="approved, rejected ou partial (aprovado com ressalva por complementar).",
    )
    cadin: Dict[str, Any] = Field(default_factory=dict)
    tcu: Dict[str, Any] = Field(default_factory=dict)
    sicaf: Dict[str, Any] = Field(default_factory=dict)
    cnpj_cruzamento: Dict[str, Any] = Field(default_factory=dict)
    complementares: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: Dict[str, Any] = Field(default_factory=dict)


class AnalyzeStages(BaseModel):
    """Container com os estágios executados no pipeline de análise."""

    stage1: Stage1Result = Field(
        ..., description="Resultado do estágio 1 — Identificação."
    )
    stage2: Stage2Result | None = Field(
        default=None,
        description="Resultado do estágio 2 — Análise da peça da requisição.",
    )
    stage3: Stage3Result | None = Field(
        default=None,
        description="Resultado do estágio 3 — Notas de Crédito (NCs).",
    )
    stage4: Stage4Result | None = Field(
        default=None,
        description="Resultado do estágio 4 — Documentação (CADIN, TCU, SICAF).",
    )
    stage5: Stage5Result | None = Field(
        default=None,
        description="Resultado do estágio 5 — Despachos (exigências e pendências).",
    )
    stage6: Stage6Result | None = Field(
        default=None,
        description="Resultado do estágio 6 — Decisão Final (veredicto consolidado).",
    )


class AnalyzeResponse(BaseModel):
    """Resposta do endpoint /api/analyze."""

    extraction: Dict[str, str] = Field(
        ..., description='Mapa "pagina_n" -> texto bruto extraído.'
    )
    metadata: AnalyzeMetadata = Field(
        ..., description="Metadados agregados da extração."
    )
    stages: AnalyzeStages = Field(
        ..., description="Resultados por estágio do pipeline."
    )

