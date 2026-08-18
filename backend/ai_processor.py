"""
Módulo de IA para estruturação e auditoria de dados extraídos de PDFs de licitações
do Exército Brasileiro usando Google Gemini Multimodal.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Carrega .env do diretório backend (ou raiz do projeto).
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()

logger = logging.getLogger(__name__)

# Modelos recomendados em ordem de preferência
CANDIDATE_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
]

# --- Schemas Pydantic para Structured Output ---


class RequisitionItemOutput(BaseModel):
    item: Optional[int] = Field(
        None, description="Número sequencial do item na requisição (ex: 1, 2, 3...)"
    )
    catmat: Optional[str] = Field(
        None, description="Código CatMat ou CatSer do material/serviço (ex: 150234)"
    )
    descricao: str = Field(
        ..., description="Descrição completa e detalhada do material ou serviço"
    )
    unidade: Optional[str] = Field(
        None, description="Unidade de fornecimento (ex: UND, UN, CX, PCT, KG, SV, RESMA, FRASCO)"
    )
    quantidade: Optional[float] = Field(
        None, description="Quantidade requisitada (numérica)"
    )
    valor_unitario: Optional[float] = Field(
        None, description="Valor unitário do item em Reais (R$)"
    )
    valor_total: Optional[float] = Field(
        None, description="Valor total do item (quantidade * valor_unitario)"
    )
    nd_subelemento: Optional[str] = Field(
        None,
        description="Natureza de Despesa / Subelemento se informado na linha (ex: 33.90.30.24 ou 30/24)",
    )


class RequisitionTableOutput(BaseModel):
    fornecedor: Optional[str] = Field(
        None, description="Razão Social ou Nome do Fornecedor / Empresa vencedora"
    )
    cnpj: Optional[str] = Field(
        None, description="CNPJ do Fornecedor formatado (00.000.000/0000-00) ou numérico"
    )
    valor_total_geral: Optional[float] = Field(
        None, description="Valor total geral da requisição / somatório dos itens"
    )
    tipo_empenho: Optional[str] = Field(
        None, description="Tipo de empenho selecionado: ORDINARIO, GLOBAL ou ESTIMATIVO"
    )
    itens: List[RequisitionItemOutput] = Field(
        default_factory=list, description="Lista de itens extraídos da tabela de materiais/serviços"
    )


class HeaderOutput(BaseModel):
    numero_processo: Optional[str] = Field(None, description="NUP / Número do Processo (ex: 64136.000532/2026-31)")
    uasg: Optional[str] = Field(None, description="Código UASG de 6 dígitos (ex: 160136)")
    orgao: Optional[str] = Field(None, description="Nome da Organização Militar / Unidade requisitante")
    modalidade: Optional[str] = Field(None, description="Modalidade da licitação (ex: Pregão Eletrônico, Dispensa, Inexigibilidade)")
    objeto: Optional[str] = Field(None, description="Descrição resumida do objeto da aquisição")
    data: Optional[str] = Field(None, description="Data do documento no formato ISO YYYY-MM-DD quando disponível")


class SupplierOutput(BaseModel):
    cnpj: Optional[str] = Field(None, description="CNPJ formatado do fornecedor")
    razao_social: Optional[str] = Field(None, description="Razão social da empresa")
    nome_fantasia: Optional[str] = Field(None, description="Nome fantasia")
    endereco: Optional[str] = Field(None, description="Logradouro e número")
    municipio: Optional[str] = Field(None, description="Cidade")
    uf: Optional[str] = Field(None, description="Sigla do estado (ex: MS, SP)")


class DispatchOutput(BaseModel):
    resumo: str = Field(..., description="Resumo sucinto do despacho em 1 a 2 frases")
    status: str = Field(..., description="Exatamente um de: 'aprovado', 'pendente', 'com_ressalvas'")
    problemas_identificados: List[str] = Field(default_factory=list, description="Problemas ou irregularidades apontados")
    acoes_necessarias: List[str] = Field(default_factory=list, description="Ações recomendadas para saneamento")


class NDClassificationOutput(BaseModel):
    subelemento: Optional[str] = Field(None, description="Código ou nome do subelemento mais adequado")
    codigo_nd: Optional[str] = Field(None, description="Código da ND (ex: 3.3.90.30)")
    confianca: str = Field(default="media", description="'alta', 'media' ou 'baixa'")


class VerificationOutput(BaseModel):
    score_confianca: float = Field(..., description="Score de 0.0 a 1.0 indicando conformidade da extração")
    correcoes: List[Dict[str, Any]] = Field(default_factory=list, description="Correções sugeridas")


# --- Prompts Especializados do Exército Brasileiro ---

MILITARY_TABLE_SYSTEM_PROMPT = """Você é um especialista em análise e auditoria de processos de compras e licitações do Exército Brasileiro.
Sua missão é extrair rigorosamente os dados da Tabela de Itens (Quadro de Material / Serviço a ser adquirido) da Requisição Militar.

Orientações de extração:
1. Extraia CADA ITEM individualmente da tabela (Item, CatMat, Descrição, Unidade, Quantidade, Valor Unitário, Valor Total, ND/Subelemento).
2. Se o documento contiver dados de Fornecedor (Razão Social, CNPJ), Tipo de Empenho (Ordinário, Global, Estimativo) e Valor Total Geral, extraia-os.
3. Para valores monetários e quantidades, extraia números puros (ex: 1250.50 e não "R$ 1.250,50"). Use ponto como separador decimal.
4. Normalize unidades comuns (UND, UN, CX, PCT, KG, SV, RESMA, FRASCO, PAR, MT).
5. Certifique-se de que cada linha seja capturada na ordem correta, mesmo que a tabela continue em múltiplas páginas.

Exemplo de estrutura militar esperada:
- Item: 1
- CatMat: "150234"
- Descrição: "CANETA ESFEROGRÁFICA AZUL 1.0MM"
- Unidade: "UND"
- Quantidade: 100.0
- Valor Unitário: 2.50
- Valor Total: 250.00
- ND/Subelemento: "33.90.30.24"
"""


def _retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    """Executa função com retry exponencial para timeout e rate limit."""
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            msg = str(e).lower()
            if (
                "rate" in msg
                or "resource" in msg
                or "429" in msg
                or "timeout" in msg
                or "503" in msg
                or "unavailable" in msg
                or "spikes in demand" in msg
            ):
                delay = base_delay * (2**attempt)
                logger.warning(
                    "Tentativa %s/%s falhou (%s). Aguardando %.1fs.",
                    attempt + 1,
                    max_retries,
                    e,
                    delay,
                )
                time.sleep(delay)
            else:
                raise
    raise last_error


class GeminiProcessor:
    """
    Processador de IA Multimodal usando Google Gemini para extração e
    estruturação de documentos militares com validação rigorosa de schemas.
    """

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError(
                "GEMINI_API_KEY não definida. Configure no .env ou passe api_key."
            )
        self._client = genai.Client(api_key=key)

    def _call_model_with_fallback(
        self,
        contents: Any,
        schema: Any = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Any:
        """Tenta a chamada no modelo prioritário e faz fallback automático se o modelo estiver indisponível."""
        last_err = None
        for model_name in CANDIDATE_MODELS:
            try:
                config_kwargs: Dict[str, Any] = {
                    "temperature": temperature,
                }
                if schema is not None:
                    config_kwargs["response_mime_type"] = "application/json"
                    config_kwargs["response_schema"] = schema
                else:
                    config_kwargs["response_mime_type"] = "application/json"

                if system_instruction:
                    config_kwargs["system_instruction"] = system_instruction

                config = types.GenerateContentConfig(**config_kwargs)

                def _exec():
                    return self._client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config,
                    )

                response = _retry_with_backoff(_exec, max_retries=2, base_delay=1.0)
                return response
            except Exception as exc:
                last_err = exc
                err_msg = str(exc).lower()
                logger.warning("Modelo %s indisponível (%s). Tentando próximo modelo...", model_name, exc)
                if "not_found" in err_msg or "404" in err_msg or "503" in err_msg or "unavailable" in err_msg:
                    continue
                # Se for outro erro, continua tentando fallback
                continue

        if last_err:
            raise last_err
        raise RuntimeError("Nenhum modelo do Gemini respondeu com sucesso.")

    def _generate(
        self, prompt: str, schema: Any = None, operation: str = "general"
    ) -> tuple[dict[str, Any], int, int]:
        """Gera resposta estruturada a partir de texto."""
        response = self._call_model_with_fallback(contents=prompt, schema=schema)
        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0

        text = (response.text or "").strip()
        if not text:
            return {}, input_tokens, output_tokens
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        try:
            return json.loads(text), input_tokens, output_tokens
        except json.JSONDecodeError:
            logger.warning("Falha ao decodificar JSON gerado: %s", text[:200])
            return {}, input_tokens, output_tokens

    def _generate_with_images(
        self,
        prompt: str,
        images_base64: list[str],
        schema: Any = None,
        system_instruction: Optional[str] = None,
        operation: str = "vision",
    ) -> tuple[dict[str, Any], int, int]:
        """Envia imagens em alta resolução + prompt diretamente ao Gemini Multimodal."""
        content_parts: List[Any] = [types.Part.from_text(text=prompt)]
        for b64 in images_base64:
            if not b64:
                continue
            content_parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(b64),
                    mime_type="image/png",
                )
            )

        response = self._call_model_with_fallback(
            contents=content_parts,
            schema=schema,
            system_instruction=system_instruction,
        )
        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0

        text = (response.text or "").strip()
        if not text:
            return {}, input_tokens, output_tokens
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        try:
            return json.loads(text), input_tokens, output_tokens
        except json.JSONDecodeError:
            logger.warning("Falha ao decodificar JSON multimodal: %s", text[:200])
            return {}, input_tokens, output_tokens

    def extract_table_from_images(
        self,
        images_base64: list[str],
        additional_context: str = "",
    ) -> dict[str, Any]:
        """
        Extrai itens e dados gerais de tabelas escaneadas / imagens usando
        o Gemini Multimodal com Structured Output estrito.
        """
        prompt = (
            "Analise as imagens da requisição militar em anexo e extraia a tabela completa de itens "
            "com fornecedor, CNPJ, valor total geral e tipo de empenho."
        )
        if additional_context:
            prompt += f"\n\nContexto adicional extraído do documento:\n{additional_context}"

        result, _, _ = self._generate_with_images(
            prompt=prompt,
            images_base64=images_base64,
            schema=RequisitionTableOutput,
            system_instruction=MILITARY_TABLE_SYSTEM_PROMPT,
            operation="extract_table_from_images",
        )
        return result

    def structure_items(self, texto_ou_tabela: str | list) -> dict[str, Any]:
        """Extrai lista de itens a partir de texto ou tabela TSV."""
        if isinstance(texto_ou_tabela, list):
            import io
            buf = io.StringIO()
            for row in texto_ou_tabela:
                buf.write("\t".join(str(c) for c in row) + "\n")
            texto_ou_tabela = buf.getvalue()

        prompt = (
            "A partir do texto/tabela abaixo, extraia todos os itens da requisição em formato estruturado.\n\n"
            f"TEXTO/TABELA:\n{texto_ou_tabela}"
        )
        result, _, _ = self._generate(
            prompt=prompt,
            schema=RequisitionTableOutput,
            operation="structure_items",
        )
        return result

    def structure_header(self, texto: str) -> dict[str, Any]:
        """Extrai campos do cabeçalho da licitação militar."""
        prompt = (
            "Extraia os dados de cabeçalho deste documento de licitação do Exército Brasileiro:\n\n"
            f"TEXTO:\n{texto}"
        )
        result, _, _ = self._generate(
            prompt=prompt,
            schema=HeaderOutput,
            operation="structure_header",
        )
        return result

    def structure_fornecedor(self, texto: str) -> dict[str, Any]:
        """Extrai dados cadastrais do fornecedor."""
        prompt = (
            "Extraia os dados do fornecedor / empresa contratada a partir do texto:\n\n"
            f"TEXTO:\n{texto}"
        )
        result, _, _ = self._generate(
            prompt=prompt,
            schema=SupplierOutput,
            operation="structure_fornecedor",
        )
        return result

    def analyze_dispatch(self, texto: str) -> dict[str, Any]:
        """Analisa despachos e pareceres de processos licitatórios."""
        prompt = (
            "Analise o despacho/parecer do processo licitatório militar e classifique o status:\n\n"
            f"TEXTO:\n{texto}"
        )
        result, _, _ = self._generate(
            prompt=prompt,
            schema=DispatchOutput,
            operation="analyze_dispatch",
        )
        return result

    def classify_nd(
        self, descricao_item: str, tabela_nd: str | list
    ) -> dict[str, Any]:
        """Classifica item na Natureza de Despesa (ND) e subelemento correspondente."""
        if isinstance(tabela_nd, list):
            import io
            buf = io.StringIO()
            for row in tabela_nd:
                buf.write("\t".join(str(c) for c in row) + "\n")
            tabela_nd = buf.getvalue()

        prompt = (
            f"Classifique o item de requisição na Natureza de Despesa correta.\n\n"
            f"DESCRIÇÃO DO ITEM:\n{descricao_item}\n\n"
            f"TABELA DE REFERÊNCIA ND:\n{tabela_nd}"
        )
        result, _, _ = self._generate(
            prompt=prompt,
            schema=NDClassificationOutput,
            operation="classify_nd",
        )
        return result

    def verify_extraction(
        self, texto_original: str, json_extraido: str | dict
    ) -> dict[str, Any]:
        """Compara o texto original com o JSON extraído para auditoria de fidelidade."""
        if isinstance(json_extraido, dict):
            json_extraido = json.dumps(json_extraido, ensure_ascii=False, indent=2)

        prompt = (
            "Compare o TEXTO ORIGINAL com o JSON EXTRAÍDO e aponte eventuais divergências ou dados faltantes.\n\n"
            f"TEXTO ORIGINAL:\n{texto_original}\n\n"
            f"JSON EXTRAÍDO:\n{json_extraido}"
        )
        result, _, _ = self._generate(
            prompt=prompt,
            schema=VerificationOutput,
            operation="verify_extraction",
        )
        return result
