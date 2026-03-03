"""
Estágio 5 — Despachos.

Responsável por:
- Identificar despachos no corpo do processo a partir de âncoras textuais.
- Extrair metadados básicos (número, data, assunto, autor/seção).
- Classificar o conteúdo via IA (Gemini) em encaminhamento, exigência ou informativo.
- Mapear exigências e verificar, em segunda passada, se foram atendidas em despachos posteriores.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from ..ai_processor import GeminiProcessor
from ..models import (
    Stage5Dispatch,
    Stage5Exigencia,
    Stage5ExigenciaStatus,
    Stage5Result,
)

logger = logging.getLogger(__name__)


DESPACHO_HEADER_REGEX = re.compile(
    r"Despacho\s+N[°ºo]\s*\.?\s*(.+?)(?:\n|$)", re.IGNORECASE
)

# Datas no formato "09/02/2026"
DATE_NUMERIC_REGEX = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

# Datas por extenso: "9 de fevereiro de 2026"
DATE_TEXT_REGEX = re.compile(
    r"\b(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})", re.IGNORECASE
)

ASSUNTO_REGEX = re.compile(r"Assunto\s*:\s*(.+)", re.IGNORECASE)

MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


STAGE5_PROMPT = """Você é um especialista em análise de despachos de 
processos licitatórios do Exército Brasileiro.

Analise o despacho abaixo e classifique-o. Extraia informações no formato JSON.

CLASSIFICAÇÃO:
- "encaminhamento": apenas encaminha, aprova ou autoriza (sem exigências)
- "exigencia": contém solicitações, correções ou pendências a resolver
- "informativo": apenas informa dados sem exigir nada

Para despachos com exigências, extraia CADA exigência individualmente.
Uma exigência é qualquer solicitação, correção pedida, documento faltante,
ou ação que alguém precisa tomar.

Retorne APENAS JSON:
{{
  "tipo": "encaminhamento|exigencia|informativo",
  "resumo": "Resumo de 1-2 frases do que o despacho diz",
  "exigencias": [
    {{
      "descricao": "Texto da exigência",
      "categoria": "correcao|documento|acao|regularizacao",
      "urgente": true/false
    }}
  ],
  "palavras_chave": ["aprovo", "encaminho"],
  "confianca": 90
}}

Se não houver exigências, retorne "exigencias": [].
Se o despacho for apenas encaminhamento, o resumo deve ser breve.
Retorne APENAS JSON válido, sem markdown."""


STAGE5_CROSS_CHECK_PROMPT = """Analise a sequência de despachos abaixo 
(em ordem cronológica) de um processo licitatório.

Despachos:
{lista_despachos_com_resumos}

Exigências encontradas:
{lista_exigencias}

Para CADA exigência, determine se foi ATENDIDA por um despacho posterior 
ou se permanece PENDENTE.

Retorne JSON:
{{
  "exigencias_status": [
    {{
      "descricao": "correção do valor do item 3",
      "despacho_origem": "324",
      "status": "atendida|pendente",
      "despacho_resolucao": "334",
      "evidencia": "Despacho 334 menciona que valor foi corrigido"
    }}
  ],
  "resultado_geral": "sem_pendencias|com_pendencias",
  "pendencias_abertas": []
}}

Retorne APENAS JSON válido."""


@dataclass
class _DispatchMeta:
    """Representa um despacho identificado no PDF antes de normalizar para Pydantic."""

    numero: Optional[str]
    data_str: Optional[str]
    assunto: Optional[str]
    autor_secao: Optional[str]
    pages: List[int]
    body_text: str
    full_text: str
    sort_date: Optional[datetime]


def _parse_date_from_text(text: str) -> Tuple[Optional[str], Optional[datetime]]:
    """
    Tenta extrair a data do despacho no formato DD/MM/YYYY ou por extenso.
    Retorna (data_normalizada, datetime) ou (None, None).
    """
    if not text:
        return None, None

    # Primeiro, tenta data numérica.
    m_num = DATE_NUMERIC_REGEX.search(text)
    if m_num:
        date_str = m_num.group(1)
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            dt = None
        return date_str, dt

    # Depois, tenta data por extenso.
    m_txt = DATE_TEXT_REGEX.search(text)
    if m_txt:
        day_s, month_s, year_s = m_txt.groups()
        try:
            day = int(day_s)
            year = int(year_s)
            month = MONTHS_PT.get(month_s.lower())
            if month:
                dt = datetime(year, month, day)
                # Normaliza para DD/MM/YYYY para facilitar consumo.
                return dt.strftime("%d/%m/%Y"), dt
        except ValueError:
            return None, None

    return None, None


def _extract_assunto(text: str) -> Optional[str]:
    """Extrai o assunto do despacho a partir da linha 'Assunto:'."""
    if not text:
        return None
    for line in text.splitlines():
        m = ASSUNTO_REGEX.search(line)
        if m:
            return m.group(1).strip()
    return None


def _infer_autor_from_numero(numero: Optional[str]) -> Optional[str]:
    """
    Infere autor/seção a partir do número do despacho,
    buscando siglas típicas como Fisc Adm, CAF, OD.
    """
    if not numero:
        return None
    raw = numero.lower()
    if "fisc adm" in raw:
        return "Fisc Adm"
    if "caf" in raw:
        return "CAF"
    if "od" in raw:
        return "OD"
    if "fisc" in raw:
        return "Fisc"
    return None


def _normalize_whitespace(text: str) -> str:
    """Normaliza espaços em branco para facilitar contagem de caracteres."""
    return re.sub(r"\s+", " ", text or "").strip()


def find_dispatch_pages(
    all_pages: Dict[str, str],
    used_pages: Optional[Dict[str, Set[int]]] = None,
) -> List[_DispatchMeta]:
    """
    Busca páginas com cabeçalho de despacho ("Despacho Nº"/"Despacho N°").

    - Agrupa páginas consecutivas como um mesmo despacho, desde que a página
      seguinte não contenha um novo cabeçalho de despacho.
    - Extrai número, data, assunto e autor/seção.
    - Ordena os despachos por data (quando disponível) ou número da primeira página.
    """
    if used_pages is None:
        used_pages = {}
    already_used: Set[int] = set()
    for pages in used_pages.values():
        already_used |= set(pages)

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

    dispatches: List[_DispatchMeta] = []
    current: Optional[_DispatchMeta] = None

    for idx, text in page_items:
        if idx in already_used:
            continue

        header_match = DESPACHO_HEADER_REGEX.search(text or "")
        if header_match:
            # Começa um novo despacho.
            numero = header_match.group(1).strip()

            # Corpo da primeira página: texto após a linha do cabeçalho.
            end = header_match.end()
            newline_pos = (text or "").find("\n", end)
            body_first = (
                (text or "")[newline_pos + 1 :] if newline_pos != -1 else (text or "")[end:]
            )

            data_str, sort_dt = _parse_date_from_text(text or "")
            assunto = _extract_assunto(text or "")
            autor = _infer_autor_from_numero(numero)

            current = _DispatchMeta(
                numero=numero,
                data_str=data_str,
                assunto=assunto,
                autor_secao=autor,
                pages=[idx],
                body_text=body_first.strip(),
                full_text=(text or ""),
                sort_date=sort_dt,
            )
            dispatches.append(current)
        elif current is not None:
            # Página de continuação: mesma peça, desde que seja imediatamente após.
            last_page = current.pages[-1]
            if idx == last_page + 1:
                current.pages.append(idx)
                current.full_text += "\n\n" + (text or "")
                current.body_text += "\n\n" + (text or "")
            else:
                current = None

    # Ordenação cronológica (quando possível).
    def _sort_key(d: _DispatchMeta) -> Tuple[datetime, int]:
        if d.sort_date:
            return d.sort_date, d.pages[0]
        # Fallback: usa ordem de página com uma data fictícia.
        return datetime(1900, 1, 1), d.pages[0]

    dispatches.sort(key=_sort_key)
    return dispatches


def _classify_dispatch_with_keywords(body_text: str) -> Dict[str, Any]:
    """
    Classificação heurística baseada em palavras-chave quando Gemini estiver indisponível.
    Útil como fallback para não quebrar o estágio 5.
    """
    text_low = (body_text or "").lower()

    encaminhamento_terms = [
        "encaminho",
        "encaminhar",
        "aprovo",
        "de acordo",
        "autorizo",
        "ciente",
        "nada a opor",
        "prossiga-se",
        "prossiga se",
    ]
    exigencia_terms = [
        "solicito",
        "solicitar",
        "providenciar",
        "corrigir",
        "juntar",
        "apresentar",
        "regularizar",
        "retificar",
        "substituir",
        "complementar",
        "pendente",
        "falta",
        "ausência de",
        "ausencia de",
        "não consta",
        "nao consta",
        "deve ser",
        "necessário",
        "necessario",
    ]

    has_exig = any(t in text_low for t in exigencia_terms)
    has_enc = any(t in text_low for t in encaminhamento_terms)

    if has_exig:
        tipo = "exigencia"
    elif has_enc:
        tipo = "encaminhamento"
    else:
        tipo = "informativo"

    return {
        "tipo": tipo,
        "resumo": None,
        "exigencias": [],
        "palavras_chave": [],
        "confianca": 60 if tipo != "informativo" else 70,
    }


def classify_dispatch(full_text: str, body_text: Optional[str] = None) -> Dict[str, Any]:
    """
    Classifica um despacho usando heurística de tamanho e Gemini.

    - Se o corpo (sem cabeçalho) tiver menos de 200 caracteres, assume
      que é encaminhamento simples e não chama a IA.
    - Caso contrário, usa o STAGE5_PROMPT com Gemini para obter JSON estruturado.
    """
    body = body_text if body_text is not None else full_text
    body_norm = _normalize_whitespace(body)

    if len(body_norm) < 200:
        # Encaminhamento curto: atalho sem IA.
        return {
            "tipo": "encaminhamento",
            "resumo": "Despacho curto de encaminhamento/aprovação sem exigências explícitas.",
            "exigencias": [],
            "palavras_chave": [],
            "confianca": 85,
        }

    try:
        proc = GeminiProcessor()
    except ValueError as exc:
        logger.warning("Gemini indisponível para estágio 5 (classificação): %s", exc)
        # Fallback simples por palavras-chave.
        return _classify_dispatch_with_keywords(body or full_text)

    prompt = STAGE5_PROMPT + "\n\nDESPACHO:\n" + full_text

    try:
        result, _, _ = proc._generate(prompt, "stage5_dispatch")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao classificar despacho no estágio 5 com IA: %s", exc)
        return _classify_dispatch_with_keywords(body or full_text)

    if not isinstance(result, dict):
        return _classify_dispatch_with_keywords(body or full_text)

    # Garante chaves esperadas.
    result.setdefault("tipo", "informativo")
    result.setdefault("resumo", None)
    result.setdefault("exigencias", [])
    result.setdefault("palavras_chave", [])
    if "confianca" not in result:
        result["confianca"] = 80
    return result


def cross_check_requirements(
    dispatches: Sequence[Stage5Dispatch],
    requirements: Sequence[Stage5Exigencia],
) -> Dict[str, Any]:
    """
    Envia todos os despachos + exigências ao Gemini para verificar se
    foram atendidas em despachos posteriores.

    Só deve ser chamado se houver exigências.
    """
    if not requirements:
        return {
            "exigencias_status": [],
            "resultado_geral": "sem_pendencias",
            "pendencias_abertas": [],
        }

    try:
        proc = GeminiProcessor()
    except ValueError as exc:
        logger.warning("Gemini indisponível para estágio 5 (cross-check): %s", exc)
        # Se IA não estiver disponível, assume tudo como pendente.
        return {
            "exigencias_status": [
                {
                    "descricao": r.descricao,
                    "despacho_origem": r.despacho_origem,
                    "status": "pendente",
                    "despacho_resolucao": None,
                    "evidencia": "Não foi possível executar verificação automática de pendências (IA indisponível).",
                }
                for r in requirements
            ],
            "resultado_geral": "com_pendencias",
            "pendencias_abertas": [r.descricao for r in requirements],
        }

    lista_desp = []
    for d in dispatches:
        numero = d.numero or "?"
        data = d.data or "?"
        resumo = d.resumo or ""
        tipo = d.tipo or "desconhecido"
        lista_desp.append(f"- Despacho {numero} ({data}) [{tipo}]: {resumo}")
    despachos_text = "\n".join(lista_desp)

    lista_exig = []
    for r in requirements:
        origem = r.despacho_origem or "?"
        lista_exig.append(f"- Despacho {origem}: {r.descricao}")
    exigencias_text = "\n".join(lista_exig)

    prompt = STAGE5_CROSS_CHECK_PROMPT.format(
        lista_despachos_com_resumos=despachos_text,
        lista_exigencias=exigencias_text,
    )

    try:
        result, _, _ = proc._generate(prompt, "stage5_cross_check")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao executar cross-check de exigências no estágio 5: %s", exc)
        # Fallback: considera todas as exigências como pendentes.
        return {
            "exigencias_status": [
                {
                    "descricao": r.descricao,
                    "despacho_origem": r.despacho_origem,
                    "status": "pendente",
                    "despacho_resolucao": None,
                    "evidencia": "Não foi possível executar verificação automática de pendências (falha na IA).",
                }
                for r in requirements
            ],
            "resultado_geral": "com_pendencias",
            "pendencias_abertas": [r.descricao for r in requirements],
        }

    if not isinstance(result, dict):
        return {
            "exigencias_status": [],
            "resultado_geral": "sem_pendencias",
            "pendencias_abertas": [],
        }
    return result


def run(
    all_pages: Dict[str, str],
    used_pages: Optional[Dict[str, Set[int]]] = None,
) -> Dict[str, Any]:
    """
    Orquestra o Estágio 5:
    - Localiza despachos no documento.
    - Classifica cada despacho (IA + heurística).
    - Executa verificação cruzada de exigências.
    """
    metas = find_dispatch_pages(all_pages, used_pages)
    if not metas:
        result = Stage5Result(
            status="sa",
            total_despachos=0,
            despachos=[],
            exigencias_pendentes=[],
            exigencias_atendidas=[],
            resultado="S/A",
            confidence={"geral": 100},
        )
        return result.model_dump()

    dispatch_models: List[Stage5Dispatch] = []
    all_requirements: List[Stage5Exigencia] = []

    # Último despacho cronológico (ultimato / ordem de análise) não gera pendências.
    final_meta = metas[-1]

    for meta in metas:
        classification = classify_dispatch(meta.full_text, body_text=meta.body_text)

        tipo = str(classification.get("tipo") or "informativo")
        resumo = classification.get("resumo")
        exigencias_raw = classification.get("exigencias") or []
        palavras_chave_raw = classification.get("palavras_chave") or []
        try:
            confianca = int(classification.get("confianca") or 0)
        except (TypeError, ValueError):
            confianca = 0

        exigencias: List[Stage5Exigencia] = []
        if isinstance(exigencias_raw, list):
            for raw in exigencias_raw:
                if not isinstance(raw, dict):
                    continue
                desc = str(raw.get("descricao") or "").strip()
                if not desc:
                    continue
                categoria = raw.get("categoria") or None
                urgente = bool(raw.get("urgente", False))
                ex = Stage5Exigencia(
                    descricao=desc,
                    categoria=categoria,
                    urgente=urgente,
                    despacho_origem=meta.numero or "",
                )
                exigencias.append(ex)
                # Exigências do ÚLTIMO despacho (ordem de análise) são
                # instruções internas e não contam como pendências do processo.
                if meta is not final_meta:
                    all_requirements.append(ex)

        palavras_chave: List[str] = []
        if isinstance(palavras_chave_raw, list):
            for w in palavras_chave_raw:
                if isinstance(w, str):
                    palavras_chave.append(w)

        dispatch_models.append(
            Stage5Dispatch(
                numero=meta.numero,
                data=meta.data_str,
                assunto=meta.assunto,
                autor_secao=meta.autor_secao,
                tipo=tipo,
                resumo=resumo,
                exigencias=exigencias,
                palavras_chave=palavras_chave,
                confianca=confianca,
                pages=meta.pages,
            )
        )

    # Se não houver exigências em nenhum despacho, resultado global é S/A.
    if not all_requirements:
        result = Stage5Result(
            status="sa",
            total_despachos=len(dispatch_models),
            despachos=dispatch_models,
            exigencias_pendentes=[],
            exigencias_atendidas=[],
            resultado="S/A",
            confidence={"geral": 90},
        )
        return result.model_dump()

    cross_result = cross_check_requirements(dispatch_models, all_requirements)
    status_list = cross_result.get("exigencias_status") or []

    pendentes: List[Stage5ExigenciaStatus] = []
    atendidas: List[Stage5ExigenciaStatus] = []

    for item in status_list:
        if not isinstance(item, dict):
            continue
        desc = str(item.get("descricao") or "").strip()
        if not desc:
            continue
        status = str(item.get("status") or "pendente")
        despacho_origem = str(item.get("despacho_origem") or "")
        despacho_resolucao = item.get("despacho_resolucao")
        evidencia = item.get("evidencia")

        status_model = Stage5ExigenciaStatus(
            descricao=desc,
            despacho_origem=despacho_origem,
            status=status,
            despacho_resolucao=despacho_resolucao,
            evidencia=evidencia,
        )
        if status == "atendida":
            atendidas.append(status_model)
        else:
            pendentes.append(status_model)

    resultado_geral = cross_result.get("resultado_geral") or (
        "com_pendencias" if pendentes else "sem_pendencias"
    )

    status_global = "sa" if resultado_geral == "sem_pendencias" and not pendentes else "com_pendencias"
    resultado_label = "S/A" if status_global == "sa" else "Pendências"

    confidence_geral = 90
    if status_global == "com_pendencias":
        confidence_geral = 85

    result = Stage5Result(
        status=status_global,
        total_despachos=len(dispatch_models),
        despachos=dispatch_models,
        exigencias_pendentes=pendentes,
        exigencias_atendidas=atendidas,
        resultado=resultado_label,
        confidence={"geral": confidence_geral},
    )
    return result.model_dump()

