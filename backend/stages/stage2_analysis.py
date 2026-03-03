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
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from ..ai_processor import GeminiProcessor
except ImportError:
    from ai_processor import GeminiProcessor

try:
    from ..models import (
        Stage2Confidence,
        Stage2Data,
        Stage2Divergencia,
        Stage2Instrument,
        Stage2Item,
        Stage2Result,
        Stage2UASG,
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
        Stage2UASG,
        Stage2VerificacaoCalculos,
    )

logger = logging.getLogger(__name__)


INSTRUMENTO_REGEX = re.compile(
    r"por\s+meio\s+d[oe]\s+"
    r"(Preg[aã]o\s+Eletr[oô]nico|[Cc]ontrato|[Dd]ispensa|[Ii]nexigibilidade)"
    r"\s*n?[°ºo]?\s*(\d+/\d{2,4})",
    flags=re.IGNORECASE,
)

UASG_AFTER_INSTRUMENTO_REGEX = re.compile(
    r"(?:UASG|UG|pela)\s*(16\d{4})\s*[–\-—]\s*(.+?)(?:\.|,|do\s+qual|$)",
    flags=re.IGNORECASE,
)

CANDIDATE_UASG_FLEX_REGEX = re.compile(
    r"(?:gerenciad[oa]\s+pel[oa]\s*(?:UASG|UG)?\s*|UASG\s*|UG\s*|pela\s*)"
    r"(16\d{4})\s*[–\-\s—]+\s*(.+?)(?:\.|,|do\s+qual|$)",
    flags=re.IGNORECASE,
)

UASG_TO_OM = {
    "160131": "9º Batalhão de Comunicações e Guerra Eletrônica",
    "160132": "3ª Companhia de Comunicações Leve",
    "160134": "9º Depósito de Suprimento",
    "160136": "9º Grupamento Logístico",
    "160516": "18º Batalhão de Transporte",
}

CNPJ_STRICT_REGEX = re.compile(
    r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$",
)

REQ_ANCHOR_REGEX = re.compile(
    r"\bReq\.?\s*(?:n[º°o\.]|nr\.?|nº|Nº|N°)?\s*\d+",
    flags=re.IGNORECASE,
)


STAGE2_TABLE_PROMPT = """
Você é um especialista em extração de tabelas de documentos de licitação do Exército Brasileiro.

Analise este TEXTO ou IMAGEM de tabela de itens de uma requisição militar e extraia
TODOS os itens no seguinte formato JSON:

{
  "fornecedor": "nome da empresa",
  "cnpj": "XX.XXX.XXX/XXXX-XX",
  "itens": [
    {
      "item": 1,
      "catmat": "código",
      "descricao": "descrição do material/serviço",
      "unidade": "und/kg/svc/m",
      "quantidade": 0,
      "nd_si": "classificação",
      "valor_unitario": 0.00,
      "valor_total": 0.00
    }
  ],
  "valor_total_geral": 0.00
}

REGRAS IMPORTANTES:
- NUNCA confunda NUP com CNPJ. NUP tem padrão XXXXX.XXXXXX/XXXX-XX (5.6/4-2 dígitos),
  enquanto CNPJ tem SEMPRE 14 dígitos com formato XX.XXX.XXX/XXXX-XX.
- Para CNPJ, use SEMPRE o formato XX.XXX.XXX/XXXX-XX (14 dígitos) e não utilize números
  de processo/NUP como se fossem CNPJ.
- O campo CatMat/CatServ (catmat) deve conter APENAS números (sem letras, hífens ou sufixos como 'Sv').
- O campo "unidade" (UND) é TEXTO (ex.: Sv, Un, Kg, M, M², L, Pç). NÃO remova letras deste campo.
  Apenas os campos "item" e "catmat" devem conter somente números.
- O campo ND/SI pode aparecer em múltiplos formatos. Normalize sempre para EE.SS (elemento.subelemento),
  por exemplo "30.24". Exemplos de normalização:
  * '30.24' -> '30.24'
  * '30/04' -> '30.04'
  * '33.90.30.34' -> '30.34'
  * '33.90.39/17' -> '39.17'
  * '4490.52.08' -> '52.08'
  * '33.9\\n0.39/\\n24' -> '39.24'
- Sempre preencha o campo "nd_si" com o valor normalizado EE.SS, mesmo que o formato original seja diferente.
- Se não encontrar um campo, use null.
- Valores monetários devem ser números decimais SEM R$ (ex: 1500.50) usando ponto como separador decimal.
- Se texto tem quebra de linha ou hífen silábico, junte as palavras.
- Extraia TODOS os itens, mesmo que a tabela seja longa.

Retorne APENAS JSON válido.
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
    formatted = (
        f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"
    )
    if not CNPJ_STRICT_REGEX.fullmatch(formatted):
        return None
    return formatted


def find_requisition_pages(all_pages: Dict[str, str]) -> List[int]:
    """
    Identifica as páginas que compõem a peça da requisição.

    Heurística:
    - Procura primeira página com "Req nº"/variações no cabeçalho.
    - Confirma presença de "Assunto:" ou "Rfr:" ou "Do:"/"Ao:" nas linhas seguintes.
    - Inclui páginas subsequentes enquanto apresentarem tópicos numerados
      (ex.: "1.", "2.") ou referências claras à continuidade da requisição.
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
            "Stage2: nenhuma página de requisição identificada. Candidatos avaliados: %s",
            debug_candidates,
        )
        return []

    requisition_pages: List[int] = [start_page]

    def _looks_like_continuation(text: str) -> bool:
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
        if _looks_like_continuation(text or ""):
            requisition_pages.append(idx)
        else:
            break

    logger.debug(
        "Stage2: páginas de requisição identificadas: %s (candidatos=%s)",
        requisition_pages,
        debug_candidates,
    )

    return requisition_pages


def extract_instrument_and_uasg(text: str) -> Dict[str, Any]:
    """
    Extrai instrumento (tipo + número) e UASG (código + nome) do texto.
    Normalmente aparecem no primeiro parágrafo/tópico.
    """
    instrumento: Dict[str, Optional[str]] = {"tipo": None, "numero": None}
    uasg: Dict[str, Optional[str]] = {"codigo": None, "nome": None}

    flat = _normalize_for_regex(text)
    head = flat[:4000]

    print("STAGE2 DEBUG | tópico 1 (primeiros 500 chars):", head[:500])

    m_inst = INSTRUMENTO_REGEX.search(head)
    print("STAGE2 DEBUG | instrumento match:", m_inst.group(0) if m_inst else None)
    if m_inst:
        tipo_raw, numero = m_inst.group(1), m_inst.group(2)
        tipo_norm = tipo_raw.lower()
        if "preg" in tipo_norm:
            tipo = "Pregão Eletrônico"
        elif "contrato" in tipo_norm:
            tipo = "Contrato"
        elif "dispensa" in tipo_norm:
            tipo = "Dispensa"
        elif "inexig" in tipo_norm:
            tipo = "Inexigibilidade"
        else:
            tipo = tipo_raw.strip()
        instrumento = {"tipo": tipo, "numero": numero.strip()}

        after = head[m_inst.end() : m_inst.end() + 900]
        print("STAGE2 DEBUG | trecho busca UASG (após instrumento):", after[:500])

        m_uasg = UASG_AFTER_INSTRUMENTO_REGEX.search(after)
        print(
            "STAGE2 DEBUG | UASG regex (após instrumento) match:",
            m_uasg.group(0) if m_uasg else None,
        )
        if not m_uasg:
            m_uasg = CANDIDATE_UASG_FLEX_REGEX.search(after)
            print(
                "STAGE2 DEBUG | UASG regex flex match:",
                m_uasg.group(0) if m_uasg else None,
            )

        if m_uasg:
            codigo, nome = m_uasg.group(1), m_uasg.group(2)
            uasg = {
                "codigo": codigo.strip(),
                "nome": format_om_name(_normalize_whitespace(nome)),
            }
    else:
        # Mesmo sem instrumento, tenta identificar UASG no cabeçalho/tópico 1
        m_uasg = CANDIDATE_UASG_FLEX_REGEX.search(head)
        print(
            "STAGE2 DEBUG | UASG (sem instrumento) match:",
            m_uasg.group(0) if m_uasg else None,
        )
        if m_uasg:
            codigo, nome = m_uasg.group(1), m_uasg.group(2)
            uasg = {
                "codigo": codigo.strip(),
                "nome": format_om_name(_normalize_whitespace(nome)),
            }

    return {"instrumento": instrumento, "uasg": uasg}


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
    Normaliza ND/SI para o formato EE.SS seguindo os formatos conhecidos.
    Se não for possível normalizar, retorna o valor original limpo.
    """
    if not raw:
        return ""
    s = re.sub(r"\s+", "", raw)
    s = s.replace(",", ".")

    m = re.match(r"^(\d{2})\.(\d{2})$", s)
    if m:
        return f"{m.group(1)}.{m.group(2)}"

    m = re.match(r"^(\d{2})/(\d{2})$", s)
    if m:
        return f"{m.group(1)}.{m.group(2).zfill(2)}"

    m = re.match(r"^\d{2}\.\d{2}\.(\d{2})\.(\d{2})$", s)
    if m:
        return f"{m.group(1)}.{m.group(2)}"

    m = re.match(r"^\d{2}\.\d{2}\.(\d{2})/(\d{2})$", s)
    if m:
        return f"{m.group(1)}.{m.group(2).zfill(2)}"

    m = re.match(r"^\d{4}\.(\d{2})\.(\d{2})$", s)
    if m:
        return f"{m.group(1)}.{m.group(2)}"

    return raw


def extract_items_table(
    pages_text: List[str],
    pdf_path: str | Path | None = None,
) -> Tuple[List[Stage2Item], bool, Optional[float], Optional[str], Optional[str]]:
    """
    Extrai a tabela de itens da requisição.

    Implementação inicial:
    - Usa Gemini com prompt especializado para interpretar o TEXTO das páginas.
    - Caso não haja texto, retorna lista vazia (suporte a OCR/vision pode ser
      adicionado em uma evolução futura).
    """
    combined = "\n\n".join(pages_text or []).strip()
    if not combined:
        return [], False, None, None, None

    try:
        proc = GeminiProcessor()
    except ValueError as exc:
        logger.warning("Gemini indisponível para extração de tabela no estágio 2: %s", exc)
        return [], False, None, None, None

    prompt = STAGE2_TABLE_PROMPT + "\n\nTEXTO DA TABELA:\n" + combined

    try:
        result, _, _ = proc._generate(prompt, "stage2_table")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao extrair tabela de itens com IA no estágio 2: %s", exc)
        return [], False, None, None, None

    if not isinstance(result, dict):
        return [], False, None, None, None

    fornecedor = result.get("fornecedor")
    cnpj = _normalize_cnpj(result.get("cnpj"))

    itens_raw = result.get("itens") or []
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
            nd_norm = normalize_nd(nd_raw) if nd_raw else None

            item = Stage2Item(
                item=item_int,
                catmat=_normalize_catmat(raw.get("catmat") or raw.get("codigo")),
                descricao_completa=desc_full,
                descricao_resumida=desc_short,
                unidade=_normalize_unidade(raw.get("unidade") or raw.get("und")),
                quantidade=float(q) if q is not None else None,
                nd_si=nd_norm,
                nd_si_original=nd_raw or None,
                valor_unitario=float(vu) if vu is not None else None,
                valor_total=float(vt) if vt is not None else None,
            )
            items.append(item)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Falha ao normalizar item da tabela no estágio 2: %s", exc)
            continue

    valor_total_geral = _safe_decimal(result.get("valor_total_geral"))
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
) -> Stage2Confidence:
    """
    Gera scores de confiança heurísticos por campo e geral.
    """
    inst_conf = 0
    if data.instrumento and (data.instrumento.tipo or data.instrumento.numero):
        inst_conf = 85

    uasg_conf = 0
    if data.uasg and data.uasg.codigo:
        uasg_conf = 90
        if data.uasg.nome:
            uasg_conf = 95

    tipo_empenho_conf = 0
    if data.tipo_empenho:
        tipo_empenho_conf = 90

    fornecedor_conf = 0
    if data.fornecedor:
        fornecedor_conf = 80
        if data.cnpj:
            fornecedor_conf = 90

    cnpj_conf = 0
    if data.cnpj and CNPJ_STRICT_REGEX.fullmatch(data.cnpj):
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
        mapped_name = UASG_TO_OM.get(codigo_norm)
        return Stage2UASG(codigo=codigo_norm, nome=mapped_name)

    # Para contratos, a UASG pode não existir no processo sem ser erro.
    if instrumento_tipo and "contrato" in instrumento_tipo.lower():
        return Stage2UASG(codigo=None, nome="N/A (Contrato)")

    return Stage2UASG(codigo=None, nome=nome)


def run(all_pages: Dict[str, str], pdf_path: str | Path | None = None) -> Dict[str, Any]:
    """
    Executa o Estágio 2 usando todas as páginas extraídas.

    Parâmetros:
        all_pages: mapa "pagina_n" -> texto bruto.
        pdf_path: caminho do PDF original (reservado para suporte futuro a OCR/vision).
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

    requisition_pages = find_requisition_pages(all_pages)
    print("STAGE2 DEBUG | páginas identificadas como requisição:", requisition_pages)
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

    core = extract_instrument_and_uasg(requisition_text)
    instrumento_data = core.get("instrumento") or {}
    uasg_data = core.get("uasg") or {}

    # Se não encontrou instrumento/UASG no tópico da requisição, tenta em TODAS as páginas.
    if not any(instrumento_data.values()) or not any(uasg_data.values()):
        broader_core = _search_instrument_and_uasg_all_pages(all_pages)
        inst_b = broader_core.get("instrumento") or {}
        uasg_b = broader_core.get("uasg") or {}
        if not any(instrumento_data.values()) and any(inst_b.values()):
            instrumento_data = inst_b
        if not any(uasg_data.values()) and any(uasg_b.values()):
            uasg_data = uasg_b

    tipo_empenho = extract_empenho_type(requisition_text)

    items, extracted_by_ai, valor_total_geral, fornecedor_tab, cnpj_tab = extract_items_table(
        texts, pdf_path=pdf_path
    )

    valor_total = valor_total_geral
    if valor_total is None and items:
        total_dec = Decimal("0.00")
        for it in items:
            vt = _safe_decimal(it.valor_total)
            if vt is not None:
                total_dec += vt
        valor_total = float(total_dec)

    verificacao = verify_calculations(items, valor_total)

    data = Stage2Data(
        instrumento=Stage2Instrument(
            tipo=instrumento_data.get("tipo"),
            numero=instrumento_data.get("numero"),
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
        tipo_empenho=tipo_empenho,
        fornecedor=fornecedor_tab,
        cnpj=cnpj_tab,
        valor_total=valor_total,
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
                data.fornecedor = fornecedor_ai
            if not data.cnpj and cnpj_ai:
                data.cnpj = cnpj_ai

    # Fallback extra: se, mesmo após regex em todas as páginas e fallback geral,
    # ainda não houver instrumento ou UASG, usa IA curta nas 3 primeiras páginas.
    if (not data.instrumento or not data.instrumento.tipo or not data.instrumento.numero) or (
        not data.uasg or not data.uasg.codigo
    ):
        fb_core = _fallback_instrument_and_uasg_with_ai(all_pages)
        if fb_core:
            inst_fb = fb_core.get("instrumento") or {}
            uasg_fb = fb_core.get("uasg") or {}
            if (not data.instrumento or not data.instrumento.tipo or not data.instrumento.numero) and inst_fb:
                data.instrumento = Stage2Instrument(
                    tipo=inst_fb.get("tipo"),
                    numero=inst_fb.get("numero"),
                )
            if (not data.uasg or not data.uasg.codigo) and uasg_fb:
                data.uasg = _build_stage2_uasg(
                    codigo=uasg_fb.get("codigo"),
                    nome=uasg_fb.get("nome"),
                    instrumento_tipo=inst_fb.get("tipo"),
                )

    if data.instrumento and data.instrumento.numero:
        data.instrumento.numero = normalize_instrument_year(data.instrumento.numero)

    confidence = _compute_confidence(data, ai_conf=ai_conf)

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

