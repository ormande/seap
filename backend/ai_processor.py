"""
Módulo de IA para estruturação de dados extraídos de PDFs de licitações
usando Google Gemini 2.5 Flash.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

# Carrega .env do diretório backend (ou raiz do projeto).
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()

logger = logging.getLogger(__name__)

# Custo aproximado por 1M tokens (Gemini 2.5 Flash, preços típicos em USD).
# Ajuste conforme a tabela oficial do Google.
INPUT_COST_PER_1M = 0.075
OUTPUT_COST_PER_1M = 0.30


def _log_token_usage(
    prompt_tokens: int,
    output_tokens: int,
    operation: str,
) -> None:
    """Registra uso de tokens e custo aproximado da chamada."""
    total = prompt_tokens + output_tokens
    cost = (prompt_tokens / 1_000_000 * INPUT_COST_PER_1M) + (
        output_tokens / 1_000_000 * OUTPUT_COST_PER_1M
    )
    logger.info(
        "Gemini tokens | operação=%s | input=%s | output=%s | total=%s | custo_aprox_usd=%.6f",
        operation,
        prompt_tokens,
        output_tokens,
        total,
        cost,
    )


def _retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    """Executa função com retry exponencial para timeout e rate limit."""
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            msg = str(e).lower()
            if "rate" in msg or "resource" in msg or "429" in msg or "timeout" in msg:
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
    Processador de texto/tabelas extraídos usando Gemini 2.5 Flash
    para gerar JSON estruturado validado.
    """

    MODEL_NAME = "gemini-2.5-flash"

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError(
                "GEMINI_API_KEY não definida. Configure no .env ou passe api_key."
            )
        genai.configure(api_key=key)
        self._model = genai.GenerativeModel(
            self.MODEL_NAME,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

    def _generate(self, prompt: str, operation: str) -> tuple[dict[str, Any], int, int]:
        """
        Chama o modelo e retorna (resposta_parseada, input_tokens, output_tokens).
        Aplica retry exponencial e log de custo.
        """
        def _call() -> Any:
            response = self._model.generate_content(prompt)
            return response

        response = _retry_with_backoff(lambda: _call())
        usage = getattr(response, "usage_metadata", None) or {}
        input_tokens = getattr(usage, "prompt_token_count", None) or 0
        output_tokens = getattr(usage, "candidates_token_count", None) or (
            getattr(usage, "total_token_count", None) or 0
        )
        if output_tokens == 0 and hasattr(response, "candidates") and response.candidates:
            output_tokens = (
                getattr(response.candidates[0], "token_count", None) or 0
            )
        _log_token_usage(input_tokens, output_tokens, operation)

        text = (response.text or "").strip()
        if not text:
            return {}, input_tokens, output_tokens
        # Remove possíveis blocos markdown ```json ... ```
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text), input_tokens, output_tokens

    def structure_header(self, texto: str) -> dict[str, Any]:
        """
        Extrai do texto de cabeçalho: número do processo, UASG, órgão,
        modalidade, objeto e data. Retorna JSON com null para não encontrados.
        """
        prompt = """Você é um assistente que extrai dados estruturados de trechos de documentos de licitação do Exército Brasileiro.

Tarefa: a partir do TEXTO abaixo, extraia os campos listados e retorne APENAS um objeto JSON válido, sem texto adicional. Use null para qualquer campo não encontrado.

Campos obrigatórios no JSON:
- numero_processo (string ou null)
- uasg (string ou null)
- orgao (string ou null)
- modalidade (string ou null, ex: Pregão Eletrônico, Concorrência)
- objeto (string ou null, descrição do objeto da licitação)
- data (string ou null, em formato ISO quando possível)

Exemplo de entrada:
"Processo nº 21.001.567890/2024-12. UASG 123456. Requisição de 1º Batalhão. Objeto: Aquisição de material de escritório."

Exemplo de saída (apenas o JSON):
{"numero_processo": "21.001.567890/2024-12", "uasg": "123456", "orgao": "1º Batalhão", "modalidade": null, "objeto": "Aquisição de material de escritório.", "data": null}

---
TEXTO:
"""
        prompt += texto
        result, _, _ = self._generate(prompt, "structure_header")
        return result

    def structure_items(self, texto_ou_tabela: str | list) -> dict[str, Any]:
        """
        Extrai lista de itens com descrição, quantidade, unidade,
        valor_unitario e valor_total. Aceita texto ou tabela (lista de linhas).
        """
        if isinstance(texto_ou_tabela, list):
            # Serializa tabela para string (ex.: lista de listas)
            import io
            buf = io.StringIO()
            for row in texto_ou_tabela:
                buf.write("\t".join(str(c) for c in row) + "\n")
            texto_ou_tabela = buf.getvalue()

        prompt = """Você é um assistente que extrai itens de licitação (quadro demonstrativo) em JSON.

Tarefa: a partir do TEXTO ou TABELA abaixo, extraia cada item e retorne APENAS um objeto JSON válido com uma chave "itens" cuja valor é uma lista de objetos. Cada objeto deve ter: descricao (string), quantidade (number ou null), unidade (string ou null), valor_unitario (number ou null), valor_total (number ou null). Use null para campos não encontrados.

Exemplo de entrada (tabela):
Item	Descrição	Qtd	Un	Valor Unit.	Valor Total
01	Caneta esferográfica	100	UN	2.50	250.00
02	Resma papel A4	20	RESMA	28.00	560.00

Exemplo de saída (apenas o JSON):
{"itens": [{"descricao": "Caneta esferográfica", "quantidade": 100, "unidade": "UN", "valor_unitario": 2.50, "valor_total": 250.00}, {"descricao": "Resma papel A4", "quantidade": 20, "unidade": "RESMA", "valor_unitario": 28.00, "valor_total": 560.00}]}

---
TEXTO/TABELA:
"""
        prompt += str(texto_ou_tabela)
        result, _, _ = self._generate(prompt, "structure_items")
        return result

    def analyze_dispatch(self, texto: str) -> dict[str, Any]:
        """
        Analisa texto de despacho e retorna: resumo, status
        (aprovado/pendente/com_ressalvas), problemas_identificados e acoes_necessarias.
        """
        prompt = """Você é um assistente que analisa despachos e pareceres de processos licitatórios.

Tarefa: analise o TEXTO abaixo e retorne APENAS um objeto JSON válido com:
- resumo (string): resumo do despacho em uma ou duas frases
- status (string): exatamente um de "aprovado", "pendente", "com_ressalvas"
- problemas_identificados (array de strings): lista de problemas citados, ou []
- acoes_necessarias (array de strings): lista de ações recomendadas, ou []

Use null apenas onde fizer sentido; arrays vazios quando não houver itens.

Exemplo de entrada:
"Despacho: Analisado o processo, determino a aprovação para aquisição. Fica pendente a entrega da documentação fiscal."

Exemplo de saída (apenas o JSON):
{"resumo": "Aprovação para aquisição com pendência de documentação fiscal.", "status": "com_ressalvas", "problemas_identificados": ["Documentação fiscal não entregue"], "acoes_necessarias": ["Entregar documentação fiscal"]}

---
TEXTO:
"""
        prompt += texto
        result, _, _ = self._generate(prompt, "analyze_dispatch")
        return result

    def structure_fornecedor(self, texto: str) -> dict[str, Any]:
        """
        Extrai dados do fornecedor: CNPJ, razão social, endereço etc.
        Retorna JSON com null para campos não encontrados.
        """
        prompt = """Você é um assistente que extrai dados de fornecedor de documentos de licitação.

Tarefa: a partir do TEXTO abaixo, extraia os campos e retorne APENAS um objeto JSON válido. Use null para qualquer campo não encontrado.

Campos: cnpj (string ou null), razao_social (string ou null), nome_fantasia (string ou null), endereco (string ou null), municipio (string ou null), uf (string ou null).

Exemplo de entrada:
"Fornecedor: Empresa ABC Ltda. CNPJ 12.345.678/0001-90. Endereço: Rua X, 100 - São Paulo/SP."

Exemplo de saída (apenas o JSON):
{"cnpj": "12.345.678/0001-90", "razao_social": "Empresa ABC Ltda", "nome_fantasia": null, "endereco": "Rua X, 100", "municipio": "São Paulo", "uf": "SP"}

---
TEXTO:
"""
        prompt += texto
        result, _, _ = self._generate(prompt, "structure_fornecedor")
        return result

    def classify_nd(
        self, descricao_item: str, tabela_nd: str | list
    ) -> dict[str, Any]:
        """
        Dada a descrição do item e uma tabela de natureza de despesa,
        retorna o subelemento mais provável.
        """
        if isinstance(tabela_nd, list):
            import io
            buf = io.StringIO()
            for row in tabela_nd:
                buf.write("\t".join(str(c) for c in row) + "\n")
            tabela_nd = buf.getvalue()

        prompt = """Você é um assistente que classifica itens de licitação em natureza de despesa (ND).

Tarefa: com base na DESCRIÇÃO do item e na TABELA de natureza de despesa (código / descrição / subelemento), retorne APENAS um objeto JSON válido com:
- subelemento (string ou null): o código ou nome do subelemento mais adequado
- codigo_nd (string ou null): código da ND se disponível na tabela
- confianca (string): "alta", "media" ou "baixa"

Exemplo de entrada:
Descrição: "Caneta esferográfica azul"
Tabela ND:
3.3.90.30	Material de consumo p/ escritório	3.3.90.30.01
3.3.90.39	Outros materiais	3.3.90.39.00

Exemplo de saída (apenas o JSON):
{"subelemento": "3.3.90.30.01", "codigo_nd": "3.3.90.30", "confianca": "alta"}

---
DESCRIÇÃO DO ITEM:
"""
        prompt += descricao_item + "\n\nTABELA ND:\n" + str(tabela_nd)
        result, _, _ = self._generate(prompt, "classify_nd")
        return result

    def verify_extraction(
        self, texto_original: str, json_extraido: str | dict
    ) -> dict[str, Any]:
        """
        Segunda etapa: compara texto original com o JSON extraído e retorna
        score de confiança (0-1) e lista de correções sugeridas.
        """
        if isinstance(json_extraido, dict):
            json_extraido = json.dumps(json_extraido, ensure_ascii=False, indent=2)

        prompt = """Você é um revisor que verifica se os dados extraídos de um documento batem com o texto original.

Tarefa: compare o TEXTO ORIGINAL com o JSON EXTRAÍDO e retorne APENAS um objeto JSON válido com:
- score_confianca (number): entre 0 e 1 (1 = total aderência)
- correcoes (array de objetos): cada objeto com "campo" (string), "valor_atual" (string), "sugestao" (string), "motivo" (string). Se não houver correções, retorne []

Exemplo de saída quando está correto (apenas o JSON):
{"score_confianca": 0.95, "correcoes": []}

Exemplo quando há uma correção (apenas o JSON):
{"score_confianca": 0.7, "correcoes": [{"campo": "numero_processo", "valor_atual": "21.001.567890", "sugestao": "21.001.567890/2024-12", "motivo": "Faltava ano no texto original"}]}

---
TEXTO ORIGINAL:
"""
        prompt += texto_original + "\n\n---\nJSON EXTRAÍDO:\n" + json_extraido
        result, _, _ = self._generate(prompt, "verify_extraction")
        return result
