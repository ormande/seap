"""
Estágio 2 — Análise da peça da requisição.

Responsável por:
- Identificar as páginas que compõem a peça da requisição.
- Extrair instrumento, UASG, tipo de empenho, fornecedor, CNPJ e tabela de itens.
- Verificar automaticamente os cálculos da tabela (quantidade x valor unitário).
- Integrar com Gemini como fallback quando regex não for suficiente.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import traceback
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from ..ai_processor import GeminiProcessor
except ImportError:
    from ai_processor import GeminiProcessor

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from azure_processor import extract_table_text_with_azure
except Exception as e1:
    try:
        from ..azure_processor import extract_table_text_with_azure
    except Exception as e2:
        print(f"\n{'='*50}", flush=True)
        print("[Stage2][?] FALHA AO IMPORTAR AZURE_PROCESSOR!", flush=True)
        print(f"Erro Absoluto: {e1}", flush=True)
        print(f"Erro Relativo: {e2}", flush=True)
        print(f"{'='*50}\n", flush=True)
        extract_table_text_with_azure = None  # type: ignore[assignment]

try:
    from extractor import get_pages_with_large_images, page_to_base64
except Exception as e1:
    try:
        from ..extractor import get_pages_with_large_images, page_to_base64
    except Exception as e2:
        print(f"\n{'='*50}", flush=True)
        print("[Stage2][?] FALHA AO IMPORTAR EXTRACTOR!", flush=True)
        print(f"Erro Absoluto: {e1}", flush=True)
        print(f"Erro Relativo: {e2}", flush=True)
        print(f"{'='*50}\n", flush=True)
        get_pages_with_large_images = None  # type: ignore[assignment]
        page_to_base64 = None  # type: ignore[assignment]

try:
    from ..models import (
        Stage2Confidence,
        Stage2Data,
        Stage2Divergencia,
        Stage2Instrument,
        Stage2Item,
        Stage2Result,
        Stage2TipoEmpenho,
        Stage2CNPJDetails,
        Stage2UASG,
        Stage2UASGDetails,
        Stage2VerificacaoCalculos,
    )
except ImportError:
    from models import (
        Stage2Confidence,
        Stage2Data,
        Stage2Divergencia,
        Stage2Instrument,
        Stage2Item,
        Stage2Result,
        Stage2TipoEmpenho,
        Stage2CNPJDetails,
        Stage2UASG,
        Stage2UASGDetails,
        Stage2VerificacaoCalculos,
    )

logger = logging.getLogger(__name__)


INSTRUMENTO_REGEX = re.compile(
    r"por\s+meio\s+d[oea]\s+"
    r"("
    r"Preg[aã]o(?:\s+Eletr[oô]nico)?"
    r"|[Cc]ontrato"
    r"|[Dd]ispensa(?:\s+de\s+[Ll]icita[çc][aã]o)?"
    r"|[Ii]nexigibilidade"
    r"|[Cc]hamada\s+[Pp][uú]blica"
    r"|[Aa]ta\s+de\s+[Rr]egistro\s+de\s+[Pp]re[çc]os"
    r")"
    r"\s*n?[°ºo.]?\s*"
    r"(\d+/\d{2,4})",
    flags=re.IGNORECASE,
)

UASG_AFTER_INSTRUMENTO_REGEX = re.compile(
    r"(?:UASG|UG|pela)\s*\(?\s*(16\d{4})\s*\)?\s*[–\-—]\s*(.+?)(?:\.|,|do\s+qual|da\s+qual|\)|$)",
    flags=re.IGNORECASE,
)

INSTRUMENTO_CAMPO6_REGEX = re.compile(
    r"(?:"
    r"(?:PE|PREG[AÃ]O(?:\s+ELETR[OÔ]NICO)?|CONTRATO|DISPENSA|CHAMADA\s+P[UÚ]BLICA)"
    r")\s*"
    r"(?:N[°ºo.]?\s*)?"
    r"(\d+/\d{2,4})"
    r"(?:[,\s]+UASG[:\s]*(16\d{4}))?",
    flags=re.IGNORECASE,
)

CANDIDATE_UASG_FLEX_REGEX = re.compile(
    r"(?:gerenciad[oa]\s+pel[oa]\s*(?:UASG|UG)?\s*|UASG\s*|UG\s*|pela\s*)"
    r"(16\d{4})\s*[–\-\s—]+\s*(.+?)(?:\.|,|do\s+qual|$)",
    flags=re.IGNORECASE,
)

# Padrões adicionais para instrumentos em formato telegráfico/abreviado.
INSTRUMENTO_PE_SIGLA_REGEX = re.compile(
    r"\bPE\s+(\d+/\d{2,4})",
    flags=re.IGNORECASE,
)

INSTRUMENTO_PREGao_CURTO_REGEX = re.compile(
    r"\bPREG[AÃ]O\b(?:\s+ELETR[OÔ]NICO)?\s*(?:N[º°o\.]|NR\.?|Nº|N°)?\s*\.?\s*(\d+/\d{2,4})",
    flags=re.IGNORECASE,
)

# Fallback quando o cache (banco) ainda não tiver a UASG.
UASG_TO_OM: Dict[str, str] = {}

# Seed local mínimo de UASGs (9ª RM) para uso seguro em testes e runtimes
# que ainda não executaram o startup da API (carregamento do cache/banco).
_UASG_SEED_FALLBACK_9RM: Dict[str, str] = {
    "160078": "Colégio Militar de Campo Grande",
    "160095": "58º Batalhão de Infantaria Motorizado",
    "160131": "17º Regimento de Cavalaria Mecanizado",
    "160132": "9º Batalhão de Engenharia de Combate",
    "160133": "10º Regimento de Cavalaria Mecanizado",
    "160136": "9º Grupamento Logístico",
    "160140": "9ª Região Militar",
    "160141": "Comissão Regional de Obras da 9ª Região Militar",
    "160142": "9º Batalhão de Suprimento",
    "160143": "Hospital Militar de Área de Campo Grande",
    "160145": "17º Batalhão de Fronteira",
    "160146": "Comando da 18ª Brigada de Infantaria de Pantanal",
    "160147": "47º Batalhão de Infantaria",
    "160149": "Comando da 4ª Brigada de Cavalaria Mecanizada",
    "160150": "4ª Companhia de Engenharia de Combate Mecanizada",
    "160151": "9º Grupo de Artilharia de Campanha",
    "160152": "11º Regimento de Cavalaria Mecanizado",
    "160153": "2ª Companhia de Fronteira",
    "160155": "Comando de Fronteira de Jauru/66º Batalhão de Infantaria Motorizado",
    "160156": "44º Batalhão de Infantaria Motorizado",
    "160157": "9º Batalhão de Engenharia de Construção",
    "160158": "Comando da 13ª Brigada Infantaria Motorizada",
    "160159": "18º Grupo de Artilharia de Campanha",
    "160512": "20º Regimento de Cavalaria Blindado",
    "160521": "3ª Bateria de Artilharia Antiaérea",
    "160522": "28º Batalhão Logístico",
    "160530": "Base de Administração e Apoio do Comando Militar do Oeste",
}

try:
    try:
        from ..database import UASG_SEED_9RM  # type: ignore[import]
    except ImportError:
        from database import UASG_SEED_9RM  # type: ignore[import]
except Exception:
    UASG_SEED_9RM = _UASG_SEED_FALLBACK_9RM

for _codigo, _nome in (UASG_SEED_9RM or {}).items():
    if _codigo and _codigo not in UASG_TO_OM:
        UASG_TO_OM[_codigo] = _nome

CNPJ_STRICT_REGEX = re.compile(
    r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$",
)


def _validate_cnpj_digits(digits: str) -> bool:
    """
    Valida CNPJ pelo algoritmo oficial de dígitos verificadores.

    - Exige exatamente 14 dígitos;
    - Rejeita sequências com todos os dígitos iguais;
    - Calcula os 2 dígitos verificadores e compara com o valor informado.
    """
    if not digits or len(digits) != 14:
        return False
    if digits == digits[0] * 14:
        return False

    def _calc_digit(seq: str, weights: list[int]) -> int:
        total = sum(int(d) * w for d, w in zip(seq, weights))
        resto = total % 11
        return 0 if resto < 2 else 11 - resto

    base = digits[:12]
    dv1_expected = _calc_digit(base, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    dv2_expected = _calc_digit(
        base + str(dv1_expected),
        [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
    )

    dv1_real = int(digits[12])
    dv2_real = int(digits[13])
    return dv1_real == dv1_expected and dv2_real == dv2_expected

REQ_ANCHOR_REGEX = re.compile(
    r"\bReq\.?\s*(?:n[º°o\.]|nr\.?|nº|Nº|N°)?\s*\d+",
    flags=re.IGNORECASE,
)


STAGE2_TABLE_PROMPT = """
Você é um auditor militar especialista em extração de tabelas de licitação.

Analise a IMAGEM ou TEXTO da tabela de itens e extraia os dados com precisão absoluta.
Como tabelas escaneadas podem ser confusas, você DEVE seguir este processo de raciocínio lógico no campo "raciocinio_matematico" ANTES de preencher os itens:

Para CADA linha da tabela:
1. Leia a Quantidade (QTD).
2. Leia o Valor Unitário (VU).
3. Leia o Valor Total (VT) que está escrito na imagem.
4. Multiplique QTD * VU.
5. Se o resultado da sua multiplicação for diferente do VT escrito na imagem (com tolerância de R$ 0,02), VOCÊ LEU ALGUM NÚMERO ERRADO. Olhe novamente para a imagem com mais cuidado, aproxime a visão e corrija sua leitura até a matemática bater perfeitamente.

Retorne APENAS um objeto JSON válido neste exato formato:

{
  "raciocinio_matematico": [
    "Item 1: Lidos QTD=10 e VU=2.50. Calculado 10*2.50=25.00. Escrito na imagem=25.00. Bateu perfeitamente.",
    "Item 2: Lidos QTD=5 e VU=10.00. Calculado 5*10=50. Escrito na imagem=80.00. ERRO. Relendo a imagem... Ah, a QTD correta é 8. 8*10=80.00. Corrigido."
  ],
  "fornecedor": "nome da empresa ou null",
  "cnpj": "XX.XXX.XXX/XXXX-XX ou null",
  "itens": [
    {
      "item": 1,
      "catmat": "código ou null",
      "descricao": "descrição",
      "unidade": "und",
      "quantidade": 10,
      "nd_si": "30.24",
      "valor_unitario": 2.50,
      "valor_total": 25.00
    }
  ],
  "valor_total_geral": 25.00
}

REGRAS:
- Use ponto decimal (ex: 1500.50).
- Unidade preserva letras (Un, Sv, Kg). Catmat SÓ números. ND sempre em formato EE.SS.
- CNPJ tem SEMPRE 14 dígitos (não confunda com NUP).
- Preencha todos os campos do JSON, extraia todos os itens da tabela.
""".strip()


STAGE2_GENERAL_PROMPT = """
Você é um especialista em documentos de licitação do governo brasileiro e Exército Brasileiro.

Analise o texto abaixo extraído da PEÇA DA REQUISIÇÃO de um processo
licitatório militar e extraia os seguintes campos:

1. INSTRUMENTO: tipo (Pregão Eletrônico, Contrato, Dispensa ou
   Inexigibilidade) e número. Aparece no primeiro parágrafo/tópico.
2. UASG: código de 6 dígitos (começa com 16) e nome da OM gerenciadora.
   Aparece próximo ao instrumento.
3. TIPO DE EMPENHO: Ordinário, Estimativo ou Global.
   Pode estar no cabeçalho ou no tópico sobre tipo de empenho.
4. FORNECEDOR: nome da empresa. Aparece antes da tabela de itens.
5. CNPJ: formato XX.XXX.XXX/XXXX-XX. Aparece próximo ao fornecedor.

EXEMPLO:
Texto: "...aprovar as despesas com aquisição de materiais por meio do
Pregão Eletrônico nº 90004/2025 gerenciado pela UASG 160142 – 
9º Batalhão de Suprimento..."
Resposta parcial: {"instrumento": {"tipo": "Pregão Eletrônico",
"numero": "90004/2025"}, "uasg": {"codigo": "160142",
"nome": "9º Batalhão de Suprimento"}}

Retorne APENAS JSON válido, sem markdown.
Se não encontrar um campo, use null.
Inclua campo "confianca" de 0 a 100.
""".strip()


STAGE2_INSTR_UASG_FALLBACK_PROMPT = """
Você é um especialista em documentos de licitação do governo brasileiro.

Analise o texto abaixo (primeiras páginas de um processo licitatório) e
identifique APENAS:

- instrumento_tipo: "Pregão Eletrônico", "Contrato", "Dispensa",
  "Inexigibilidade" ou "Ata de Registro de Preços"
- instrumento_numero: número do instrumento no formato "999/9999"
- uasg: código UASG/UG de 6 dígitos (ex.: 160142)

Retorne APENAS JSON válido no formato:
{"instrumento_tipo": "...", "instrumento_numero": "...", "uasg": "..."}

Se não encontrar algum campo, use null.
""".strip()


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def format_om_name(name: str) -> str:
    """
    Formata o nome da OM para Title Case, mantendo preposições em minúsculo.
    Ex.: "9º GRUPAMENTO LOGÍSTICO" -> "9º Grupamento Logístico".
    """
    prepositions = {"de", "do", "da", "dos", "das", "e", "o", "a"}
    words = name.title().split()
    return " ".join(
        w.lower() if w.lower() in prepositions and i > 0 else w
        for i, w in enumerate(words)
    )


def _normalize_for_regex(text: str) -> str:
    """
    Normaliza texto para aumentar robustez de regex:
    - Remove quebras de linha (vira espaço)
    - Colapsa múltiplos espaços
    - Remove espaços não-quebráveis
    """
    return _normalize_whitespace((text or "").replace("\u00a0", " ").replace("\n", " "))


def normalize_instrument_year(numero: str) -> str:
    """
    Garante que o ano no número do instrumento tenha 4 dígitos.

    Regra: só normalizar se o ano tiver EXATAMENTE 2 dígitos.
    O ano é considerado como o trecho após a última barra "/" ou hífen "-".
    """
    match = re.search(r"[/-](\d+)$", numero)
    if match:
        year_part = match.group(1)
        if len(year_part) == 2:
            try:
                year_int = int(year_part)
            except ValueError:
                return numero
            year_4d = f"20{year_part}" if year_int < 50 else f"19{year_part}"
            # Substitui apenas a parte do ano, preservando o restante do número.
            return numero[: match.start(1)] + year_4d
        # Se já tiver 4 dígitos (ou outro tamanho), não alterar.
    return numero


def _safe_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        cleaned = cleaned.replace("R$", "").replace(" ", "")
        cleaned = cleaned.replace(".", "").replace(",", ".")
        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return None
    return None


def _normalize_cnpj(value: Any) -> Optional[str]:
    """
    Normaliza um possível CNPJ, garantindo que não seja confundido com NUP.
    Formato final: XX.XXX.XXX/XXXX-XX (14 dígitos).
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    if len(digits) != 14:
        return None
    if not _validate_cnpj_digits(digits):
        return None
    formatted = (
        f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"
    )
    if not CNPJ_STRICT_REGEX.fullmatch(formatted):
        return None
    return formatted


def extract_cnpj_candidates(
    text: str,
    section: str = "requisicao",
    page_scope: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Gera candidatos de CNPJ a partir do texto da requisição, sem usar IA.

    Cada candidato contém, no mínimo:
    - value: apenas dígitos (14)
    - formatted_value: XX.XXX.XXX/XXXX-XX
    - score: float (ajustado depois no resolvedor)
    - source: identificação do padrão que gerou o candidato
    - section: ex.: 'requisicao'
    - matched_text: trecho original da linha/janela
    - normalized_text: igual ao formatted_value
    - reasons: lista de strings (evidências)
    """
    full_text = text or ""
    candidates: List[Dict[str, Any]] = []

    def _base_candidate(
        value_raw: str,
        source: str,
        match_span: Tuple[int, int],
        extra_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        start, end = match_span
        matched_text = full_text[start:end]
        window_start = max(0, start - 120)
        window_end = min(len(full_text), end + 120)
        window = full_text[window_start:window_end]

        digits = re.sub(r"\D", "", value_raw)
        formatted = _normalize_cnpj(digits)

        cand: Dict[str, Any] = {
            "value": digits if digits else None,
            "formatted_value": formatted,
            "score": 0.0,
            "source": source,
            "section": section,
            "page_scope": page_scope,
            "matched_text": matched_text,
            "normalized_text": formatted,
            "reasons": [],
            "context_window": window,
        }
        if extra_reason:
            cand["reasons"].append(extra_reason)
        return cand

    # 1) Padrões explícitos com rótulo CNPJ ou CPF/CNPJ.
    labeled_regex = re.compile(
        r"(?P<label>\bCNPJ\b|\bCPF\/CNPJ\b).{0,40}?(?P<cnpj>\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}|\d{14})",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for m in labeled_regex.finditer(full_text):
        span = m.span("cnpj")
        label = m.group("label")
        value_raw = m.group("cnpj")
        cand = _base_candidate(
            value_raw,
            "label_cnpj",
            span,
            extra_reason=f"Número logo após rótulo '{label}'.",
        )
        candidates.append(cand)

    # 2) Frases de inscrição: "inscrita no CNPJ sob o nº ..."
    inscrita_regex = re.compile(
        r"inscrit[ao]s?\s+no\s+cnpj[^0-9]{0,40}?(?P<cnpj>\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}|\d{14})",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for m in inscrita_regex.finditer(full_text):
        span = m.span("cnpj")
        value_raw = m.group("cnpj")
        cand = _base_candidate(
            value_raw,
            "inscrita_no_cnpj",
            span,
            extra_reason="Frase explícita de inscrição no CNPJ.",
        )
        candidates.append(cand)

    # 3) Linhas com fornecedor/empresa/contratada e um CNPJ próximo.
    context_tokens = [
        "fornecedor",
        "empresa",
        "contratada",
        "contratado",
        "favorecida",
        "favorecido",
        "razao social",
        "razão social",
    ]
    lines = full_text.splitlines()
    offset = 0
    for line in lines:
        line_start = offset
        line_end = offset + len(line)
        offset += len(line) + 1
        line_lower = line.lower()
        if not any(tok in line_lower for tok in context_tokens):
            continue

        for m in re.finditer(
            r"(\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}|\d{14})",
            line,
        ):
            span = (line_start + m.start(1), line_start + m.end(1))
            value_raw = m.group(1)
            cand = _base_candidate(
                value_raw,
                "linha_fornecedor",
                span,
                extra_reason="Linha com contexto forte de fornecedor/empresa.",
            )
            cand["line_length"] = len(line.strip())
            candidates.append(cand)

    return candidates


def resolve_cnpj(
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Resolve o melhor CNPJ a partir da lista de candidatos.

    Retorna:
    {
      "value": str | None,              # dígitos
      "formatted_value": str | None,    # XX.XXX.XXX/XXXX-XX
      "confidence": int 0-100,
      "source": str | None,
      "matched_text": str | None,
      "normalized_text": str | None,
      "candidates": [...],
      "reason": str,
    }
    """
    if not candidates:
        return {
            "value": None,
            "formatted_value": None,
            "confidence": 0,
            "candidates": [],
            "reason": "Nenhum candidato de CNPJ identificado.",
        }

    for cand in candidates:
        score = 0.0
        reasons = cand.get("reasons", [])
        source = str(cand.get("source") or "")
        section = str(cand.get("section") or "")
        window = cand.get("context_window") or ""
        window_lower = str(window).lower()
        digits = re.sub(r"\D", "", str(cand.get("value") or ""))

        is_valid = _validate_cnpj_digits(digits) if len(digits) == 14 else False
        cand["is_valid"] = is_valid

        # Bônus principais conforme a origem.
        if source == "label_cnpj":
            score += 70.0
            reasons.append("Número logo após rótulo explícito de CNPJ.")
        elif source == "inscrita_no_cnpj":
            score += 65.0
            reasons.append("Frase de inscrição explícita no CNPJ.")
        elif source == "linha_fornecedor":
            score += 55.0
            reasons.append("Linha com contexto forte de fornecedor/empresa.")

        if section == "requisicao":
            score += 5.0

        # Bônus por tokens de contexto positivos na janela.
        positive_ctx = [
            "cnpj",
            "cpf/cnpj",
            "fornecedor",
            "empresa",
            "contratada",
            "contratado",
            "favorecida",
            "favorecido",
            "razao social",
            "razão social",
            "inscrita no cnpj",
        ]
        if any(tok in window_lower for tok in positive_ctx):
            score += 10.0
            reasons.append("Janela contém termos típicos de identificação de fornecedor.")

        # Penalização forte para contextos típicos de números administrativos.
        false_ctx = [
            "nup",
            "processo",
            "nc ",
            "nota de credito",
            "ptres",
            "evento",
            "fonte",
            "esfera",
            "ug emitente",
            "natureza de despesa",
            "nd ",
            "pi ",
        ]
        if any(tok in window_lower for tok in false_ctx):
            score -= 40.0
            reasons.append("Contexto sugere número administrativo, não CNPJ.")

        # Penalidade para candidatos sem qualquer rótulo de identificação.
        if not any(tok in window_lower for tok in ["cnpj", "cpf/cnpj"]) and source != "linha_fornecedor":
            score -= 15.0
            reasons.append("Número sem rótulo de CNPJ na vizinhança.")

        # Penalidade forte para CNPJ que falha na validação dos dígitos.
        if not is_valid:
            score -= 60.0
            reasons.append("Falha na validação de dígitos verificadores do CNPJ.")

        # Bônus leve para linhas curtas e objetivas com fornecedor + CNPJ.
        line_len = cand.get("line_length")
        if isinstance(line_len, int) and line_len and line_len <= 80:
            score += 5.0
            reasons.append("Linha curta e objetiva reforça a confiabilidade do CNPJ.")

        cand["score"] = score
        cand["reasons"] = reasons

    # Agregar consenso por valor formatado.
    by_value: Dict[str, List[Dict[str, Any]]] = {}
    for cand in candidates:
        formatted = str(cand.get("formatted_value") or "").strip()
        if not formatted:
            continue
        by_value.setdefault(formatted, []).append(cand)

    for _, group in by_value.items():
        if len(group) >= 2:
            for cand in group:
                cand["score"] = float(cand.get("score", 0.0)) + 15.0
                reasons = cand.get("reasons", [])
                reasons.append("Consenso entre múltiplas ocorrências para o mesmo CNPJ.")
                cand["reasons"] = reasons

    sorted_cands = sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)
    best = sorted_cands[0]
    best_score = float(best.get("score", 0.0))

    confidence = int(max(0.0, min(100.0, best_score)))

    # Se o melhor candidato ainda for inválido ou com confiança baixa, não promove.
    if confidence <= 0 or not best.get("is_valid"):
        return {
            "value": None,
            "formatted_value": None,
            "confidence": 0,
            "candidates": sorted_cands,
            "reason": "Candidatos de CNPJ encontrados, mas todos com score muito baixo, contexto duvidoso ou dígitos inválidos.",
        }

    reason_parts: List[str] = best.get("reasons", []) or ["Melhor score entre candidatos de CNPJ."]

    return {
        "value": re.sub(r"\D", "", str(best.get("value") or "")) or None,
        "formatted_value": best.get("formatted_value"),
        "confidence": confidence,
        "source": best.get("source"),
        "matched_text": best.get("matched_text"),
        "normalized_text": best.get("normalized_text"),
        "candidates": sorted_cands,
        "reason": "; ".join(reason_parts),
    }


def _is_instrument_page(text: str) -> bool:
    """
    Retorna True se a página pertence a um documento do instrumento
    (edital, contrato, chamada pública etc.), NÃO da requisição.
    """
    if not text:
        return False
    text = str(text)
    upper = text.upper()
    lines = [ln.strip().upper() for ln in text.splitlines() if ln.strip()]
    first_lines = "\n".join(lines[:25])
    # Títulos/cabeçalhos de documentos do instrumento
    if re.search(r"\bEDITAL\b", first_lines):
        return True
    if re.search(r"\bCHAMADA\s+P[UÚ]BLICA\b", first_lines):
        return True
    if "ATA DE REGISTRO DE PREÇOS" in upper:
        return True
    if "EXTRATO DE CONTRATO" in upper:
        return True
    if re.search(r"\bTERMO\s+DE\s+REFER[EÊ]NCIA\b", first_lines):
        return True
    # Contrato: contratante e contratada
    if "CONTRATANTE" in upper and "CONTRATADA" in upper:
        return True
    # Cláusulas contratuais
    if re.search(r"\bCL[ÁA]USULA\b", upper):
        return True
    if re.search(r"\bDA\s+VIG[EÊ]NCIA\b", upper):
        return True
    if re.search(r"\bDAS\s+OBRIGA[ÇC][OÕ]ES\b", upper):
        return True
    return False


def _is_requisition_end(text: str) -> bool:
    """
    Retorna True se a página contém sinais de encerramento da requisição
    (linha de assinatura, posto/graduação, fiscal, ordenador).
    """
    if not text:
        return False
    text = str(text)
    upper = text.upper()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Linha com 10+ underscores (linha de assinatura)
    if re.search(r"_{10,}", text):
        return True
    # Posto/graduação militar em linha curta (assinante)
    rank_pattern = re.compile(
        r"^\s*(CAP|MAJ|TEN\s*CEL|CEL|1[º°]\s*TEN|2[º°]\s*TEN|ST|1[º°]\s*SGT|2[º°]\s*SGT|3[º°]\s*SGT|CB)\s*$",
        re.IGNORECASE,
    )
    for ln in lines[-15:]:  # rodapé da página
        if len(ln) < 50 and rank_pattern.search(ln):
            return True
    # Fiscal Adm ou Ch + seção/OM
    if "FISCAL ADM" in upper or re.search(r"\bCH\s+[A-Z0-9/]", upper):
        return True
    if "ORDENADOR DE DESPESAS" in upper:
        return True
    return False


def _find_requisition_pages_legacy(all_pages: Dict[str, str], nup_id: str = "") -> List[int]:
    """
    Lógica legada: identifica páginas da requisição a partir de "Req nº" + "Assunto".
    Mantida como fallback quando a âncora do campo 6 não é encontrada.
    """
    page_items: List[Tuple[int, str]] = []
    for key, text in all_pages.items():
        if not key.startswith("pagina_"):
            continue
        try:
            idx = int(key.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        page_items.append((idx, text or ""))

    page_items.sort(key=lambda x: x[0])

    start_page: Optional[int] = None

    debug_candidates: List[Dict[str, Any]] = []

    for idx, text in page_items:
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        if not lines:
            continue

        joined = "\n".join(lines[:15])
        has_req = bool(REQ_ANCHOR_REGEX.search(joined))
        window = "\n".join(lines[:40]).upper()
        has_assunto = "ASSUNTO" in window
        has_tipo_empenho = "TIPO DE EMPENHO" in window
        has_ao_do = any(
            ln.upper().startswith(("AO ", "AO:", "DO ", "DO:")) for ln in lines[:20]
        )

        debug_candidates.append(
            {
                "page": idx,
                "has_req": has_req,
                "has_assunto": has_assunto,
                "has_tipo_empenho": has_tipo_empenho,
                "has_ao_do": has_ao_do,
            }
        )

        if has_req and (has_assunto or has_tipo_empenho or has_ao_do):
            start_page = idx
            break

    if start_page is None:
        logger.debug(
            "Stage2 legado: nenhuma página de requisição identificada. Candidatos avaliados: %s",
            debug_candidates,
        )
        return []

    requisition_pages: List[int] = [start_page]
    max_continuation = 5
    continuation_count = 0

    def _looks_like_continuation(text: str) -> bool:
        if not text:
            return False
        text = str(text)
        upper = text.upper()
        if "REQUISIÇÃO" in upper or "MATERIAL" in upper or "SERVIÇO A SER ADQUIRIDO" in upper:
            return True
        if re.search(r"^\s*\d+\.", text, flags=re.MULTILINE):
            return True
        if "Nº DA REQUISIÇÃO" in upper or "Nº REQ" in upper:
            return True
        return False

    started = False
    for idx, text in page_items:
        if idx == start_page:
            started = True
            continue
        if not started:
            continue
        if continuation_count >= max_continuation:
            break
        text = (all_pages.get(f"pagina_{idx}") or "") if not isinstance(text, str) else text
        page_text = text or ""
        if _is_instrument_page(page_text):
            break
        if _is_requisition_end(page_text):
            requisition_pages.append(idx)
            break
        if _looks_like_continuation(page_text):
            requisition_pages.append(idx)
            continuation_count += 1
        else:
            break

    logger.debug(
        "Stage2 legado: páginas de requisição identificadas: %s (candidatos=%s)",
        requisition_pages,
        debug_candidates,
    )

    return requisition_pages


def find_requisition_pages(all_pages: Dict[str, str], nup_id: str = "") -> List[int]:
    """
    Identifica as páginas que compõem a peça da requisição usando como âncora
    o campo 6 ("Material/Serviço a ser adquirido/contratado"), expandindo para
    trás e para frente. Se a âncora não existir, usa a heurística legada.
    """
    ANCHOR_CAMPO6 = re.compile(
        r"6\.\s*Material(?:/Servi[çc]o)?\s+a\s+ser\s+(?:adquirido|contratado)",
        re.IGNORECASE,
    )

    # Organizar páginas em (numero, texto)
    page_items: List[Tuple[int, str]] = []
    for key, text in all_pages.items():
        if not key.startswith("pagina_"):
            continue
        try:
            idx = int(key.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        page_items.append((idx, text or ""))
    page_items.sort(key=lambda x: x[0])

    if not page_items:
        return []

    # 1. Encontrar página-âncora (campo 6)
    anchor_page: Optional[int] = None
    for idx, text in page_items:
        if ANCHOR_CAMPO6.search(text or ""):
            anchor_page = idx
            break

    if anchor_page is None:
        print(
            f"[Stage2][{nup_id}] Âncora campo 6 não encontrada, usando fallback legado",
            flush=True,
        )
        return _find_requisition_pages_legacy(all_pages, nup_id=nup_id)

    print(f"[Stage2][{nup_id}] Âncora campo 6 encontrada na pg {anchor_page}", flush=True)

    # Mapas auxiliares
    page_map: Dict[int, str] = {idx: text for idx, text in page_items}
    all_indices: List[int] = [idx for idx, _ in page_items]
    anchor_pos = all_indices.index(anchor_page)

    requisition_pages: List[int] = [anchor_page]

    # 2. Expandir pra trás
    STOP_BACKWARD = re.compile(
        r"Termo de Abertura"
        r"|PE[ÇC]AS\s+PROCESSUAIS"
        r"|Classifica[çc][aã]o:"
        r"|PROCESSO\s+NUP"
        r"|C[oó]d\s+verificador"
        r"|MINUTA\s+DO\s+CONTRATO",
        re.IGNORECASE,
    )
    REQ_INDICATORS = re.compile(
        r"Tipo de Empenho"
        r"|Do\s+Cmt"
        r"|Ao\s+Sr\s+Ordenador"
        r"|Rfr:"
        r"|Assunto:\s*Aquisi"
        r"|solicito-vos\s+provid[eê]ncias"
        r"|aprovar\s+as\s+despesas"
        r"|^\s*[1-5]\.",
        re.IGNORECASE | re.MULTILINE,
    )

    for i in range(anchor_pos - 1, -1, -1):
        prev_idx = all_indices[i]
        prev_text = page_map.get(prev_idx, "") or ""

        if STOP_BACKWARD.search(prev_text):
            break
        if REQ_INDICATORS.search(prev_text):
            requisition_pages.insert(0, prev_idx)
        else:
            break

    # 3. Expandir pra frente
    STOP_FORWARD = re.compile(
        r"CL[AÁ]USULA"
        r"|Edital\s+\d"
        r"|Nota\s+de\s+Cr[eé]dito"
        r"|SICAF"
        r"|CADIN"
        r"|Despacho\s+N[°ºo]"
        r"|Termo\s+de\s+Refer[eê]ncia"
        r"|Consulta\s+Consolidada"
        r"|Chamada\s+P[uú]blica\s+n"
        r"|PREG[AÃ]O\s+ELETR[OÔ]NICO\s+N",
        re.IGNORECASE,
    )
    CONTINUATION_INDICATORS = re.compile(
        r"TOTAL\s+FORNECEDOR"
        r"|Visto\s+do\s+Fisc"
        r"|Fisc\s+Adm"
        r"|Ch\s+do\s+St"
        r"|^\s*\d+\s+\d{4,6}\s+"
        r"|ITEM\s+.*(CATMAT|Descri)"
        r"|Material/Servi[çc]o",
        re.IGNORECASE | re.MULTILINE,
    )

    for i in range(anchor_pos + 1, len(all_indices)):
        next_idx = all_indices[i]
        next_text = page_map.get(next_idx, "") or ""

        if STOP_FORWARD.search(next_text):
            break
        if CONTINUATION_INDICATORS.search(next_text):
            requisition_pages.append(next_idx)
        else:
            break

    print(f"[Stage2][{nup_id}] Req páginas (via âncora): {requisition_pages}", flush=True)
    return requisition_pages


def _normalize_instrument_type(raw_type: str) -> str:
    """Normaliza o tipo do instrumento para valor canônico."""
    lower = raw_type.strip().lower()
    if lower == "pe" or lower.startswith("pe "):
        return "Pregão Eletrônico"
    if "preg" in lower:
        return "Pregão Eletrônico"
    if "contrato" in lower:
        return "Contrato"
    if "dispensa" in lower:
        return "Dispensa"
    if "inexig" in lower:
        return "Inexigibilidade"
    if "chamada" in lower:
        return "Chamada Pública"
    if "ata" in lower and "registro" in lower:
        return "Ata de Registro de Preços"
    return raw_type.strip()


def extract_instrument_and_uasg(text: str, nup_id: str = "") -> Dict[str, Any]:
    """
    Extrai instrumento (tipo + número) e UASG (código + nome) do texto.
    Normalmente aparecem no primeiro parágrafo/tópico.
    Ordem: INSTRUMENTO_REGEX (tópico 1) → INSTRUMENTO_CAMPO6_REGEX (campo 6) → UASG só.
    """
    instrumento: Dict[str, Optional[str]] = {"tipo": None, "numero": None}
    uasg: Dict[str, Optional[str]] = {"codigo": None, "nome": None}

    flat = _normalize_for_regex(text)
    head = flat[:4000]

    m_inst = INSTRUMENTO_REGEX.search(head)
    if m_inst:
        tipo_raw = m_inst.group(1)
        tipo = _normalize_instrument_type(tipo_raw)
        numero = m_inst.group(2).strip()
        instrumento = {"tipo": tipo, "numero": numero}

        after = head[m_inst.end() : m_inst.end() + 900]

        m_uasg = UASG_AFTER_INSTRUMENTO_REGEX.search(after)
        if not m_uasg:
            m_uasg = CANDIDATE_UASG_FLEX_REGEX.search(after)

        if m_uasg:
            codigo, nome = m_uasg.group(1), m_uasg.group(2)
            uasg = {
                "codigo": codigo.strip(),
                "nome": format_om_name(_normalize_whitespace(nome)),
            }
    else:
        # Fallback: formato telegráfico do campo 6 (abaixo da tabela)
        m_campo6 = INSTRUMENTO_CAMPO6_REGEX.search(head)
        if m_campo6:
            match_text = m_campo6.group(0)
            tipo = _normalize_instrument_type(match_text.split()[0])
            numero = m_campo6.group(1).strip()
            instrumento = {"tipo": tipo, "numero": numero}
            uasg_code = m_campo6.group(2)
            if uasg_code:
                uasg = {
                    "codigo": uasg_code.strip(),
                    "nome": format_om_name(UASG_TO_OM.get(uasg_code.strip(), "")),
                }
            print(
                f"[Stage2][{nup_id}] Instrumento via campo 6: {tipo} {numero}",
                flush=True,
            )
        else:
            # Mesmo sem instrumento, tenta identificar UASG no cabeçalho/tópico 1
            m_uasg = CANDIDATE_UASG_FLEX_REGEX.search(head)
            if m_uasg:
                codigo, nome = m_uasg.group(1), m_uasg.group(2)
                uasg = {
                    "codigo": codigo.strip(),
                    "nome": format_om_name(_normalize_whitespace(nome)),
                }

    inst_tipo = instrumento.get("tipo") or ""
    inst_num = instrumento.get("numero") or ""
    inst_str = f"{inst_tipo} {inst_num}".strip() or "?"
    uasg_cod = uasg.get("codigo") or ""
    uasg_nome = (uasg.get("nome") or "").strip() or "?"
    print(f"[Stage2][{nup_id}] Instrumento: {inst_str} | UASG: {uasg_cod} - {uasg_nome}", flush=True)
    return {"instrumento": instrumento, "uasg": uasg}


def extract_instrument_candidates(
    text: str,
    section: str = "requisicao",
    page_scope: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Gera candidatos de instrumento a partir do texto da requisição.

    Não usa IA. Baseado apenas em padrões determinísticos.
    """
    candidates: List[Dict[str, Any]] = []
    cleaned = _normalize_for_regex(text or "")

    def _base_candidate(tipo_raw: str, numero_raw: str, source: str, match_span: Tuple[int, int]) -> Dict[str, Any]:
        tipo_norm = _normalize_instrument_type(tipo_raw)
        numero_norm = normalize_instrument_year(numero_raw.strip())
        start, end = match_span
        matched_text = cleaned[start:end]
        window_start = max(0, start - 80)
        window_end = min(len(cleaned), end + 80)
        window = cleaned[window_start:window_end]

        cand: Dict[str, Any] = {
            "tipo": tipo_norm,
            "numero": numero_norm,
            "score": 0.0,
            "source": source,
            "page_scope": page_scope,
            "section": section,
            "matched_text": matched_text,
            "normalized_text": f"{tipo_norm} {numero_norm}".strip(),
            "reasons": [],
            "context_window": window,
        }
        return cand

    # 1) Padrão narrativo do tópico 1: "por meio do Pregão Eletrônico nº 90005/2025"
    for m in INSTRUMENTO_REGEX.finditer(cleaned):
        tipo_raw = m.group(1)
        numero_raw = m.group(2)
        cand = _base_candidate(tipo_raw, numero_raw, "topico1_narrativo", m.span())
        cand["reasons"].append("Padrão narrativo do tópico 1 identificado.")
        candidates.append(cand)

    # 2) Padrão telegráfico do campo 6: "CONTRATO N° 28/2026, UASG 160142 (GER)."
    for m in INSTRUMENTO_CAMPO6_REGEX.finditer(cleaned):
        full = m.group(0)
        first_word = full.split()[0] if full.split() else ""
        tipo_raw = first_word
        numero_raw = m.group(1)
        cand = _base_candidate(tipo_raw, numero_raw, "campo6_telegráfico", m.span())
        cand["reasons"].append("Padrão telegráfico do campo 6 identificado.")
        candidates.append(cand)

    # 3) Padrão sigla curta: "PE 90005/2025 ..."
    for m in INSTRUMENTO_PE_SIGLA_REGEX.finditer(cleaned):
        numero_raw = m.group(1)
        cand = _base_candidate("PE", numero_raw, "sigla_pe", m.span())
        cand["reasons"].append("Padrão sigla 'PE <numero>' identificado.")
        candidates.append(cand)

    # 4) Padrão PREGÃO curto: "PREGÃO N° 90003/2025 ..."
    for m in INSTRUMENTO_PREGao_CURTO_REGEX.finditer(cleaned):
        numero_raw = m.group(1)
        cand = _base_candidate("Pregão", numero_raw, "pregao_curto", m.span())
        cand["reasons"].append("Padrão 'PREGÃO <numero>' identificado.")
        candidates.append(cand)

    return candidates


def resolve_instrument(
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Resolve o melhor instrumento a partir da lista de candidatos.

    Retorna:
    {
      "instrument": {"tipo": str | None, "numero": str | None} ou None,
      "confidence": int (0-100),
      "candidates": [...],
      "reason": str,
    }
    """
    if not candidates:
        return {
            "instrument": None,
            "confidence": 0,
            "candidates": [],
            "reason": "Nenhum candidato de instrumento identificado.",
        }

    # Ajustar scores com base em evidências reais.
    for cand in candidates:
        score = 0.0
        reasons = cand.get("reasons", [])
        source = str(cand.get("source") or "")
        section = str(cand.get("section") or "")
        window = cand.get("context_window") or ""
        window_lower = window.lower()

        # Bônus por fonte/section
        if source == "topico1_narrativo":
            score += 50.0
            reasons.append("Instrumento identificado no tópico 1 da requisição.")
        if source == "campo6_telegráfico":
            score += 40.0
            reasons.append("Instrumento identificado no campo 6 (telegráfico).")
        if source == "sigla_pe":
            score += 35.0
        if source == "pregao_curto":
            score += 30.0

        if section == "requisicao":
            score += 10.0

        # Bônus se tipo e número aparecem próximos (já garantido pelos padrões).
        score += 10.0

        # Bônus se mencionar termos que reforçam o contexto de instrumento.
        if any(w in window_lower for w in ["gerenciado", "gerenciador", "ger.", " (ger", "part)"]):
            score += 10.0
            reasons.append("Janela contém marcadores de gerência (GER/Part).")

        # Bônus se houver UASG próxima.
        if re.search(r"\b(?:uasg|ug)\s*[:\-]?\s*16\d{4}\b", window, flags=re.IGNORECASE):
            score += 10.0
            reasons.append("UASG encontrada na mesma janela do instrumento.")

        # Penalidades fortes para contextos de falso positivo.
        false_positive_tokens = [
            "equipe de gestão e fiscalização de contrato",
            "egfc",
            "gestor de contrato",
            "fiscal de contrato",
            "lei federal",
            "14.133",
            "req nº",
            "requisição nº",
            "nup",
            "nc ",
            "ptres",
            "natureza de despesa",
            " nd ",
        ]
        if any(tok in window_lower for tok in false_positive_tokens):
            score -= 80.0
            reasons.append("Contexto sugere falso positivo (EGFC/Lei/Req/NUP/ND/PTRES).")

        cand["score"] = score
        cand["reasons"] = reasons

    # Agregar consenso por (tipo, numero)
    by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for cand in candidates:
        tipo = str(cand.get("tipo") or "")
        numero = str(cand.get("numero") or "")
        if not tipo or not numero:
            continue
        key = (tipo, numero)
        by_key.setdefault(key, []).append(cand)

    for key, group in by_key.items():
        if len(group) >= 2:
            # Consenso entre múltiplas fontes para o mesmo instrumento.
            for cand in group:
                cand["score"] = float(cand.get("score", 0.0)) + 15.0
                reasons = cand.get("reasons", [])
                reasons.append("Consenso entre múltiplos padrões para o mesmo instrumento.")
                cand["reasons"] = reasons

    # Escolher melhor candidato.
    sorted_cands = sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)
    best = sorted_cands[0]
    best_score = float(best.get("score", 0.0))

    # Mapear score para confiança 0-100.
    # Regra simples: clampa o score em [0, 100].
    confidence = int(max(0.0, min(100.0, best_score)))

    if confidence <= 0:
        return {
            "instrument": None,
            "confidence": 0,
            "candidates": sorted_cands,
            "reason": "Candidatos de instrumento encontrados, mas todos com score muito baixo ou contexto duvidoso.",
        }

    reason_parts: List[str] = best.get("reasons", [])
    if not reason_parts:
        reason_parts = ["Melhor score entre candidatos de instrumento."]

    return {
        "instrument": {"tipo": best.get("tipo"), "numero": best.get("numero")},
        "confidence": confidence,
        "source": best.get("source"),
        "matched_text": best.get("matched_text"),
        "normalized_text": best.get("normalized_text"),
        "candidates": sorted_cands,
        "reason": "; ".join(reason_parts),
    }


def extract_uasg_from_text(text: str, nup_id: str = "") -> Dict[str, Optional[str]]:
    """
    Extrai apenas a UASG/UG do texto da requisição.

    Mantém a lógica determinística e separada da resolução de instrumento.
    """
    uasg: Dict[str, Optional[str]] = {"codigo": None, "nome": None}
    flat = _normalize_for_regex(text)
    head = flat[:4000]

    m_uasg = CANDIDATE_UASG_FLEX_REGEX.search(head)
    if m_uasg:
        codigo, nome = m_uasg.group(1), m_uasg.group(2)
        uasg = {
            "codigo": codigo.strip(),
            "nome": format_om_name(_normalize_whitespace(nome)),
        }
    else:
        m_uasg = re.search(
            r"\b(?:UASG|UG)\s*[:\-]?\s*(16\d{4})\b",
            head,
            flags=re.IGNORECASE,
        )
        if m_uasg:
            uasg = {
                "codigo": m_uasg.group(1).strip(),
                "nome": None,
            }

    uasg_cod = uasg.get("codigo") or ""
    uasg_nome = (uasg.get("nome") or "").strip() or "?"
    print(f"[Stage2][{nup_id}] UASG: {uasg_cod} - {uasg_nome}", flush=True)
    return uasg


def extract_uasg_candidates(
    text: str,
    section: str = "requisicao",
    page_scope: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Gera candidatos de UASG/UG gerenciadora a partir do texto da requisição,
    sem usar IA.
    """
    candidates: List[Dict[str, Any]] = []
    full = text or ""
    flat = _normalize_for_regex(full)

    def _base_candidate(
        codigo: str,
        nome_raw: Optional[str],
        source: str,
        match_span: Tuple[int, int],
        extra_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        codigo_norm = (codigo or "").strip()
        nome_norm = format_om_name(_normalize_whitespace(nome_raw)) if nome_raw else None
        start, end = match_span
        matched_text = full[start:end]
        window_start = max(0, start - 120)
        window_end = min(len(full), end + 120)
        window = full[window_start:window_end]

        cand: Dict[str, Any] = {
            "codigo": codigo_norm,
            "nome": nome_norm,
            "score": 0.0,
            "source": source,
            "page_scope": page_scope,
            "section": section,
            "matched_text": matched_text,
            "normalized_text": f"{codigo_norm} - {nome_norm}" if nome_norm else codigo_norm,
            "reasons": [],
            "context_window": window,
        }
        if extra_reason:
            cand["reasons"].append(extra_reason)
        return cand

    # 1) Padrão narrativo flexível com "gerenciado pela UASG/UG/código - nome".
    for m in CANDIDATE_UASG_FLEX_REGEX.finditer(flat):
        codigo, nome = m.group(1), m.group(2)
        # Mapear span no texto original aproximando pelo trecho exato encontrado.
        matched_flat = flat[m.start() : m.end()]
        start_orig = full.find(matched_flat.split()[0])
        if start_orig == -1:
            start_orig = max(0, m.start() - 10)
        end_orig = min(len(full), start_orig + len(matched_flat) + 10)
        cand = _base_candidate(
            codigo,
            nome,
            "narrativo_gerenciado",
            (start_orig, end_orig),
            extra_reason="Padrão narrativo de UASG/UG gerenciadora identificado.",
        )
        candidates.append(cand)

    # 2) Padrão telegráfico de campo 6: "... UASG 160142 (GER)" ou "UASG: 160078-CMCG - (Part)".
    tele_regex = re.compile(
        r"\b(UASG|UG)\s*[:\-]?\s*(16\d{4})\b(?:[^\n\r]{0,60})",
        flags=re.IGNORECASE,
    )
    for m in tele_regex.finditer(full):
        rotulo = m.group(1)
        codigo = m.group(2)
        span_start, span_end = m.span()
        snippet = full[span_start:span_end]
        # Tenta capturar possível nome curto após código (ex.: '- 9º Batalhão de Suprimento').
        nome_match = re.search(
            r"\b16\d{4}\b\s*[–\-\s—]+\s*(.+?)(?:\.|,|\)|$)",
            snippet,
            flags=re.IGNORECASE,
        )
        nome = nome_match.group(1) if nome_match else None
        cand = _base_candidate(
            codigo,
            nome,
            "telegráfico_rotulado",
            (span_start, span_end),
            extra_reason=f"Padrão telegráfico com rótulo {rotulo} identificado.",
        )
        candidates.append(cand)

    # 3) Código + nome sem rótulo explícito, mas com contexto forte de gerência.
    context_regex = re.compile(
        r"(gerenciad[oa]\s+pel[oa]\s+)(16\d{4})\s*[–\-\s—]+\s*(.+?)(?:\.|,|$)",
        flags=re.IGNORECASE,
    )
    for m in context_regex.finditer(full):
        codigo = m.group(2)
        nome = m.group(3)
        cand = _base_candidate(
            codigo,
            nome,
            "codigo_nome_contexto_gerencia",
            m.span(2),
            extra_reason="Código e nome próximos em contexto explícito de gerência.",
        )
        candidates.append(cand)

    # 4) Códigos soltos com rótulo (UASG/UG) sem nome (candidatos fracos).
    simple_label_regex = re.compile(
        r"\b(?:UASG|UG)\s*[:\-]?\s*(16\d{4})\b",
        flags=re.IGNORECASE,
    )
    for m in simple_label_regex.finditer(full):
        codigo = m.group(1)
        cand = _base_candidate(
            codigo,
            None,
            "codigo_rotulado_simples",
            m.span(1),
            extra_reason="Código rotulado como UASG/UG sem nome explícito.",
        )
        candidates.append(cand)

    return candidates


def _uasg_name_matches(nome_banco: str, nome_textual: str) -> bool:
    """
    Compara nomes de UASG tolerando pequenos ruídos/sufixos no texto extraído.
    """
    banco = format_om_name(_normalize_whitespace(nome_banco))
    textual = format_om_name(_normalize_whitespace(nome_textual))
    if not banco or not textual:
        return False
    return banco == textual or textual.startswith(banco)


def resolve_uasg(
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Resolve a melhor UASG/UG gerenciadora a partir da lista de candidatos.

    Retorna:
    {
      "uasg": {"codigo": str | None, "nome": str | None} ou None,
      "confidence": int (0-100),
      "source": str | None,
      "matched_text": str | None,
      "normalized_text": str | None,
      "candidates": [...],
      "reason": str,
    }
    """
    if not candidates:
        return {
            "uasg": None,
            "confidence": 0,
            "candidates": [],
            "reason": "Nenhum candidato de UASG/UG identificado.",
        }

    # Import lazy para evitar ciclos.
    try:
        from ..uasg_store import get_uasg_nome
    except ImportError:
        from uasg_store import get_uasg_nome

    for cand in candidates:
        score = 0.0
        reasons = cand.get("reasons", [])
        source = str(cand.get("source") or "")
        section = str(cand.get("section") or "")
        window = cand.get("context_window") or ""
        window_lower = str(window).lower()
        codigo = str(cand.get("codigo") or "").strip()
        nome_textual = str(cand.get("nome") or "").strip() or None

        # Bônus por padrões mais fortes.
        if source == "narrativo_gerenciado":
            score += 60.0
            reasons.append("UASG/UG encontrada em padrão narrativo de gerência.")
        elif source == "telegráfico_rotulado":
            score += 50.0
            reasons.append("UASG/UG encontrada em padrão telegráfico com rótulo.")
        elif source == "codigo_nome_contexto_gerencia":
            score += 55.0
            reasons.append("Código e nome em contexto forte de gerência.")
        elif source == "codigo_rotulado_simples":
            score += 25.0
            reasons.append("Código rotulado como UASG/UG, sem nome explícito.")

        if section == "requisicao":
            score += 5.0

        # Bônus por marcadores de gerência/participação na janela.
        if any(
            tok in window_lower
            for tok in ["gerenciado", "gerenciadora", "ger.", "participante", "part)"]
        ):
            score += 10.0
            reasons.append("Janela contém marcadores de gerência/participação (GER/Part).")

        # Enriquecimento com banco/cache.
        nome_banco = get_uasg_nome(codigo) or UASG_TO_OM.get(codigo)
        if nome_banco:
            # Temos conhecimento prévio do código.
            score += 15.0
            reasons.append("Código UASG/UG encontrado na base local (9ª RM / banco).")

        if nome_banco and nome_textual:
            if _uasg_name_matches(nome_banco, nome_textual):
                score += 15.0
                reasons.append("Nome textual é coerente com o nome cadastrado no banco.")
            else:
                score -= 25.0
                reasons.append(
                    "Nome textual diverge do nome cadastrado na base de UASGs (mantido para auditoria)."
                )

        # Penalidades para possíveis falsos positivos de código solto.
        # Ex.: números de 6 dígitos em contextos orçamentários, ND, PTRES etc.
        false_context_tokens = [
            "ptres",
            "evento",
            "fonte",
            "esfera",
            "ug emitente",
            "nd ",
            "natureza de despesa",
            "elemento de despesa",
        ]
        if any(tok in window_lower for tok in false_context_tokens):
            score -= 30.0
            reasons.append("Contexto sugere código orçamentário, não UASG/UG gerenciadora.")

        cand["score"] = score
        cand["reasons"] = reasons

    # Agregar consenso por código.
    by_codigo: Dict[str, List[Dict[str, Any]]] = {}
    for cand in candidates:
        codigo = str(cand.get("codigo") or "").strip()
        if not codigo:
            continue
        by_codigo.setdefault(codigo, []).append(cand)

    for codigo, group in by_codigo.items():
        if len(group) >= 2:
            for cand in group:
                cand["score"] = float(cand.get("score", 0.0)) + 10.0
                reasons = cand.get("reasons", [])
                reasons.append("Consenso entre múltiplas ocorrências para o mesmo código de UASG/UG.")
                cand["reasons"] = reasons

    sorted_cands = sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)
    best = sorted_cands[0]
    best_score = float(best.get("score", 0.0))

    # Mapear score para confiança 0-100.
    confidence = int(max(0.0, min(100.0, best_score)))

    if confidence <= 0:
        return {
            "uasg": None,
            "confidence": 0,
            "candidates": sorted_cands,
            "reason": "Candidatos de UASG/UG encontrados, mas todos com score muito baixo ou contexto duvidoso.",
        }

    codigo_best = str(best.get("codigo") or "").strip()
    nome_best = best.get("nome")
    nome_final = nome_best

    # Enriquecimento final de nome com banco se necessário.
    nome_banco_best = get_uasg_nome(codigo_best) or UASG_TO_OM.get(codigo_best)
    if not nome_final and nome_banco_best:
        nome_final = nome_banco_best

    reason_parts: List[str] = best.get("reasons", []) or ["Melhor score entre candidatos de UASG/UG."]

    # Ajuste final de coerência/divergência de nome usando o nome resolvido.
    if nome_banco_best and nome_final:
        if _uasg_name_matches(str(nome_banco_best), str(nome_final)):
            if "Nome textual é coerente com o nome cadastrado no banco." not in reason_parts:
                reason_parts.append("Nome textual é coerente com o nome cadastrado no banco.")
            confidence = int(max(0, min(100, confidence + 5)))
        else:
            if (
                "Nome textual diverge do nome cadastrado na base de UASGs (mantido para auditoria)."
                not in reason_parts
            ):
                reason_parts.append(
                    "Nome textual diverge do nome cadastrado na base de UASGs (mantido para auditoria)."
                )
            # Penalização adicional para garantir queda perceptível na confiança em caso de divergência.
            confidence = int(max(0, confidence - 20))
    return {
        "uasg": {"codigo": codigo_best or None, "nome": nome_final or None},
        "confidence": confidence,
        "source": best.get("source"),
        "matched_text": best.get("matched_text"),
        "normalized_text": best.get("normalized_text"),
        "candidates": sorted_cands,
        "reason": "; ".join(reason_parts),
    }


def _search_uasg_all_pages(all_pages: Dict[str, str]) -> Dict[str, Optional[str]]:
    """
    Busca UASG em todas as páginas do processo.

    Mantém o fallback textual para UASG sem reintroduzir resolução legada de instrumento.
    """
    uasg: Dict[str, Optional[str]] = {"codigo": None, "nome": None}

    page_items: List[Tuple[int, str]] = []
    for key, text in all_pages.items():
        if not key.startswith("pagina_"):
            continue
        try:
            idx = int(key.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        page_items.append((idx, text or ""))

    page_items.sort(key=lambda x: x[0])

    for _, text in page_items:
        found = extract_uasg_from_text(text)
        if found.get("codigo"):
            return found

    return uasg


def _search_instrument_and_uasg_all_pages(all_pages: Dict[str, str]) -> Dict[str, Any]:
    """
    Busca instrumento (tipo + número) e UASG em TODAS as páginas do processo,
    usando regex mais abrangentes.
    """
    instrumento: Dict[str, Optional[str]] = {"tipo": None, "numero": None}
    uasg: Dict[str, Optional[str]] = {"codigo": None, "nome": None}

    patterns: List[Tuple[re.Pattern[str], str]] = [
        (
            re.compile(
                r"(Preg[aã]o\s+Eletr[oô]nico)\s*(?:n[º°o\.]|nr\.?|nº|Nº|N°)?\s*\.?\s*(\d+[/-]\d+)",
                flags=re.IGNORECASE,
            ),
            "Pregão Eletrônico",
        ),
        (
            re.compile(
                r"(Contrato)\s+[Nn][°ºo\.]?\s*\.?\s*(\d+[/-]\d+)",
                flags=re.IGNORECASE,
            ),
            "Contrato",
        ),
        (
            re.compile(
                r"(Dispensa(?:\s+de\s+Licita[çc][aã]o)?)\s+[Nn][°ºo\.]?\s*\.?\s*(\d+[/-]\d+)",
                flags=re.IGNORECASE,
            ),
            "Dispensa",
        ),
        (
            re.compile(
                r"(Inexigibilidade)\s+[Nn][°ºo\.]?\s*\.?\s*(\d+[/-]\d+)",
                flags=re.IGNORECASE,
            ),
            "Inexigibilidade",
        ),
        (
            re.compile(
                r"(Ata\s+de\s+Registro\s+de\s+Pre[çc]os?)\s*[Nn][°ºo\.]?\s*\.?\s*(\d+[/-]\d+)",
                flags=re.IGNORECASE,
            ),
            "Ata de Registro de Preços",
        ),
    ]

    page_items: List[Tuple[int, str]] = []
    for key, text in all_pages.items():
        if not key.startswith("pagina_"):
            continue
        try:
            idx = int(key.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        page_items.append((idx, text or ""))

    page_items.sort(key=lambda x: x[0])

    instrumento_page: Optional[int] = None

    for idx, text in page_items:
        flat = _normalize_for_regex(text)
        for regex, tipo_label in patterns:
            m = regex.search(flat)
            if m:
                numero = m.group(2).strip()
                instrumento = {"tipo": tipo_label, "numero": numero}
                instrumento_page = idx
                break
        if instrumento_page is not None:
            break

    # Busca UASG preferencialmente na mesma página do instrumento; senão, em qualquer página.
    uasg_patterns = [
        re.compile(r"UASG\s*[:\-]?\s*(\d{6})", flags=re.IGNORECASE),
        re.compile(r"UG\s*[:/\-]\s*(\d{6})", flags=re.IGNORECASE),
    ]

    def _find_uasg_in_text(text: str) -> Optional[str]:
        for rgx in uasg_patterns:
            m = rgx.search(text)
            if m:
                return m.group(1).strip()
        return None

    if instrumento_page is not None:
        text = next((t for (i, t) in page_items if i == instrumento_page), "")
        codigo = _find_uasg_in_text(text or "")
        if codigo:
            uasg["codigo"] = codigo

    if not uasg["codigo"]:
        for _, text in page_items:
            codigo = _find_uasg_in_text(text or "")
            if codigo:
                uasg["codigo"] = codigo
                break

    return {"instrumento": instrumento, "uasg": uasg}


def _fallback_instrument_and_uasg_with_ai(
    all_pages: Dict[str, str],
) -> Dict[str, Any]:
    """
    Fallback curto via Gemini usando apenas as 3 primeiras páginas do processo
    para identificar instrumento e UASG.
    """
    page_items: List[Tuple[int, str]] = []
    for key, text in all_pages.items():
        if not key.startswith("pagina_"):
            continue
        try:
            idx = int(key.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        page_items.append((idx, text or ""))
    page_items.sort(key=lambda x: x[0])

    first_texts = [t for _, t in page_items[:3] if t]
    if not first_texts:
        return {}

    combined = "\n\n".join(first_texts)

    try:
        proc = GeminiProcessor()
    except ValueError as exc:
        logger.warning(
            "Gemini indisponível para fallback de instrumento/UASG no estágio 2: %s",
            exc,
        )
        return {}

    prompt = STAGE2_INSTR_UASG_FALLBACK_PROMPT + "\n\nTEXTO:\n" + combined

    try:
        result, _, _ = proc._generate(prompt, "stage2_instr_uasg")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Falha no fallback de instrumento/UASG com IA (estágio 2): %s", exc
        )
        return {}

    if not isinstance(result, dict):
        return {}

    instrumento_tipo = result.get("instrumento_tipo")
    instrumento_numero = result.get("instrumento_numero")
    uasg_codigo = result.get("uasg")

    instrumento: Dict[str, Optional[str]] = {
        "tipo": instrumento_tipo or None,
        "numero": instrumento_numero or None,
    }
    uasg: Dict[str, Optional[str]] = {
        "codigo": uasg_codigo or None,
        "nome": None,
    }

    return {"instrumento": instrumento, "uasg": uasg}


def extract_empenho_type(text: str) -> Optional[str]:
    """
    Extrai o tipo de empenho (Ordinário, Estimativo, Global) do cabeçalho
    ou do tópico específico sobre tipo de empenho.
    """
    upper = text.upper()

    header_match = re.search(
        r"Tipo de empenho\s*:\s*(Ordin[aá]rio|Estimativo|Global)",
        text,
        flags=re.IGNORECASE,
    )
    if header_match:
        value = header_match.group(1).lower()
        if "ordin" in value:
            return "Ordinário"
        if "estim" in value:
            return "Estimativo"
        if "global" in value:
            return "Global"

    segmento = ""
    for m in re.finditer(r"(^\s*\d+\..+?$)", text, flags=re.MULTILINE):
        linha = m.group(1)
        if "empenho" in linha.lower():
            start = m.start()
            segmento = text[start : start + 500]
            break

    if not segmento:
        segmento = text

    if "ORDIN" in upper:
        return "Ordinário"
    if "ESTIMAT" in upper:
        return "Estimativo"
    if "GLOBAL" in upper:
        return "Global"

    return None


def _normalize_tipo_empenho_value(raw: str) -> Optional[str]:
    """
    Normaliza variantes textuais/ocr de tipo de empenho para valores canônicos.
    """
    s = (raw or "").strip().lower()
    # Normalização simples sem depender de bibliotecas externas de acentuação.
    s = (
        s.replace("á", "a")
        .replace("â", "a")
        .replace("ã", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
    )
    if "ordin" in s:
        return "Ordinário"
    if "estimativ" in s or "estimativ" in s:
        return "Estimativo"
    if "global" in s:
        return "Global"
    return None


def extract_tipo_empenho_candidates(
    text: str,
    section: str = "requisicao",
    page_scope: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Gera candidatos de tipo de empenho (Ordinário, Estimativo, Global) a partir
    do texto da requisição, sem usar IA.
    """
    candidates: List[Dict[str, Any]] = []
    full_text = text or ""
    lowered = full_text.lower()

    def _base_candidate(
        value_raw: str,
        source: str,
        match_span: Tuple[int, int],
        extra_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        value_norm = _normalize_tipo_empenho_value(value_raw)
        if not value_norm:
            return {}
        start, end = match_span
        matched_text = full_text[start:end]
        window_start = max(0, start - 120)
        window_end = min(len(full_text), end + 120)
        window = full_text[window_start:window_end]

        cand: Dict[str, Any] = {
            "value": value_norm,
            "score": 0.0,
            "source": source,
            "page_scope": page_scope,
            "section": section,
            "matched_text": matched_text,
            "normalized_text": value_norm,
            "reasons": [],
            "context_window": window,
        }
        if extra_reason:
            cand["reasons"].append(extra_reason)
        return cand

    # 1) Cabeçalho explícito: "Tipo de empenho: Ordinário"
    header_regex = re.compile(
        r"Tipo\s+de\s+Empenho\s*[:\-–—]?\s*(Ordin[aá]rio|Ordinario|ESTIMATIVO|Estimativo|GLOBAL|Global)",
        flags=re.IGNORECASE,
    )
    for m in header_regex.finditer(full_text):
        value_raw = m.group(1)
        # Usa o grupo capturado (valor) para o span principal.
        span = m.span(1)
        cand = _base_candidate(
            value_raw,
            "header_label",
            span,
            extra_reason="Linha de cabeçalho com rótulo 'Tipo de Empenho'.",
        )
        if cand:
            # Heurística: linha curta e objetiva recebe anotação especial.
            line_start = full_text.rfind("\n", 0, m.start())
            line_end = full_text.find("\n", m.end())
            if line_start == -1:
                line_start = 0
            if line_end == -1:
                line_end = len(full_text)
            line = full_text[line_start:line_end].strip()
            cand["line_length"] = len(line)
            candidates.append(cand)

    # 2) Tópico específico: "4. Tipo de Empenho" seguido de explicação.
    lines = full_text.splitlines()
    offset = 0
    for idx, line in enumerate(lines):
        line_lower = line.lower()
        line_start = offset
        line_end = offset + len(line)
        offset += len(line) + 1  # +1 para o '\n'

        if "tipo de empenho" not in line_lower:
            continue

        # Janela: linha do tópico + próximas 3 linhas.
        window_lines = [line]
        for j in range(1, 4):
            if idx + j < len(lines):
                window_lines.append(lines[idx + j])
        topic_window = "\n".join(window_lines)
        topic_window_lower = topic_window.lower()

        for raw_token, canonical in [
            ("ordinario", "Ordinário"),
            ("ordinário", "Ordinário"),
            ("estimativo", "Estimativo"),
            ("global", "Global"),
        ]:
            if raw_token in topic_window_lower:
                pos = topic_window_lower.find(raw_token)
                # Converte posição relativa na janela para posição no texto completo.
                abs_start = full_text.find(window_lines[0])
                if abs_start == -1:
                    abs_start = line_start
                span_start = abs_start + pos
                span_end = span_start + len(raw_token)
                cand = _base_candidate(
                    raw_token,
                    "topic_tipo_empenho",
                    (span_start, span_end),
                    extra_reason="Valor identificado em tópico específico sobre tipo de empenho.",
                )
                if cand:
                    candidates.append(cand)

    # 3) Frases com "empenho" próximo do valor (sem cabeçalho explícito).
    body_regex = re.compile(
        r"empenho.{0,80}?\b(ordin[aá]rio|ordinario|estimativo|global)\b",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for m in body_regex.finditer(full_text):
        value_raw = m.group(1)
        cand = _base_candidate(
            value_raw,
            "body_empenho_phrase",
            m.span(1),
            extra_reason="Valor identificado em frase que menciona 'empenho'.",
        )
        if cand:
            candidates.append(cand)

    # 4) Ocorrências isoladas de termos canônicos (muito mais frágeis).
    # Usado apenas como último recurso, com forte penalidade depois.
    for raw_token, canonical in [
        ("ordinario", "Ordinário"),
        ("ordinário", "Ordinário"),
        ("estimativo", "Estimativo"),
        ("global", "Global"),
    ]:
        start = 0
        while True:
            pos = lowered.find(raw_token, start)
            if pos == -1:
                break
            span = (pos, pos + len(raw_token))
            cand = _base_candidate(
                raw_token,
                "isolated_token",
                span,
                extra_reason="Ocorrência isolada de termo de tipo de empenho.",
            )
            if cand:
                candidates.append(cand)
            start = pos + len(raw_token)

    return candidates


def resolve_tipo_empenho(
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Resolve o melhor tipo de empenho a partir da lista de candidatos.

    Retorna:
    {
      "value": "Ordinário" | "Estimativo" | "Global" | None,
      "confidence": int 0-100,
      "source": str | None,
      "matched_text": str | None,
      "normalized_text": str | None,
      "candidates": [...],
      "reason": str,
      "ambiguous": bool,
    }
    """
    if not candidates:
        return {
            "value": None,
            "confidence": 0,
            "candidates": [],
            "reason": "Nenhum candidato de tipo de empenho identificado.",
            "ambiguous": False,
        }

    # Ajuste de scores com base em evidências reais.
    for cand in candidates:
        score = 0.0
        reasons = cand.get("reasons", [])
        source = str(cand.get("source") or "")
        section = str(cand.get("section") or "")
        window = cand.get("context_window") or ""
        window_lower = str(window).lower()
        value = str(cand.get("value") or "")

        # Bônus principais conforme a origem.
        if source == "header_label":
            score += 70.0
            reasons.append("Cabeçalho explícito com rótulo 'Tipo de Empenho'.")
            # Bônus adicional se a linha parecer curta/objetiva.
            line_len = cand.get("line_length")
            if isinstance(line_len, int) and line_len and line_len <= 80:
                score += 10.0
                reasons.append("Linha de cabeçalho curta e objetiva.")
        elif source == "topic_tipo_empenho":
            score += 60.0
            reasons.append("Valor extraído de tópico específico sobre tipo de empenho.")
        elif source == "body_empenho_phrase":
            score += 40.0
            reasons.append("Frase que menciona 'empenho' próxima ao valor.")
        elif source == "isolated_token":
            score += 10.0
            reasons.append("Ocorrência isolada de termo de tipo de empenho (fraca).")

        if section == "requisicao":
            score += 5.0

        # Bônus se o rótulo "Tipo de empenho" aparece na janela do contexto.
        if "tipo de empenho" in window_lower:
            score += 15.0
            reasons.append("Janela de contexto contém o rótulo 'Tipo de empenho'.")

        # Penalidades para ocorrências potencialmente fora de contexto.
        if value == "Global":
            # Palavra "global" é muito genérica; exige forte vínculo com empenho.
            if "empenho" not in window_lower and "tipo de empenho" not in window_lower:
                score -= 40.0
                reasons.append(
                    "Menção a 'global' sem estar claramente ligada a 'empenho' no contexto."
                )

        # Penalidade leve se termos sugerirem uso genérico (estimativas, contexto global).
        false_context_tokens = [
            "escala global",
            "impacto global",
            "visão global",
            "estimativa",
            "estimado",
            "estimando",
        ]
        if any(tok in window_lower for tok in false_context_tokens):
            score -= 20.0
            reasons.append("Contexto indica uso genérico (estimativa/global) fora de empenho.")

        cand["score"] = score
        cand["reasons"] = reasons

    # Agregar consenso por valor canônico.
    by_value: Dict[str, List[Dict[str, Any]]] = {}
    for cand in candidates:
        value = str(cand.get("value") or "")
        if not value:
            continue
        by_value.setdefault(value, []).append(cand)

    for value, group in by_value.items():
        if len(group) >= 2:
            for cand in group:
                cand["score"] = float(cand.get("score", 0.0)) + 10.0
                reasons = cand.get("reasons", [])
                reasons.append("Consenso entre múltiplas ocorrências para o mesmo tipo de empenho.")
                cand["reasons"] = reasons

    sorted_cands = sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)
    best = sorted_cands[0]
    best_score = float(best.get("score", 0.0))

    # Detectar conflito: outro valor canônico com score competitivo.
    ambiguous = False
    conflict_reason: Optional[str] = None
    if len(sorted_cands) > 1:
        best_value = best.get("value")
        for other in sorted_cands[1:]:
            if other.get("value") != best_value:
                if float(other.get("score", 0.0)) >= best_score - 15.0:
                    ambiguous = True
                    conflict_reason = (
                        "Conflito entre candidatos de tipo de empenho com scores próximos."
                    )
                break

    # Mapear score para confiança 0-100, com penalização por ambiguidade.
    confidence = int(max(0.0, min(100.0, best_score)))
    if ambiguous:
        confidence = max(0, confidence - 30)

    if confidence <= 0:
        return {
            "value": None,
            "confidence": 0,
            "candidates": sorted_cands,
            "reason": "Candidatos de tipo de empenho encontrados, mas todos com score muito baixo ou contexto duvidoso.",
            "ambiguous": True,
        }

    reason_parts: List[str] = best.get("reasons", []) or []
    if conflict_reason:
        reason_parts.append(conflict_reason)
    if not reason_parts:
        reason_parts = ["Melhor score entre candidatos de tipo de empenho."]

    return {
        "value": best.get("value"),
        "confidence": confidence,
        "source": best.get("source"),
        "matched_text": best.get("matched_text"),
        "normalized_text": best.get("normalized_text"),
        "candidates": sorted_cands,
        "reason": "; ".join(reason_parts),
        "ambiguous": ambiguous,
    }


def _normalize_catmat(value: Any) -> Optional[str]:
    """
    Limpa o campo CatMat/CatServ para conter apenas números.
    """
    if value is None:
        return None
    s = str(value)
    m = re.search(r"\d+", s)
    if not m:
        return None
    return m.group(0)


def _normalize_unidade(value: Any) -> Optional[str]:
    """
    Unidade (UND) é texto livre. Preserva letras e símbolos.
    Ajusta casos comuns onde OCR/IA retorna 'S' em vez de 'Sv'.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    low = s.lower()
    if low in {"s", "sv", "s.v", "s/v"}:
        return "Sv"
    # Normaliza unidades curtas (ex.: un -> Un, kg -> Kg)
    if len(s) <= 3 and s.isalpha():
        return s[0].upper() + s[1:].lower()
    return s


def normalize_nd(raw: str) -> str:
    """
    LEGADO: mantém assinatura antiga, mas delega para parse_nd_si e retorna
    apenas o canônico "EE.SS" (ou o valor original se inválido).
    """
    parsed = parse_nd_si(raw)
    return parsed["canonical"] or raw.strip()


def parse_nd_si(raw: str) -> Dict[str, Optional[str]]:
    """
    Faz o parse/normalização de ND/SI em um formato canônico.

    Aceita formatos:
    - 33.90.30/07, 33.90.30.07, 339030/07
    - 30/07, 30.07
    - 33.90.30, 339030

    Retorna dict com:
    - element: '30', '39', '52' (ou outra coisa, se não bater tabela)
    - subelement: '07' ou None
    - display: forma amigável para UI (ex.: '30/07' ou '30')
    - canonical: forma canônica interna (ex.: '30.07' ou '30')
    - valid_element: bool indicando se o elemento existe na tabela ND_ELEMENTS
    - valid_pair: bool indicando se (element, subelement) existe na tabela ND_ELEMENTS
    - valid: bool legado (igual a valid_element ou valid_pair)
    - is_partial: True quando a leitura é parcial/genérica (ex.: apenas elemento)
    - parse_type: rótulo descritivo do formato reconhecido
    """
    from typing import cast

    result: Dict[str, Optional[str] | bool | str] = {
        "element": None,
        "subelement": None,
        "display": None,
        "canonical": None,
        "valid": False,
        "valid_element": False,
        "valid_pair": False,
        "is_partial": False,
        "parse_type": "invalid",
    }

    if not raw:
        return cast(Dict[str, Optional[str]], result)

    s = re.sub(r"\s+", "", str(raw))
    s = s.replace(",", ".")

    element: Optional[str] = None
    sub: Optional[str] = None

    # 0) Prefixos específicos do tipo 33.90 ou 44.90 -> partial_prefix
    # (não promovemos a ND final). Evita capturar formatos completos como 30.07.
    if re.fullmatch(r"(33|44)\.90", s):
        result["display"] = raw.strip()
        result["canonical"] = None
        result["valid"] = False
        result["valid_element"] = False
        result["valid_pair"] = False
        result["is_partial"] = True
        result["parse_type"] = "partial_prefix"
        return cast(Dict[str, Optional[str]], result)

    # 1) Formatos simples EE.SS ou EE/SS (ND/SI completa sem prefixo)
    m = re.match(r"^(\d{2})[./](\d{2})$", s)
    if m:
        element, sub = m.group(1), m.group(2)
        result["parse_type"] = "full_with_si"
    else:
        # 2) Formatos com prefixo completo: 33.90.30/07 ou 33.90.30.07 (abreviados)
        m = re.match(r"^\d{2}\.\d{2}\.(\d{2})[./](\d{2})$", s)
        if m:
            element, sub = m.group(1), m.group(2)
            result["parse_type"] = "abbreviated_with_si"
        else:
            m = re.match(r"^\d{2}\.\d{2}\.(\d{2})\.(\d{2})$", s)
            if m:
                element, sub = m.group(1), m.group(2)
                result["parse_type"] = "abbreviated_with_si"
            else:
                # 3) Formato 339030/07 => sufixo 6 dígitos + opcional "/SS" (abreviado)
                m = re.match(r"^(\d{6})/(\d{2})$", s)
                if m:
                    block = m.group(1)
                    if len(block) == 6:
                        element = block[-2:]
                        sub = m.group(2)
                        result["parse_type"] = "abbreviated_with_si"
                else:
                    # 4) Formato 339030 (6 dígitos) => elemento 30 sem SI (abreviado, sem SI)
                    m = re.match(r"^(\d{6})$", s)
                    if m:
                        block = m.group(1)
                        element = block[-2:]
                        sub = None
                        result["parse_type"] = "abbreviated_element_only"
                    else:
                        # 5) Formato 33.90.30 (usa só o último bloco como elemento, sem SI)
                        m = re.match(r"^\d{2}\.\d{2}\.(\d{2})$", s)
                        if m:
                            element = m.group(1)
                            sub = None
                            result["parse_type"] = "abbreviated_element_only"

    # Preencher retorno básico
    if element:
        element = element.zfill(2)
    if sub is not None:
        sub = sub.zfill(2)

    result["element"] = element
    result["subelement"] = sub

    # Montar display e canônico
    if element and sub:
        result["display"] = f"{element}/{sub}"
        result["canonical"] = f"{element}.{sub}"
    elif element:
        result["display"] = element
        result["canonical"] = element
    else:
        # Não conseguimos nem elemento, manter valor bruto
        result["display"] = raw.strip()
        result["canonical"] = None
        return cast(Dict[str, Optional[str]], result)

    # Validação contra a tabela oficial (ND_ELEMENTS)
    try:
        try:
            from ..nd_database import ND_ELEMENTS  # type: ignore[import]
        except ImportError:
            from nd_database import ND_ELEMENTS  # type: ignore[import]
    except Exception:
        # Se por algum motivo não conseguir importar a tabela, considera válido
        result["valid"] = True
        return cast(Dict[str, Optional[str]], result)

    nd_table = ND_ELEMENTS
    if element not in nd_table:
        # Elemento não existe na tabela oficial
        result["valid"] = False
        result["valid_element"] = False
        result["valid_pair"] = False
        result["is_partial"] = bool(element and not sub)
        return cast(Dict[str, Optional[str]], result)

    # Se chegou aqui, o elemento existe na base oficial.
    valid_element = True
    valid_pair = False

    if sub:
        # Nosso nd_database usa chave "subelementos"
        sub_map = nd_table[element].get("subelementos", {})
        if isinstance(sub_map, dict) and sub in sub_map:
            valid_pair = True

    result["valid_element"] = valid_element
    result["valid_pair"] = valid_pair
    # Legado: consideramos válido se ao menos o elemento existe.
    result["valid"] = bool(valid_element or valid_pair)
    # Parcial quando temos apenas elemento ou quando viemos de formatos abreviados.
    result["is_partial"] = bool(element and not sub)

    return cast(Dict[str, Optional[str]], result)


def resolve_nd_candidate(
    raw_nd: str,
    descricao_item: str,
    nd_processo: Optional[str] = None,
    candidatos_extras: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Resolve ND/SI candidata considerando:
    - tabela oficial ND_ELEMENTS
    - ND do processo (quando informada)
    - compatibilidade semântica com a descrição do item
    - penalizações para formatos parciais/incompletos.

    Retorna:
    {
      "chosen": {raw, element, subelement, display, canonical, valid, score},
      "candidates": [...],
      "ambiguous": bool,
      "reason": str,
    }
    """
    from typing import cast

    descricao = (descricao_item or "").lower()
    raw_nd = (raw_nd or "").strip()

    candidates: List[Dict[str, Any]] = []
    seen_raw: set[str] = set()

    def _add_candidate(source_raw: str, reason_hint: str) -> None:
        nonlocal candidates, seen_raw
        if not source_raw:
            return
        key = source_raw.strip()
        if key in seen_raw:
            return
        seen_raw.add(key)
        parsed = parse_nd_si(source_raw)
        candidates.append(
            {
                "raw": source_raw,
                "element": parsed.get("element"),
                "subelement": parsed.get("subelement"),
                "display": parsed.get("display"),
                "canonical": parsed.get("canonical"),
                "valid": parsed.get("valid"),
                "valid_element": parsed.get("valid_element"),
                "valid_pair": parsed.get("valid_pair"),
                "is_partial": parsed.get("is_partial"),
                "parse_type": parsed.get("parse_type"),
                "base_from": reason_hint,
                "score": 0.0,
            }
        )

    # 1) Candidato direto do bruto
    if raw_nd:
        _add_candidate(raw_nd, "raw")

        # Se for algo como 33.90.30/07 etc., gerar variação "EE/SS"
        direct = parse_nd_si(raw_nd)
        elem = direct.get("element")
        sub = direct.get("subelement")
        if elem and sub:
            _add_candidate(f"{elem}/{sub}", "simplificado_elemento_subelemento")
        elif elem:
            _add_candidate(elem, "simplificado_elemento")

    # 2) Candidatos extras fornecidos pelo chamador (se houver)
    if candidatos_extras:
        for extra in candidatos_extras:
            _add_candidate(extra, "extra")

    if not candidates:
        return {
            "chosen": None,
            "candidates": [],
            "ambiguous": False,
            "reason": "Nenhum candidato de ND/SI pôde ser gerado a partir do valor bruto.",
        }

    # ND do processo (se houver), extraindo apenas o elemento
    nd_proc_element: Optional[str] = None
    if nd_processo:
        parsed_proc = parse_nd_si(nd_processo)
        nd_proc_element = parsed_proc.get("element")

    # Heurística simples de compatibilidade semântica por tipo
    def _semantic_score_for_element(element: Optional[str]) -> float:
        if not element:
            return 0.0
        e = element
        score = 0.0
        if e == "30":
            # Material de consumo
            if any(w in descricao for w in ["material", "aquisi", "compra", "fornec", "gênero", "alimenta", "produto"]):
                score += 15.0
        elif e == "39":
            # Serviços
            if any(w in descricao for w in ["servi", "manuten", "locaç", "locac", "limpeza", "conserva", "contrata"]):
                score += 15.0
        elif e == "52":
            # Permanente / equipamento
            if any(w in descricao for w in ["equip", "permanente", "máquina", "veículo", "mobili", "aparelho"]):
                score += 15.0
        return score

    # 3) Atribuir score para cada candidato
    for cand in candidates:
        score = 0.0
        element = cand.get("element")
        sub = cand.get("subelement")
        valid = bool(cand.get("valid"))
        valid_pair = bool(cand.get("valid_pair"))
        is_partial = bool(cand.get("is_partial"))
        parse_type = str(cand.get("parse_type") or "")

        # + peso por existir na tabela oficial
        if valid:
            score += 50.0
        # + bônus extra quando há par elemento/subelemento válido
        if valid_pair:
            score += 15.0

        # + peso se o elemento bater com a ND do processo
        if element and nd_proc_element and element == nd_proc_element:
            score += 20.0

        # + peso se existir subelemento
        if element and sub:
            score += 10.0

        # + peso semântico pela descrição
        score += _semantic_score_for_element(element)

        raw_value = cand.get("raw") or ""
        raw_str = str(raw_value)

        # Penalidades
        # - se parecer ND parcial/incompleta (ex.: "33.90", apenas elemento etc.)
        if re.fullmatch(r"\d{2}\.\d{2}", raw_str) or is_partial:
            score -= 25.0

        # - se perdeu subelemento apesar do bruto parecer ter mais informação
        if ("/" in raw_nd or "." in raw_nd) and (sub is None):
            score -= 10.0

        # - penalidade para candidatos não válidos na tabela
        if not valid:
            score -= 20.0

        cand["score"] = score

    # 4) Deduplicar candidatos por (canonical, element, subelement)
    dedup_map: Dict[Tuple[Optional[str], Optional[str], Optional[str]], Dict[str, Any]] = {}
    for cand in candidates:
        key = (
            cand.get("canonical"),
            cand.get("element"),
            cand.get("subelement"),
        )
        existing = dedup_map.get(key)
        if existing is None:
            # Inicializa com lista de formas de origem
            cand["source_forms"] = [cand.get("raw")]
            dedup_map[key] = cand
        else:
            # Agregar forms brutas
            forms = existing.get("source_forms") or []
            forms.append(cand.get("raw"))
            existing["source_forms"] = forms
            # Manter o de maior score
            if float(cand.get("score", 0.0)) > float(existing.get("score", 0.0)):
                cand["source_forms"] = existing["source_forms"]
                dedup_map[key] = cand

    candidates_dedup = list(dedup_map.values())

    # 5) Escolher melhor candidato entre representações distintas
    candidates_sorted = sorted(
        candidates_dedup, key=lambda c: c.get("score", 0.0), reverse=True
    )
    best = candidates_sorted[0]
    best_score = best.get("score", 0.0)

    # Considerar ambíguo se houver outro candidato muito próximo
    ambiguous = False
    if len(candidates_sorted) > 1:
        second_best = candidates_sorted[1]
        if abs(float(best_score) - float(second_best.get("score", 0.0))) < 5.0:
            ambiguous = True

    # Se não houver NENHUM par elemento/subelemento válido, não promovemos ND
    # parcial/genérica a valor final confiável. Mantemos apenas como candidatos.
    has_full_pair = any(c.get("valid_pair") for c in candidates_sorted)
    if not has_full_pair:
        reason_partial = (
            "Somente ND/SI parcial ou genérica (sem par elemento/subelemento válido) "
            "foi encontrada; mantida apenas como candidata, sem valor final confiável."
        )
        return {
            "chosen": None,
            "candidates": candidates_sorted,
            "ambiguous": True,
            "reason": reason_partial,
        }

    # Quando existir pelo menos um candidato com par elemento/subelemento válido,
    # escolhemos o melhor APENAS dentre esses pares completos.
    full_pairs = [c for c in candidates_sorted if c.get("valid_pair")]
    full_pairs_sorted = sorted(
        full_pairs, key=lambda c: c.get("score", 0.0), reverse=True
    )
    best = full_pairs_sorted[0]
    best_score = best.get("score", 0.0)

    # Se, após isso, ainda assim o melhor não for válido ou tiver score muito baixo,
    # rejeita e mantém somente como informação/candidatos.
    if not best.get("valid") or best_score <= 0:
        reason = (
            "Nenhum candidato de ND/SI obteve score suficiente ou é válido na tabela oficial."
        )
        return {
            "chosen": None,
            "candidates": candidates_sorted,
            "ambiguous": True,
            "reason": reason,
        }

    # Construir razão explicável
    parts: List[str] = []
    if best.get("valid"):
        parts.append("par (elemento/subelemento) existe na tabela ND oficial")
    if nd_proc_element and best.get("element") == nd_proc_element:
        parts.append("elemento consistente com ND do processo")
    sem_score = _semantic_score_for_element(best.get("element"))
    if sem_score > 0:
        parts.append("compatível semanticamente com a descrição do item")
    if re.fullmatch(r"\d{2}\.\d{2}", str(best.get("raw") or "")):
        parts.append("ajustada forma parcial para formato canônico")

    reason = "; ".join(parts) if parts else "melhor score entre candidatos gerados"

    return {
        "chosen": best,
        "candidates": candidates_sorted,
        "ambiguous": ambiguous,
        "reason": reason,
    }


def _parse_table_result(
    result: Dict[str, Any],
) -> Tuple[List[Stage2Item], Optional[str], Optional[str], Optional[Decimal]]:
    """
    Parseia o dict retornado pelo Gemini (tabela de itens) em lista de
    Stage2Item, fornecedor, cnpj e valor_total_geral. Reutilizado no fluxo
    normal e no fallback Vision.
    """
    fornecedor = result.get("fornecedor")
    cnpj = _normalize_cnpj(result.get("cnpj"))
    itens_raw = result.get("itens") or []

    # ND do processo (melhor fonte disponível no estágio 2):
    # agregamos o elemento predominante entre os itens com ND válida.
    nd_proc_elements: Dict[str, int] = {}
    for raw in itens_raw:
        if not isinstance(raw, dict):
            continue
        nd_raw_global = str(raw.get("nd_si") or raw.get("nd") or "").strip()
        if not nd_raw_global:
            continue
        parsed_global = parse_nd_si(nd_raw_global)
        if parsed_global.get("valid_element"):
            elem = parsed_global.get("element")
            if elem:
                nd_proc_elements[elem] = nd_proc_elements.get(elem, 0) + 1

    nd_processo: Optional[str] = None
    if nd_proc_elements:
        # Escolhe o elemento mais frequente como ND geral do processo (apenas elemento).
        nd_processo = max(nd_proc_elements.items(), key=lambda kv: kv[1])[0]

    items: List[Stage2Item] = []
    for raw in itens_raw:
        if not isinstance(raw, dict):
            continue
        try:
            item_num = raw.get("item")
            try:
                item_int = int(item_num) if item_num is not None else None
            except (TypeError, ValueError):
                item_int = None
            q = _safe_decimal(raw.get("quantidade"))
            vu = _safe_decimal(raw.get("valor_unitario"))
            vt = _safe_decimal(raw.get("valor_total"))
            desc_full = _normalize_whitespace(str(raw.get("descricao") or "")) or None
            desc_short = (
                (desc_full or "")[:80] + ("..." if desc_full and len(desc_full) > 80 else "")
                if desc_full
                else None
            )
            nd_raw = str(raw.get("nd_si") or raw.get("nd") or "").strip()
            desc_for_nd = desc_full or desc_short or ""
            nd_resolution = (
                resolve_nd_candidate(
                    nd_raw,
                    desc_for_nd,
                    nd_processo=nd_processo,
                )
                if nd_raw
                else {
                    "chosen": None,
                    "candidates": [],
                    "ambiguous": False,
                    "reason": "ND/SI vazia.",
                }
            )
            chosen_nd = nd_resolution.get("chosen")
            # Só promovemos a ND canônica final quando houver par elemento/subelemento válido.
            nd_norm = (
                chosen_nd.get("canonical")
                if chosen_nd and chosen_nd.get("valid_pair")
                else None
            )
            nd_display = (
                chosen_nd.get("display")
                if chosen_nd
                else (nd_raw or None)
            )
            item = Stage2Item(
                item=item_int,
                catmat=_normalize_catmat(raw.get("catmat") or raw.get("codigo")),
                descricao_completa=desc_full,
                descricao_resumida=desc_short,
                unidade=_normalize_unidade(raw.get("unidade") or raw.get("und")),
                quantidade=float(q) if q is not None else None,
                nd_si=nd_norm,
                nd_si_display=nd_display,
                nd_si_original=nd_raw or None,
                nd_si_raw=nd_raw or None,
                nd_si_candidates=nd_resolution.get("candidates") or [],
                nd_si_resolution_reason=nd_resolution.get("reason"),
                nd_si_ambigua=bool(nd_resolution.get("ambiguous")),
                valor_unitario=float(vu) if vu is not None else None,
                valor_total=float(vt) if vt is not None else None,
            )
            items.append(item)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Falha ao normalizar item da tabela no estágio 2: %s", exc)
            continue
    valor_total_geral = _safe_decimal(result.get("valor_total_geral"))
    return items, fornecedor, cnpj, valor_total_geral


def extract_items_table(
    pages_text: List[str],
    pdf_path: str | Path | None = None,
    req_pages: List[int] | None = None,
    image_pages: List[int] | None = None,
    nup_id: str = "",
) -> Tuple[List[Stage2Item], bool, Optional[float], Optional[str], Optional[str]]:
    """
    Extrai a tabela de itens da requisição.

    Implementação inicial:
    - Usa Gemini com prompt especializado para interpretar o TEXTO das páginas.
    - Se alguma página de req_pages estiver em image_pages e pdf_path existir,
      envia as imagens ao Gemini Vision (_generate_with_images).
    - Caso não haja texto nem imagens, retorna lista vazia.
    """
    combined = "\n\n".join(pages_text or []).strip()
    req_pages = req_pages or []
    image_pages = image_pages or []
    images_b64: List[str] = []
    if pdf_path and req_pages:
        for page_num in req_pages:
            if page_num in image_pages:
                try:
                    b64 = page_to_base64(pdf_path, page_num)
                    if b64:
                        images_b64.append(b64)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Falha ao converter página %s para base64: %s", page_num, exc)

    if not combined and not (pdf_path and req_pages):
        return [], False, None, None, None

    try:
        proc = GeminiProcessor()
    except ValueError as exc:
        logger.warning("Gemini indisponível para extração de tabela no estágio 2: %s", exc)
        return [], False, None, None, None

    # 1. Extração base por texto (sem imagens; fallbacks vêm depois)
    prompt_base = STAGE2_TABLE_PROMPT + "\n\nTEXTO DA TABELA:\n" + (
        combined or "(sem texto extraído; será usado fallback Azure ou Vision se disponível)"
    )
    try:
        result, _, _ = proc._generate(prompt_base, "stage2_table")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao extrair tabela de itens com IA no estágio 2: %s", exc)
        return [], False, None, None, None

    if not isinstance(result, dict):
        return [], False, None, None, None

    items, fornecedor, cnpj, valor_total_geral = _parse_table_result(result)

    if not items or len(items) == 0:
        print(f"[Stage2][{nup_id}] 0 itens na 1ª tentativa (Gemini texto)", flush=True)
        # TENTATIVA 2: AZURE (apenas se houver páginas com imagem grande + âncora)
        if pdf_path and req_pages and extract_table_text_with_azure and get_pages_with_large_images:
            pages_with_imgs = get_pages_with_large_images(pdf_path, req_pages)
            if not pages_with_imgs:
                print(
                    f"[Stage2][{nup_id}] Nenhuma página com imagem grande → pulando Azure",
                    flush=True,
                )
            else:
                try:
                    azure_tsvs: List[str] = []
                    for p_num in pages_with_imgs:
                        img_b64 = page_to_base64(pdf_path, p_num)
                        if img_b64:
                            tsv = extract_table_text_with_azure(img_b64)
                            if tsv:
                                azure_tsvs.append(tsv)

                    azure_tsv_combined = "\n".join(azure_tsvs)
                    if azure_tsv_combined.strip():
                        prompt_azure = (
                            STAGE2_TABLE_PROMPT
                            + "\n\nTEXTO DA TABELA (TSV do Azure):\n"
                            + azure_tsv_combined
                        )
                        result_azure, _, _ = proc._generate(  # type: ignore[attr-defined]
                            prompt_azure, "stage2_table_azure"
                        )
                        if isinstance(result_azure, dict):
                            items, fornecedor, cnpj, valor_total_geral = _parse_table_result(
                                result_azure
                            )
                            if items:
                                print(f"[Stage2][{nup_id}] Azure fallback: {len(items)} itens extraídos", flush=True)
                                return (
                                    items,
                                    True,
                                    float(valor_total_geral) if valor_total_geral is not None else None,
                                    fornecedor,
                                    cnpj,
                                )
                    if not items or len(items) == 0:
                        print(
                            f"[Stage2][{nup_id}] Azure: 0 itens → acionando Vision fallback",
                            flush=True,
                        )
                except Exception as e:
                    print(f"[Stage2][{nup_id}] Erro Azure: {e}", flush=True)

        # TENTATIVA 3: GEMINI VISION (só roda se o Azure falhou ou não retornou itens)
        if not items or len(items) == 0:
            if pdf_path and req_pages and page_to_base64:
                fallback_images: List[str] = []
                for p in req_pages:
                    img = page_to_base64(pdf_path, p)
                    if img:
                        fallback_images.append(img)
                if fallback_images:
                    try:
                        prompt_vision = (
                            STAGE2_TABLE_PROMPT
                            + "\n\nTEXTO DA TABELA:\n(sem texto extraído; use as imagens anexas)"
                        )
                        result_fb, _, _ = proc._generate_with_images(  # type: ignore[attr-defined]
                            prompt_vision, fallback_images, "stage2_table_vision_fallback"
                        )
                        if isinstance(result_fb, dict):
                            items, fornecedor, cnpj, valor_total_geral = _parse_table_result(
                                result_fb
                            )
                            if items:
                                print(
                                    f"[Stage2][{nup_id}] Vision fallback: {len(items)} item(ns) extraído(s)",
                                    flush=True,
                                )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Vision fallback falhou no estágio 2: %s", exc)

    print(
        f"[Stage2][{nup_id}] Resultado: {len(items)} itens, fornecedor={fornecedor or '?'}, cnpj={cnpj or '?'}",
        flush=True,
    )
    return (
        items,
        True,
        float(valor_total_geral) if valor_total_geral is not None else None,
        fornecedor,
        cnpj,
    )


def verify_calculations(
    items: List[Stage2Item],
    valor_total_documento: Optional[float],
) -> Stage2VerificacaoCalculos:
    """
    Verificação matemática pura (sem IA):
    - Confere se QTD × V.UNT == V.TOTAL por item (com tolerância de R$0,02).
    - Confere se soma dos V.TOTAL == valor total da requisição (quando informado).
    """
    divergencias: List[Stage2Divergencia] = []
    total_calc = Decimal("0.00")

    for item in items:
        q = _safe_decimal(item.quantidade)
        vu = _safe_decimal(item.valor_unitario)
        vt = _safe_decimal(item.valor_total)
        if q is None or vu is None or vt is None:
            continue

        expected = (q * vu).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        diff = abs(expected - vt)
        if diff > Decimal("0.02"):
            divergencias.append(
                Stage2Divergencia(
                    tipo="item",
                    item=item.item,
                    esperado=float(expected),
                    encontrado=float(vt),
                )
            )

        total_calc += vt

    vt_doc_dec = _safe_decimal(valor_total_documento) if valor_total_documento is not None else total_calc

    if vt_doc_dec is not None:
        diff_total = abs(total_calc - vt_doc_dec)
        if diff_total > Decimal("0.02"):
            divergencias.append(
                Stage2Divergencia(
                    tipo="total",
                    item=None,
                    esperado=float(total_calc),
                    encontrado=float(vt_doc_dec),
                )
            )

    correto = len(divergencias) == 0

    return Stage2VerificacaoCalculos(
        correto=correto,
        divergencias=divergencias,
        valor_total_calculado=float(total_calc),
    )


def structure_with_ai(requisition_text: str) -> Dict[str, Any]:
    """
    Fallback geral: envia todo o texto da requisição ao Gemini para
    extração dos campos principais (instrumento, UASG, tipo de empenho,
    fornecedor, CNPJ).
    """
    try:
        proc = GeminiProcessor()
    except ValueError as exc:
        logger.warning("Gemini indisponível para estágio 2 (fallback geral): %s", exc)
        return {}

    prompt = STAGE2_GENERAL_PROMPT + "\n\nTEXTO DA PEÇA DA REQUISIÇÃO:\n" + requisition_text

    try:
        result, _, _ = proc._generate(prompt, "stage2_general")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao executar fallback geral do estágio 2 com IA: %s", exc)
        return {}

    if not isinstance(result, dict):
        return {}

    return result


def _compute_confidence(
    data: Stage2Data,
    ai_conf: Optional[int] = None,
    instrument_conf_override: Optional[int] = None,
    tipo_empenho_conf_override: Optional[int] = None,
    uasg_conf_override: Optional[int] = None,
    cnpj_conf_override: Optional[int] = None,
) -> Stage2Confidence:
    """
    Gera scores de confiança heurísticos por campo e geral.
    """
    inst_conf = 0
    if instrument_conf_override is not None:
        inst_conf = max(0, min(100, instrument_conf_override))
    elif data.instrumento and (data.instrumento.tipo or data.instrumento.numero):
        inst_conf = 85

    uasg_conf = 0
    if uasg_conf_override is not None:
        uasg_conf = max(0, min(100, uasg_conf_override))
    elif data.uasg and data.uasg.codigo:
        uasg_conf = 90
        if data.uasg.nome:
            uasg_conf = 95

    tipo_empenho_conf = 0
    if tipo_empenho_conf_override is not None:
        tipo_empenho_conf = max(0, min(100, tipo_empenho_conf_override))
    elif data.tipo_empenho:
        tipo_empenho_conf = 90

    fornecedor_conf = 0
    if data.fornecedor:
        fornecedor_conf = 80
        if data.cnpj:
            fornecedor_conf = 90

    cnpj_conf = 0
    if cnpj_conf_override is not None:
        cnpj_conf = max(0, min(100, cnpj_conf_override))
    elif data.cnpj and isinstance(data.cnpj, str) and CNPJ_STRICT_REGEX.fullmatch(data.cnpj):
        cnpj_conf = 95
    elif data.cnpj:
        cnpj_conf = 60

    valor_total_conf = 0
    if data.valor_total is not None:
        valor_total_conf = 80
        if data.verificacao_calculos and data.verificacao_calculos.correto:
            valor_total_conf = 95

    itens_conf = 0
    if data.itens:
        itens_conf = 90

    scores = [
        inst_conf,
        uasg_conf,
        tipo_empenho_conf,
        fornecedor_conf,
        cnpj_conf,
        valor_total_conf,
        itens_conf,
    ]
    valid = [s for s in scores if s > 0]
    geral = int(round(sum(valid) / len(valid))) if valid else (ai_conf or 0)

    return Stage2Confidence(
        instrumento=inst_conf,
        uasg=uasg_conf,
        tipo_empenho=tipo_empenho_conf,
        fornecedor=fornecedor_conf,
        cnpj=cnpj_conf,
        valor_total=valor_total_conf,
        itens=itens_conf,
        geral=geral,
    )


def compute_nd_req_from_items(items: List[Stage2Item]) -> Optional[str]:
    """
    Calcula a ND agregada da requisição de forma determinística e segura.

    Regra:
    - Usa apenas ND/SI finais válidas por item (par elemento/subelemento canônico);
    - Se todos os itens que possuem ND/SI concordarem em um único valor EE.SS,
      esse valor é adotado como nd_req;
    - Se houver conflito entre itens (mais de um EE.SS distinto) ou poucos dados,
      não inventa um valor agregado e retorna None.
    """
    if not items:
        return None

    canonicals: List[str] = [it.nd_si for it in items if it.nd_si]
    if not canonicals:
        return None

    unique = set(canonicals)
    if len(unique) == 1:
        return canonicals[0]

    # Conflito entre itens com ND/SI divergente → não agregamos.
    return None


def _build_stage2_uasg(
    codigo: Optional[str],
    nome: Optional[str],
    instrumento_tipo: Optional[str] = None,
) -> Stage2UASG:
    """
    Constrói o objeto UASG garantindo que, quando houver código conhecido,
    o nome da OM venha do mapa fixo. Se o código não estiver no mapa,
    mantém apenas o código (nome = None).

    Quando não há código:
    - Se o instrumento é Contrato, UASG é opcional. Retorna marcador
      "N/A (Contrato)" para exibição no frontend;
    - Caso contrário, preserva apenas o nome informado.
    """
    codigo_norm = (codigo or "").strip() or None

    if codigo_norm:
        try:
            from ..uasg_store import get_uasg_nome
            mapped_name = get_uasg_nome(codigo_norm) or UASG_TO_OM.get(codigo_norm) or nome
        except ImportError:
            from uasg_store import get_uasg_nome
            mapped_name = get_uasg_nome(codigo_norm) or UASG_TO_OM.get(codigo_norm) or nome
        return Stage2UASG(codigo=codigo_norm, nome=mapped_name)

    # Para contratos, a UASG pode não existir no processo sem ser erro.
    if instrumento_tipo and "contrato" in instrumento_tipo.lower():
        return Stage2UASG(codigo=None, nome="N/A (Contrato)")

    return Stage2UASG(codigo=None, nome=nome)


def run(
    all_pages: Dict[str, str],
    pdf_path: str | Path | None = None,
    image_pages: List[int] | None = None,
    total_pages: int = 0,
    nup_id: str = "",
) -> Dict[str, Any]:
    """
    Executa o Estágio 2 usando todas as páginas extraídas.

    Parâmetros:
        all_pages: mapa "pagina_n" -> texto bruto.
        pdf_path: caminho do PDF original (para conversão de páginas-imagem).
        image_pages: números das páginas que são imagem (para Vision quando a tabela estiver nelas).
        total_pages: total de páginas do PDF (opcional).
        nup_id: identificador da análise para logs (ex.: primeiros 11 chars do NUP).
    """
    if not all_pages:
        result = Stage2Result(
            status="error",
            method="regex",
            data=None,
            confidence=None,
            inactive_fields=["verificacao_nd", "mascara"],
        )
        return result.model_dump()

    requisition_pages = find_requisition_pages(all_pages, nup_id=nup_id)
    print(f"[Stage2][{nup_id}] Req páginas: {requisition_pages}", flush=True)
    if not requisition_pages:
        result = Stage2Result(
            status="error",
            method="regex",
            data=None,
            confidence=None,
            inactive_fields=["verificacao_nd", "mascara"],
        )
        return result.model_dump()

    texts: List[str] = []
    for page_num in requisition_pages:
        key = f"pagina_{page_num}"
        texts.append(all_pages.get(key, "") or "")

    requisition_text = "\n\n".join(texts)

    # Instrumento: usa extrator especializado baseado em candidatos e score.
    instr_candidates = extract_instrument_candidates(requisition_text, section="requisicao")
    instr_resolution = resolve_instrument(instr_candidates)
    instrumento_data = instr_resolution.get("instrument") or {}
    instrumento_conf = int(instr_resolution.get("confidence") or 0)
    instrumento_source = instr_resolution.get("source")
    instrumento_matched_text = instr_resolution.get("matched_text")
    instrumento_normalized_text = instr_resolution.get("normalized_text")
    instrumento_reason = instr_resolution.get("reason")

    # UASG: usa extrator especializado baseado em candidatos e score.
    uasg_candidates = extract_uasg_candidates(requisition_text, section="requisicao")
    uasg_resolution = resolve_uasg(uasg_candidates)
    uasg_data = uasg_resolution.get("uasg") or {}
    uasg_conf = int(uasg_resolution.get("confidence") or 0)

    # Fallback textual amplo para UASG, alimentando o resolvedor especializado.
    if not any(uasg_data.values()):
        fallback_uasg = _search_uasg_all_pages(all_pages)
        if any(fallback_uasg.values()):
            # Reexecuta o resolvedor com candidatos gerados a partir do texto fallback.
            combined_texts = []
            for key, txt in all_pages.items():
                if key.startswith("pagina_"):
                    combined_texts.append(txt or "")
            fb_text = "\n\n".join(combined_texts)
            fb_candidates = extract_uasg_candidates(fb_text, section="processo", page_scope="all_pages")
            uasg_resolution = resolve_uasg(fb_candidates)
            uasg_data = uasg_resolution.get("uasg") or {}
            uasg_conf = int(uasg_resolution.get("confidence") or 0)

    # Tipo de empenho: usa extrator especializado baseado em candidatos e score.
    tipo_cands = extract_tipo_empenho_candidates(requisition_text, section="requisicao")
    tipo_res = resolve_tipo_empenho(tipo_cands)
    tipo_empenho_value = tipo_res.get("value")
    tipo_empenho_conf = int(tipo_res.get("confidence") or 0)

    # CNPJ: usa extrator especializado baseado em candidatos e score (texto nativo).
    cnpj_cands = extract_cnpj_candidates(requisition_text, section="requisicao")
    cnpj_res = resolve_cnpj(cnpj_cands)
    cnpj_value = cnpj_res.get("formatted_value")
    cnpj_conf = int(cnpj_res.get("confidence") or 0)

    # Fallback leve para lógica legada apenas quando o resolvedor especializado
    # não encontrou valor confiável.
    legacy_tipo = None
    if not tipo_empenho_value:
        legacy_tipo = extract_empenho_type(requisition_text)
        if legacy_tipo:
            tipo_empenho_value = legacy_tipo

    try:
        items, extracted_by_ai, valor_total_geral, fornecedor_tab, cnpj_tab = extract_items_table(
            texts, pdf_path=pdf_path, req_pages=requisition_pages, image_pages=image_pages or [], nup_id=nup_id,
        )
    except Exception as exc:
        print(f"[Stage2][{nup_id}] ERRO em extract_items_table: {exc}", flush=True)
        traceback.print_exc()
        items, extracted_by_ai, valor_total_geral, fornecedor_tab, cnpj_tab = [], False, None, None, None

    valor_total = valor_total_geral
    if valor_total is None and items:
        total_dec = Decimal("0.00")
        for it in items:
            vt = _safe_decimal(it.valor_total)
            if vt is not None:
                total_dec += vt
        valor_total = float(total_dec)

    verificacao = verify_calculations(items, valor_total)

    # ND agregada da requisição (nd_req) calculada a partir das NDs finais dos itens.
    nd_req = compute_nd_req_from_items(items)

    # Sanitizar fornecedor e cnpj caso venham como dict da IA
    if isinstance(fornecedor_tab, dict):
        fornecedor_tab = fornecedor_tab.get("nome") or fornecedor_tab.get("razao_social") or None
        if fornecedor_tab is not None:
            fornecedor_tab = str(fornecedor_tab)
    if isinstance(cnpj_tab, dict):
        cnpj_tab = cnpj_tab.get("numero") or cnpj_tab.get("cnpj") or None
        if cnpj_tab is not None:
            cnpj_tab = _normalize_cnpj(str(cnpj_tab))

    # Determinar fornecedor e CNPJ finais:
    # - fornecedor continua vindo principalmente da tabela/IA;
    # - CNPJ prioriza o resolvedor especializado em texto nativo,
    #   com fallback para a tabela/IA quando necessário.
    final_fornecedor = fornecedor_tab
    final_cnpj = cnpj_value or cnpj_tab

    data = Stage2Data(
        instrumento=Stage2Instrument(
            tipo=instrumento_data.get("tipo"),
            numero=instrumento_data.get("numero"),
            confidence=instrumento_conf or None,
            source=str(instrumento_source) if instrumento_source else None,
            matched_text=str(instrumento_matched_text) if instrumento_matched_text else None,
            normalized_text=(
                str(instrumento_normalized_text) if instrumento_normalized_text else None
            ),
            resolution_reason=str(instrumento_reason) if instrumento_reason else None,
            candidates=instr_resolution.get("candidates") or [],
        )
        if any(instrumento_data.values())
        else None,
        uasg=_build_stage2_uasg(
            codigo=uasg_data.get("codigo"),
            nome=uasg_data.get("nome"),
            instrumento_tipo=instrumento_data.get("tipo"),
        )
        if any(uasg_data.values())
        else None,
        uasg_details=(
            Stage2UASGDetails(
                codigo=uasg_data.get("codigo"),
                nome=uasg_data.get("nome"),
                confidence=uasg_conf or None,
                source=str(uasg_resolution.get("source")) if uasg_resolution.get("source") else None,
                matched_text=str(uasg_resolution.get("matched_text"))
                if uasg_resolution.get("matched_text")
                else None,
                normalized_text=str(uasg_resolution.get("normalized_text"))
                if uasg_resolution.get("normalized_text")
                else None,
                resolution_reason=str(uasg_resolution.get("reason"))
                if uasg_resolution.get("reason")
                else None,
                candidates=uasg_resolution.get("candidates") or [],
            )
            if any(uasg_data.values())
            else None
        ),
        tipo_empenho=tipo_empenho_value,
        tipo_empenho_details=(
            Stage2TipoEmpenho(
                value=tipo_empenho_value,
                confidence=tipo_empenho_conf or None,
                source=str(tipo_res.get("source")) if tipo_res.get("source") else None,
                matched_text=str(tipo_res.get("matched_text"))
                if tipo_res.get("matched_text")
                else None,
                normalized_text=str(tipo_res.get("normalized_text"))
                if tipo_res.get("normalized_text")
                else None,
                resolution_reason=str(tipo_res.get("reason")) if tipo_res.get("reason") else None,
                candidates=tipo_res.get("candidates") or [],
            )
            if tipo_empenho_value
            else None
        ),
        fornecedor=final_fornecedor,
        cnpj=final_cnpj,
        cnpj_details=(
            Stage2CNPJDetails(
                value=str(cnpj_res.get("value")) if cnpj_res.get("value") else None,
                formatted_value=cnpj_value,
                confidence=cnpj_conf or None,
                source=str(cnpj_res.get("source")) if cnpj_res.get("source") else None,
                matched_text=str(cnpj_res.get("matched_text"))
                if cnpj_res.get("matched_text")
                else None,
                normalized_text=str(cnpj_res.get("normalized_text"))
                if cnpj_res.get("normalized_text")
                else None,
                resolution_reason=str(cnpj_res.get("reason")) if cnpj_res.get("reason") else None,
                candidates=cnpj_res.get("candidates") or [],
            )
            if cnpj_res
            else None
        ),
        valor_total=valor_total,
        nd_req=nd_req,
        itens=items,
        verificacao_calculos=verificacao,
        extracted_by_ai=extracted_by_ai,
    )

    used_ai = False
    ai_conf: Optional[int] = None

    missing_core = sum(
        1
        for field in [
            data.instrumento,
            data.uasg,
            data.tipo_empenho,
            data.fornecedor,
            data.cnpj,
        ]
        if not field
    )

    if missing_core >= 3 or not data.itens:
        ai_data = structure_with_ai(requisition_text)
        if ai_data:
            used_ai = True
            inst_ai = ai_data.get("instrumento") or {}
            uasg_ai = ai_data.get("uasg") or {}
            tipo_ai = ai_data.get("tipo_empenho")
            fornecedor_ai = ai_data.get("fornecedor")
            cnpj_ai = ai_data.get("cnpj")
            ai_conf_raw = ai_data.get("confianca")
            try:
                ai_conf = int(ai_conf_raw) if ai_conf_raw is not None else None
            except (TypeError, ValueError):
                ai_conf = None

            if not data.instrumento and inst_ai:
                data.instrumento = Stage2Instrument(
                    tipo=inst_ai.get("tipo"),
                    numero=inst_ai.get("numero"),
                )
            if not data.uasg and uasg_ai:
                data.uasg = _build_stage2_uasg(
                    codigo=uasg_ai.get("codigo"),
                    nome=uasg_ai.get("nome"),
                    instrumento_tipo=inst_ai.get("tipo"),
                )
            if not data.tipo_empenho and tipo_ai:
                data.tipo_empenho = tipo_ai
            if not data.fornecedor and fornecedor_ai:
                if isinstance(fornecedor_ai, dict):
                    fornecedor_ai = fornecedor_ai.get("nome") or fornecedor_ai.get("razao_social")
                data.fornecedor = str(fornecedor_ai) if fornecedor_ai else None
            if not data.cnpj and cnpj_ai:
                if isinstance(cnpj_ai, dict):
                    cnpj_ai = cnpj_ai.get("numero") or cnpj_ai.get("cnpj")
                data.cnpj = _normalize_cnpj(str(cnpj_ai)) if cnpj_ai else None

    if data.instrumento and data.instrumento.numero:
        data.instrumento.numero = normalize_instrument_year(data.instrumento.numero)

    confidence = _compute_confidence(
        data,
        ai_conf=ai_conf,
        instrument_conf_override=instrumento_conf,
        tipo_empenho_conf_override=tipo_empenho_conf if tipo_empenho_value else None,
        uasg_conf_override=uasg_conf if any(uasg_data.values()) else None,
        cnpj_conf_override=cnpj_conf if cnpj_value else None,
    )

    # Para contratos, a UASG é opcional; para os demais instrumentos
    # (Pregão, Dispensa, Inexigibilidade, Ata de Registro de Preços),
    # a ausência de UASG caracteriza extração incompleta (status partial).
    instrumento_tipo_lower = (
        (data.instrumento.tipo or "").lower() if data.instrumento else ""
    )
    uasg_obrigatoria = not (
        instrumento_tipo_lower and "contrato" in instrumento_tipo_lower
    )

    if (
        not data.instrumento
        and not data.uasg
        and not data.tipo_empenho
        and not data.fornecedor
        and not data.cnpj
        and not data.itens
    ):
        status = "error"
    elif not data.itens or not data.instrumento or (uasg_obrigatoria and not data.uasg):
        status = "partial"
    else:
        status = "success"

    method = "regex"
    if used_ai and extracted_by_ai:
        method = "hybrid"
    elif used_ai:
        method = "ai"
    elif extracted_by_ai:
        method = "ai"

    result = Stage2Result(
        status=status,
        method=method,
        data=data,
        confidence=confidence,
        inactive_fields=["verificacao_nd", "mascara"],
    )

    return result.model_dump()
