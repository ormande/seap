"""
Estágio 1 — Identificação do processo (NUP, Requisição, OM).

Camadas:
- extração via regex (rápida, gratuita)
- fallback via IA (Gemini) quando regex não encontra tudo
- verificação com score de confiança por campo e geral
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

try:
    from ..ai_processor import GeminiProcessor
except ImportError:
    from ai_processor import GeminiProcessor

logger = logging.getLogger(__name__)


NUP_REGEX = re.compile(r"\d{5}\.\d{6}/\d{4}-\d{2}")

REQUISICAO_REGEX_MAIN = re.compile(
    r"Requisi[çc][aã]o\s*N?[°ºo]?\s*-?\s*(\d{1,3})\/?(\d{4})?",
    flags=re.IGNORECASE,
)

REQUISICAO_REGEX_ALT = re.compile(
    r"Req\s*N?[°ºo]?\s*-?\s*(\d{1,3})\/?(\d{4})?",
    flags=re.IGNORECASE,
)


OM_LIST = [
    {"sigla": "9º B Sup", "extenso": "9º Batalhão de Suprimento"},
    {"sigla": "9º B Mnt", "extenso": "9º Batalhão de Manutenção"},
    {"sigla": "9º B Sau", "extenso": "9º Batalhão de Saúde"},
    {"sigla": "9º Gpt Log", "extenso": "9º Grupamento Logístico"},
    {"sigla": "18º B Trnp", "extenso": "18º Batalhão de Transporte"},
]


STAGE1_PROMPT = """
Você é um especialista em documentos de licitação do governo brasileiro e Exército Brasileiro.

Analise o texto abaixo extraído da PRIMEIRA PÁGINA de um processo licitatório 
e extraia APENAS os seguintes campos:

1. NUP (Número Único de Protocolo): aparece após "PROCESSO NUP", formato 
   XXXXX.XXXXXX/XXXX-XX
2. Requisição: aparece após "ASSUNTO:", pode estar como "Requisição N°XX/XXXX", 
   "Req XX", "Requisição XX/XXXX" — extrair número e ano separados
3. OM (Organização Militar): aparece após "Órgão de Origem:", nome por extenso.

As únicas OMs VÁLIDAS para este sistema são (use exatamente estes textos):
- 9º Batalhão de Suprimento (sigla: 9º B Sup)
- 9º Batalhão de Manutenção (sigla: 9º B Mnt)
- 9º Batalhão de Saúde (sigla: 9º B Sau)
- 9º Grupamento Logístico (sigla: 9º Gpt Log)
- 18º Batalhão de Transporte (sigla: 18º B Trnp)

No JSON de saída, o campo "om" DEVE ser um objeto com:
- "nome": string com o nome por extenso, padronizado exatamente como na lista acima
- "sigla": string com a sigla da OM ou null se não reconhecida
- "validada": boolean indicando se a OM foi reconhecida na lista fixa
- "confianca": número inteiro de 0 a 100 (use valor alto, ex.: 98, se reconhecida; use 50 se não tiver certeza ou não estiver na lista)

EXEMPLO:
Texto: "PROCESSO NUP 64445.003210/2025-45 ... ASSUNTO: Requisição N°15/2025 
de material de expediente ... Órgão de Origem: 9º Grupamento Logístico"
Resposta: {
  "nup": "64445.003210/2025-45",
  "requisicao": {
    "numero": 15,
    "ano": 2025,
    "texto_original": "Requisição N°15/2025"
  },
  "om": {
    "nome": "9º Grupamento Logístico",
    "sigla": "9º Gpt Log",
    "validada": true,
    "confianca": 98
  },
  "confianca": 95
}

Retorne APENAS JSON válido, sem markdown, sem explicações.
Se não encontrar um campo, use null.
Campo confianca é de 0 a 100 indicando sua certeza geral.
"""


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _clean_om_candidate(text: str) -> str:
    """
    Limpa o texto bruto da OM removendo campos que possam ter vindo na mesma
    linha ou na linha seguinte (Data da Criação, CNPJ, etc.).
    """
    if not text:
        return ""

    cleaned = _normalize_whitespace(text)

    stop_keywords = [
        "data da criação",
        "data:",
        "cnpj",
        "endereço",
        "endereco",
        "telefone",
        "tel.",
        "e-mail",
        "email",
    ]

    pattern_stop = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in stop_keywords) + r")\b",
        flags=re.IGNORECASE,
    )
    m = pattern_stop.search(cleaned)
    if m:
        cleaned = cleaned[: m.start()]

    # Remove datas ou números longos no final (ex.: "10/02/2026", telefones, etc.)
    cleaned = re.sub(r"\d{2}/\d{2}/\d{4}.*$", "", cleaned).strip()
    cleaned = re.sub(r"[-–—:·\s]+$", "", cleaned).strip()

    return cleaned


def _match_known_om(nome: str) -> Dict[str, Any]:
    """
    Faz matching do nome da OM contra a lista fixa.
    Tenta por extenso e por sigla usando substring case-insensitive.
    """
    base = _normalize_whitespace(nome)
    if not base:
        return {
            "nome": "",
            "sigla": None,
            "validada": False,
            "confianca": 0,
        }

    lowered = base.lower()

    for om in OM_LIST:
        extenso = om["extenso"]
        sigla = om["sigla"]
        if extenso.lower() in lowered or lowered in extenso.lower():
            return {
                "nome": extenso,
                "sigla": sigla,
                "validada": True,
                "confianca": 98,
            }
        if sigla.lower() in lowered or lowered in sigla.lower():
            return {
                "nome": extenso,
                "sigla": sigla,
                "validada": True,
                "confianca": 98,
            }

    return {
        "nome": base,
        "sigla": None,
        "validada": False,
        "confianca": 50,
    }


def _build_om_field(raw_om: Any) -> Optional[Dict[str, Any]]:
    """
    Constrói o objeto OM padronizado a partir de um valor bruto (string ou dict).
    """
    if raw_om is None:
        return None

    if isinstance(raw_om, dict) and "nome" in raw_om:
        nome_raw = raw_om.get("nome") or ""
    else:
        nome_raw = str(raw_om)

    cleaned = _clean_om_candidate(nome_raw)
    if not cleaned:
        return None

    return _match_known_om(cleaned)


def _extract_nup(page_text: str) -> Optional[str]:
    lines = page_text.splitlines()
    for idx, line in enumerate(lines):
        upper = line.upper()
        if "PROCESSO NUP" in upper:
            candidate_lines = []
            if idx + 1 < len(lines):
                candidate_lines.append(lines[idx + 1])
            if idx + 2 < len(lines):
                candidate_lines.append(lines[idx + 2])
            for cand in candidate_lines:
                m = NUP_REGEX.search(cand)
                if m:
                    return m.group(0).strip()
    match_any = NUP_REGEX.search(page_text)
    if match_any:
        return match_any.group(0).strip()
    return None


def _extract_requisicao(page_text: str) -> Optional[Dict[str, Any]]:
    lines = page_text.splitlines()
    snippet = ""
    for line in lines:
        if "ASSUNTO" in line.upper():
            idx = line.upper().find("ASSUNTO")
            snippet = line[idx + len("ASSUNTO") :].strip()
            break
    if not snippet:
        return None
    m = REQUISICAO_REGEX_MAIN.search(snippet) or REQUISICAO_REGEX_ALT.search(snippet)
    if not m:
        return None
    numero_str, ano_str = m.group(1), m.group(2)
    try:
        numero = int(numero_str)
    except (TypeError, ValueError):
        numero = None
    ano: Optional[int] = None
    if ano_str:
        try:
            ano_val = int(ano_str)
            if 1900 <= ano_val <= 2100:
                ano = ano_val
        except ValueError:
            ano = None

    return {
        "numero": numero,
        "ano": ano,
        "texto_original": _normalize_whitespace(m.group(0)),
    }


def _extract_om_raw(page_text: str) -> Optional[str]:
    """
    Extrai o texto bruto logo após "Órgão de Origem:" podendo incluir
    parte da linha seguinte. A limpeza e validação ficam em _build_om_field.
    """
    lines = page_text.splitlines()
    pattern = re.compile(r"Órgão de Origem:\s*(.*)", flags=re.IGNORECASE)

    for idx, line in enumerate(lines):
        m = pattern.search(line)
        if not m:
            continue

        candidate = m.group(1) or ""

        # Tenta capturar continuação da OM na linha seguinte, se não parecer outro campo.
        if idx + 1 < len(lines):
            next_line = (lines[idx + 1] or "").strip()
            if next_line and not re.match(
                r"^(Data da Criação|Data\b|CNPJ\b|Endere[cç]o\b|Telefone\b|Tel\.|E-?mail\b)",
                next_line,
                flags=re.IGNORECASE,
            ):
                candidate = candidate + " " + next_line

        candidate = _clean_om_candidate(candidate)
        if candidate:
            return candidate

    return None


def extract_with_regex(page_text: str) -> Dict[str, Any]:
    """
    Primeira camada: tenta extrair NUP, Requisição e OM apenas com regex.
    """
    nup = _extract_nup(page_text)
    requisicao = _extract_requisicao(page_text)
    om_raw = _extract_om_raw(page_text)
    om = _build_om_field(om_raw)

    return {
        "nup": nup,
        "requisicao": requisicao,
        "om": om,
    }


def extract_with_ai(page_text: str, processor: Optional[GeminiProcessor] = None) -> Dict[str, Any]:
    """
    Fallback com IA (Gemini) quando a regex não encontra todos os campos.
    """
    try:
        proc = processor or GeminiProcessor()
    except ValueError as exc:
        logger.warning("Gemini indisponível para estágio 1 (extração): %s", exc)
        return {}

    prompt = STAGE1_PROMPT.strip() + "\n\nTEXTO:\n" + page_text
    result, _, _ = proc._generate(prompt, "stage1_identification")  # type: ignore[attr-defined]

    if not isinstance(result, dict):
        return {}

    return result


def _compute_confidence_for_fields(extracted: Dict[str, Any], original_text: str) -> Dict[str, int]:
    nup = (extracted.get("nup") or "") if isinstance(extracted, dict) else ""
    requisicao = extracted.get("requisicao") or {}
    om = extracted.get("om") or None

    nup_conf = 0
    if isinstance(nup, str) and nup.strip():
        if NUP_REGEX.fullmatch(nup.strip()):
            nup_conf = 95
        elif NUP_REGEX.search(original_text or ""):
            nup_conf = 80
        else:
            nup_conf = 40

    req_conf = 0
    if isinstance(requisicao, dict):
        numero = requisicao.get("numero")
        ano = requisicao.get("ano")
        if isinstance(numero, int) and numero > 0:
            req_conf = 80
            if isinstance(ano, int) and 1900 <= ano <= 2100:
                req_conf += 10
        elif numero is not None or ano is not None:
            req_conf = 40

    om_conf = 0
    if isinstance(om, dict):
        raw_conf = om.get("confianca")
        if isinstance(raw_conf, (int, float)):
            om_conf = int(raw_conf)
    elif isinstance(om, str) and om.strip():
        # Compatibilidade caso em algum cenário ainda venha string.
        om_norm = om.strip()
        om_conf = 75
        if any(
            token in om_norm.lower()
            for token in [
                "batalh",
                "companh",
                "regimento",
                "comando",
                "quartel",
                "exército",
                "logístico",
            ]
        ):
            om_conf += 10

    fields = [nup_conf, req_conf, om_conf]
    valid = [v for v in fields if v > 0]
    geral = int(round(sum(valid) / len(valid))) if valid else 0

    return {
        "nup": max(0, min(100, nup_conf)),
        "requisicao": max(0, min(100, req_conf)),
        "om": max(0, min(100, om_conf)),
        "geral": max(0, min(100, geral)),
    }


def verify_extraction(
    extracted: Dict[str, Any],
    original_text: str,
    method: str,
    processor: Optional[GeminiProcessor] = None,
) -> Dict[str, int]:
    """
    Verifica a extração, sempre retornando scores numéricos por campo e geral.
    Usa IA de verificação apenas quando necessário (baixa confiança).
    """
    base_scores = _compute_confidence_for_fields(extracted, original_text)

    all_high = (
        method == "regex"
        and base_scores["nup"] >= 85
        and base_scores["requisicao"] >= 85
        and base_scores["om"] >= 85
    )

    if all_high:
        return base_scores

    try:
        proc = processor or GeminiProcessor()
    except ValueError as exc:
        logger.warning("Gemini indisponível para verificação do estágio 1: %s", exc)
        return base_scores

    try:
        json_extraido = json.dumps(extracted, ensure_ascii=False)
        verification = proc.verify_extraction(original_text, json_extraido)
        score = float(verification.get("score_confianca", 0.0))
        geral_ai = int(round(max(0.0, min(1.0, score)) * 100))
        base_scores["geral"] = geral_ai
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao verificar extração do estágio 1 com IA: %s", exc)

    return base_scores


def _merge_regex_and_ai(regex_data: Dict[str, Any], ai_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mescla resultados de regex e IA, priorizando o que já estiver bem definido.
    """
    merged: Dict[str, Any] = {}

    merged["nup"] = regex_data.get("nup") or ai_data.get("nup")

    req_regex = regex_data.get("requisicao") or {}
    req_ai = ai_data.get("requisicao") or {}
    if isinstance(req_regex, dict) or isinstance(req_ai, dict):
        numero = req_regex.get("numero") or req_ai.get("numero")
        ano = req_regex.get("ano") or req_ai.get("ano")
        texto_original = req_regex.get("texto_original") or req_ai.get("texto_original")
        merged["requisicao"] = {
            "numero": numero,
            "ano": ano,
            "texto_original": texto_original,
        }
    else:
        merged["requisicao"] = None

    om_source = regex_data.get("om")
    if not om_source:
        om_source = ai_data.get("om")
    merged["om"] = _build_om_field(om_source)

    return merged


def run(page_text: str) -> Dict[str, Any]:
    """
    Executa o Estágio 1 para o texto da primeira página.
    """
    if not page_text or not page_text.strip():
        return {
            "status": "error",
            "method": "regex",
            "data": None,
            "confidence": {"nup": 0, "requisicao": 0, "om": 0, "geral": 0},
        }

    regex_result = extract_with_regex(page_text)
    has_all_regex = all(
        regex_result.get(field) is not None for field in ("nup", "requisicao", "om")
    )

    used_ai = False
    final_data: Dict[str, Any] = regex_result
    method = "regex"

    if not has_all_regex:
        ai_result = extract_with_ai(page_text)
        if ai_result:
            used_ai = True
            final_data = _merge_regex_and_ai(regex_result, ai_result)
            method = "ai" if not any(regex_result.values()) else "hybrid"

    confidence = verify_extraction(final_data, page_text, method=method)

    nup_val = final_data.get("nup")
    req_val = final_data.get("requisicao")
    om_val = final_data.get("om")

    if not nup_val and not req_val and not om_val:
        status = "error"
    elif not nup_val or not req_val or not om_val:
        status = "partial"
    else:
        status = "success"

    return {
        "status": status,
        "method": "ai" if used_ai and method != "hybrid" else method,
        "data": final_data,
        "confidence": confidence,
    }

