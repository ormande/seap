"""
Estágio 3 — Notas de Crédito (NC).

Responsável por:
- Identificar páginas que contenham Notas de Crédito em diferentes formatos.
- Extrair campos principais de cada NC (número, UG emitente, destinos, valores).
- Suportar múltiplas NCs por processo.
- Usar IA (Gemini) como extrator principal, com fallback de dados do tópico 2
  da peça da requisição quando necessário.
- Para páginas que são imagens (screenshot SIAFI no PDF), usar Gemini Vision.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import google.generativeai as genai

from ..ai_processor import GeminiProcessor
from ..extractor import page_to_base64
from ..models import (
    Stage3Destination,
    Stage3NC,
    Stage3NCConfidence,
    Stage3Result,
)

logger = logging.getLogger(__name__)


NC_NUMBER_REGEX = re.compile(r"\b\d{4}NC\d{6}\b", flags=re.IGNORECASE)


STAGE3_PROMPT = """
Você é um especialista em documentos orçamentários do governo brasileiro,
especificamente Notas de Crédito (NC) do SIAFI.

Analise o texto abaixo extraído de uma Nota de Crédito e extraia os campos
no JSON especificado.

CAMPOS A EXTRAIR (somente do DESTINO do crédito, ignorar origem):
- numero_nc: formato XXXXNCXXXXXX (ex: 2026NC400428)
- ug_emitente: código de 6 dígitos
- valor: valor total em reais (número decimal, sem R$)
- esfera: geralmente 1 dígito
- ptres: código numérico
- fonte: código numérico longo (até 10 dígitos)
- ugr: código de 6 dígitos
- nd: Natureza de Despesa, 6 dígitos (ex: 339000, 339039)
- pi: código alfanumérico (Plano Interno)

REGRA DE EVENTOS (formato SIAFI com múltiplas linhas):
Se houver múltiplos eventos, o evento com NÚMERO MAIOR é o mais recente.
Para NDs iguais entre eventos diferentes, SOMENTE o evento mais recente
representa o saldo atual. Retornar cada ND única com o valor do evento
mais recente.

Se algum campo não for encontrado, use null.
Retorne APENAS JSON válido com campo "confianca" de 0 a 100.

Se houver múltiplas NDs no destino, retorne como lista:
{
  "numero_nc": "2026NC400428",
  "ug_emitente": "167504",
  "destinos": [
    {"esfera": "1", "ptres": "232180", "fonte": "1021000000",
     "nd": "339039", "ugr": "167504", "pi": "E3PCFSCDEGE",
     "valor": 2000.00, "evento": "301203"},
    {"esfera": "1", "ptres": "232180", "fonte": "1021000000",
     "nd": "339000", "ugr": "167504", "pi": "E3PCFSCDEGE",
     "valor": 2000.00, "evento": "301201"}
  ],
  "valor_total": 4000.00,
  "confianca": 90
}
""".strip()


# Modelos para Vision; em caso de 429 (quota), tenta o próximo.
MODELS_FALLBACK = [
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
]

# Prompt único para múltiplas imagens: detecta NCs e extrai em uma só chamada.
STAGE3_VISION_MULTI_PROMPT = """Estas imagens são páginas consecutivas de um processo licitatório.
Identifique quais delas contêm Notas de Crédito (NC) do SIAFI e extraia os dados de TODAS as NCs encontradas.

Se uma NC ocupa 2 páginas (cabeçalho numa, tabela de eventos noutra), combine os dados numa única NC.

Se nenhuma imagem contiver NC, retorne {"ncs_found": 0, "ncs": []}

Para cada NC encontrada, retorne:
{
  "ncs_found": N,
  "ncs": [
    {
      "pages": [10, 11],
      "numero_nc": "2026NC400428",
      "ug_emitente": "167504",
      "ug_favorecida": "167136",
      "destinos": [
        {
          "evento": "301203",
          "esfera": "1",
          "ptres": "232180",
          "fonte": "1021000000",
          "nd": "339039",
          "ugr": "167504",
          "pi": "E3PCFSCDEGE",
          "valor": 2000.00
        }
      ],
      "valor_total": 4000.00,
      "confianca": 90
    }
  ]
}

REGRAS:
- Para NDs iguais em eventos diferentes, SÓ o evento com número MAIOR (mais recente) conta
- Valores monetários como decimais sem R$
- Se algum campo não for legível, use null
Retorne APENAS JSON válido."""


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


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


def _parse_brazilian_currency(value: str) -> Optional[Decimal]:
    """
    Converte um valor no formato brasileiro (ex.: '2.000,00') para Decimal.
    """
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace("R$", "").replace(" ", "")
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def deduplicate_events(destinos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Para NDs iguais, manter SOMENTE o evento com número MAIOR
    (mais recente). Recalcular valor_total após deduplicação.
    """
    nd_map: Dict[Any, Dict[str, Any]] = {}
    for dest in destinos:
        nd = dest.get("nd")
        evento = dest.get("evento", "0")
        if nd not in nd_map or str(evento) > str(nd_map[nd].get("evento", "0")):
            nd_map[nd] = dest
    return list(nd_map.values())


def _apply_deduplication_and_recalc(
    data: Dict[str, Any],
    destinos_key: str = "destinos",
    valor_total_key: str = "valor_total",
) -> None:
    """Aplica deduplicate_events aos destinos e recalcula valor_total com prints de debug."""
    destinos = data.get(destinos_key) or []
    if not destinos:
        return
    print(f"[Stage3] Antes da deduplicação: {len(destinos)} destinos")
    destinos_deduplicados = deduplicate_events(destinos)
    print(f"[Stage3] Após deduplicação: {len(destinos_deduplicados)} destinos")
    data[destinos_key] = destinos_deduplicados
    valor_total = sum(
        float(_safe_decimal(d.get("valor")) or 0) for d in destinos_deduplicados
    )
    data[valor_total_key] = valor_total
    print(f"[Stage3] Valor total recalculado: {valor_total}")


def _group_nc_pages(nc_pages: List[Dict[str, Any]]) -> List[List[int]]:
    """
    Agrupa páginas consecutivas de mesmo formato como pertencentes à mesma NC.
    """
    if not nc_pages:
        return []

    # Ordena por número de página.
    sorted_pages = sorted(nc_pages, key=lambda x: x["page"])
    groups: List[List[int]] = []
    current_group: List[int] = [sorted_pages[0]["page"]]
    current_format = sorted_pages[0]["format"]
    last_page = sorted_pages[0]["page"]

    for entry in sorted_pages[1:]:
        page = entry["page"]
        fmt = entry["format"]
        if fmt == current_format and page == last_page + 1:
            current_group.append(page)
        else:
            groups.append(current_group)
            current_group = [page]
            current_format = fmt
        last_page = page

    if current_group:
        groups.append(current_group)

    print("[Stage3] Grupos de páginas de NC formados:", groups)
    logger.debug("Stage3: grupos de páginas de NC formados: %s", groups)
    return groups


def find_nc_pages(
    all_pages: Dict[str, str],
    image_pages: Optional[List[int]] = None,
    pdf_path: Optional[str] = None,
    total_pages: int = 0,
    req_pages: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Identifica páginas que contêm NCs e agrupa em conjuntos por NC.

    Retorna lista de dicts: cada um com "pages", "format", e opcionalmente
    "data" e "method" (gemini_vision para NCs extraídas de imagem).

    Critérios texto:
    - Usa âncoras POSITIVAS específicas de NC (SIAFI ou Web).
    - Usa âncoras NEGATIVAS para descartar capas/requisições, exceto quando
      houver forte evidência de SIAFI (3+ âncoras SIAFI).

    Se nenhuma NC for encontrada por texto e houver image_pages + pdf_path,
    verifica páginas-imagem via Gemini Vision.
    """
    # Âncoras POSITIVAS SIAFI
    siafi_anchors = [
        r"SIAFI\d{4}",
        r"CONTABIL-DEMONSTRA-DIARIO|CONSULTA DIARIO CONTABIL",
        r"DOCUMENTO\s+WEB\s*:\s*\d{4}NC",
        r"UG/GESTAO\s+EMITENTE",
        r"V\s+A\s+L\s+O\s+R",
        r"EVENTO\s+ESF\s+PTRES",
    ]

    # Âncoras POSITIVAS Web
    web_anchors = [
        r"Itens de Contabiliza[çc][aã]o",
        r"C[eé]lula Or[çc]ament[aá]ria",
        r"Destino do Cr[eé]dito",
        r"Origem do Cr[eé]dito",
        r"Sequencial\s+\d+\s*\|\s*Situa[çc][aã]o:\s*Contabilizado",
    ]

    # Âncoras NEGATIVAS (indicam NÃO ser NC, salvo forte evidência SIAFI)
    negative_anchors = [
        r"PROCESSO\s+NUP",
        r"PE[ÇC]AS\s+PROCESSUAIS",
        r"ASSUNTO:\s*Requisi",
        r"[OÓ]rg[aã]o\s+de\s+Origem:",
        r"Nos\s+termos\s+contidos",
    ]

    nc_pages_meta: List[Dict[str, Any]] = []
    nc_groups: List[Dict[str, Any]] = []

    # Debug bruto: mostra início do texto de cada página.
    for page_num_str, text in all_pages.items():
        print(f"[Stage3 RAW] Página {page_num_str}: {repr((text or '')[:300])}")

    for key, text in all_pages.items():
        if not key.startswith("pagina_"):
            continue
        try:
            page_num = int(key.replace("pagina_", ""))
        except ValueError:
            continue

        page_text = text or ""
        siafi_score = sum(
            1 for anc in siafi_anchors if re.search(anc, page_text, re.IGNORECASE)
        )
        web_score = sum(
            1 for anc in web_anchors if re.search(anc, page_text, re.IGNORECASE)
        )

        negative_hits = [
            neg
            for neg in negative_anchors
            if re.search(neg, page_text, re.IGNORECASE)
        ]
        has_negative = bool(negative_hits)

        print(
            f"[Stage3] Página {page_num}: "
            f"negativas={len(negative_hits)} ({negative_hits}), "
            f"SIAFI_score={siafi_score}, Web_score={web_score}"
        )

        if has_negative and siafi_score < 3:
            print(
                f"[Stage3] Página {page_num} descartada (âncora negativa forte, "
                f"SIAFI_score={siafi_score})"
            )
            continue

        if siafi_score >= 2 or web_score >= 2:
            fmt = "siafi" if siafi_score > web_score else "web"
            nc_pages_meta.append(
                {
                    "page": page_num,
                    "format": fmt,
                    "siafi_score": siafi_score,
                    "web_score": web_score,
                }
            )
            print(
                f"[Stage3] Página {page_num} identificada como NC "
                f"(formato={fmt}, SIAFI:{siafi_score}, Web:{web_score})"
            )
        else:
            print(
                f"[Stage3] Página {page_num} ignorada "
                f"(SIAFI:{siafi_score}, Web:{web_score})"
            )

    groups = _group_nc_pages(nc_pages_meta)
    for group in groups:
        fmt = "siafi"
        for meta in nc_pages_meta:
            if meta["page"] == group[0]:
                fmt = meta["format"]
                break
        nc_groups.append({
            "pages": group,
            "format": fmt,
            "data": None,
            "method": "text",
        })

    # Se não encontrou NC por texto, tentar páginas-imagem em UMA chamada Vision
    if not nc_groups and image_pages and pdf_path:
        print(
            f"[Stage3] Nenhuma NC por texto. Filtrando e enviando "
            f"páginas-imagem em uma única chamada Vision..."
        )
        candidate_pages = filter_candidate_pages(
            image_pages,
            all_pages,
            exclude_pages=req_pages or [],
            total_pages=total_pages,
        )
        if candidate_pages:
            vision_groups = extract_ncs_from_images_batch(pdf_path, candidate_pages)
            nc_groups.extend(vision_groups)

    print("[Stage3] Grupos finais de páginas de NC:", [g["pages"] for g in nc_groups])
    return nc_groups


def detect_nc_format(page_text: str) -> str:
    """
    Detecta o formato predominante da NC nesta página.
    """
    upper = (page_text or "").upper()

    # Formato SIAFI completo: SIAFI + EVENTO ESF PTRES
    if "SIAFI" in upper and "EVENTO ESF PTRES" in upper:
        return "siafi_complete"

    # Formato SIAFI parcial: SIAFI + DOCUMENTO WEB, mas sem EVENTO
    if "SIAFI" in upper and "DOCUMENTO WEB" in upper and "EVENTO ESF PTRES" not in upper:
        return "siafi_partial"

    # Formato Web completo: Célula Orçamentária + Destino do Crédito
    if (
        ("CÉLULA ORÇAMENTÁRIA" in upper or "CELULA ORCAMENTARIA" in upper)
        and ("DESTINO DO CRÉDITO" in upper or "DESTINO DO CREDITO" in upper)
    ):
        return "web_complete"

    # Formato Web padrão: UG Emitente + Tipo + NC
    if (
        "UG EMITENTE" in upper
        and "UG/GESTAO EMITENTE" not in upper
        and "TIPO" in upper
        and " NC" in upper
    ):
        return "web_standard"

    return "unknown"


def _parse_siafi_header(text: str) -> Dict[str, Optional[str]]:
    """
    Extrai número da NC, UG emitente e UG favorecida do cabeçalho SIAFI.
    """
    numero_nc: Optional[str] = None
    ug_emitente: Optional[str] = None
    ug_favorecida: Optional[str] = None

    # Normaliza para facilitar regex (acentos podem variar)
    upper = text.upper()

    m_nc = re.search(
        r"DOCUMENTO\s+WEB\s*:\s*(\d{4}NC\d{6})",
        upper,
        flags=re.IGNORECASE,
    )
    if m_nc:
        numero_nc = m_nc.group(1)

    m_uge = re.search(
        r"UG/GESTAO\s+EMITENTE:\s*(\d{6})",
        upper,
        flags=re.IGNORECASE,
    )
    if m_uge:
        ug_emitente = m_uge.group(1)

    m_ugf = re.search(
        r"UG/GESTAO\s+FAVORECIDA:\s*(\d{6})",
        upper,
        flags=re.IGNORECASE,
    )
    if m_ugf:
        ug_favorecida = m_ugf.group(1)

    header = {
        "numero_nc": numero_nc,
        "ug_emitente": ug_emitente,
        "ug_favorecida": ug_favorecida,
    }
    print("STAGE3 DEBUG | cabeçalho SIAFI extraído:", header)
    return header


def _parse_siafi_events(text: str) -> List[Dict[str, Any]]:
    """
    Faz parsing da tabela de eventos do print SIAFI.

    Estrutura de 2 linhas por evento:
    Linha 1: número_linha (3 dígitos), evento (6 dígitos), valor (R$)
    Linha 2: esfera, ptres, fonte, nd, ugr, pi.
    """
    events: List[Dict[str, Any]] = []
    lines = text.splitlines()

    line1_re = re.compile(
        r"^\s*(\d{3})\s+(\d{6})\s+.*?([\d.]+,\d{2})\s*$"
    )
    # ESF pode estar ausente em formato parcial; por isso usamos (\d?) opcional.
    line2_re = re.compile(
        r"^\s*(\d?)\s+(\d{4,6})\s+(\d{7,10})\s+(\d{6})\s+(\d{6})\s+(\S+)"
    )

    i = 0
    while i < len(lines):
        m1 = line1_re.match(lines[i])
        if m1 and i + 1 < len(lines):
            m2 = line2_re.match(lines[i + 1])
            if m2:
                linha = int(m1.group(1))
                evento = m1.group(2)
                valor_dec = _parse_brazilian_currency(m1.group(3))

                esfera = m2.group(1) or None
                ptres = m2.group(2)
                fonte = m2.group(3)
                nd = m2.group(4)
                ugr = m2.group(5)
                pi = m2.group(6)

                events.append(
                    {
                        "linha": linha,
                        "evento": evento,
                        "valor": float(valor_dec) if valor_dec is not None else None,
                        "esfera": esfera,
                        "ptres": ptres,
                        "fonte": fonte,
                        "nd": nd,
                        "ugr": ugr,
                        "pi": pi,
                    }
                )
                i += 2
                continue
        i += 1

    # Deduplicação por ND: mantém apenas o evento mais recente (maior número)
    nd_map: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        nd = ev.get("nd")
        if not nd:
            continue
        if nd not in nd_map or int(ev["evento"]) > int(nd_map[nd]["evento"]):
            nd_map[nd] = ev

    deduped = list(nd_map.values())
    print("STAGE3 DEBUG | eventos SIAFI parseados (deduplicados por ND):", deduped)
    return deduped


def _parse_web_header(text: str) -> Dict[str, Optional[str]]:
    """
    Extrai número da NC e UG emitente do cabeçalho Web.
    """
    ug_emitente: Optional[str] = None
    numero_nc: Optional[str] = None

    # Tenta capturar UG Emitente pela linha "UG Emitente"
    m_ug_line = re.search(
        r"UG\s+Emitente[^\n]*\n([ \t]*)(\d{6})",
        text,
        flags=re.IGNORECASE,
    )
    if m_ug_line:
        ug_emitente = m_ug_line.group(2)

    # Região de Ano / Tipo / Número
    m_ano_tipo = re.search(
        r"Ano\s+Tipo\s+N[úu]mero[^\n]*\n([^\n]+)",
        text,
        flags=re.IGNORECASE,
    )
    if m_ano_tipo:
        linha = m_ano_tipo.group(1)
        m_vals = re.search(
            r"(\d{4})\s+NC\s+(\d{1,6})",
            linha,
            flags=re.IGNORECASE,
        )
        if m_vals:
            ano = m_vals.group(1)
            numero = int(m_vals.group(2))
            numero_nc = f"{ano}NC{numero:06d}"

    # Fallback: procura padrão XXXXNCXXXXXX em qualquer lugar
    if not numero_nc:
        m_nc = NC_NUMBER_REGEX.search(text)
        if m_nc:
            numero_nc = m_nc.group(0)

    header = {
        "numero_nc": numero_nc,
        "ug_emitente": ug_emitente,
    }
    print("STAGE3 DEBUG | cabeçalho Web extraído:", header)
    return header


def _parse_web_destinos(text: str) -> List[Dict[str, Any]]:
    """
    Extrai destinos (NDs) da tabela 'Destino do Crédito' / 'Célula Orçamentária'.
    """
    destinos: List[Dict[str, Any]] = []

    m_section = re.search(
        r"(?:Destino do Crédito|C[eé]lula Orçament[áa]ria)(.+?)(?:Origem do Crédito|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m_section:
        print("STAGE3 DEBUG | seção de destino Web não encontrada")
        return destinos

    dest_text = m_section.group(1)
    print("STAGE3 DEBUG | texto da seção de destino Web (primeiros 400 chars):", dest_text[:400])

    line_re = re.compile(
        r"Destino\s*\d+\s+(\d)\s+(\d{4,6})\s+(\d{7,10})\s+(\d{6})\s+(\d{6})\s+(\S+)\s+([\d.]+,\d{2})",
        flags=re.IGNORECASE,
    )

    for m in line_re.finditer(dest_text):
        esfera = m.group(1)
        ptres = m.group(2)
        fonte = m.group(3)
        nd = m.group(4)
        ugr = m.group(5)
        pi = m.group(6)
        valor_dec = _parse_brazilian_currency(m.group(7))

        destinos.append(
            {
                "esfera": esfera,
                "ptres": ptres,
                "fonte": fonte,
                "nd": nd,
                "ugr": ugr,
                "pi": pi,
                "valor": float(valor_dec) if valor_dec is not None else None,
            }
        )

    print("STAGE3 DEBUG | destinos Web parseados:", destinos)
    return destinos


def _extract_with_ai(text: str) -> Dict[str, Any]:
    """
    Usa Gemini com STAGE3_PROMPT para estruturar uma NC.
    """
    try:
        proc = GeminiProcessor()
    except ValueError as exc:
        logger.warning("Gemini indisponível para estágio 3 (NC): %s", exc)
        return {}

    prompt = STAGE3_PROMPT + "\n\nTEXTO DA NOTA DE CRÉDITO:\n" + text

    try:
        result, _, _ = proc._generate(prompt, "stage3_nc")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao extrair NC com IA no estágio 3: %s", exc)
        return {}

    if not isinstance(result, dict):
        return {}
    # Deduplicação de eventos (fallback IA)
    _apply_deduplication_and_recalc(result)
    return result


def _call_gemini_vision_with_fallback(
    prompt: str,
    images_base64: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Chama o Gemini com prompt e opcionalmente várias imagens.
    Rate limit: 2 s antes da chamada. Em caso de 429, tenta próximo modelo.
    Retorna o texto da resposta ou None.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY não definida.")
    genai.configure(api_key=api_key)
    time.sleep(2)  # Rate limiting para não estourar limite por minuto
    content: List[Any] = [prompt]
    if images_base64:
        for img_b64 in images_base64:
            if not img_b64:
                continue
            img_bytes = base64.b64decode(img_b64)
            content.append(
                {"inline_data": {"mime_type": "image/png", "data": img_bytes}}
            )
    last_error: Optional[Exception] = None
    for model_name in MODELS_FALLBACK:
        try:
            model = genai.GenerativeModel(
                model_name,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            response = model.generate_content(content)
            text = (response.text or "").strip()
            if text:
                return text
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if "429" in str(exc):
                print(
                    f"[Stage3] {model_name} quota excedida, tentando próximo modelo..."
                )
                logger.warning("Gemini 429 ao usar %s: %s", model_name, exc)
                continue
            raise
    if last_error:
        logger.warning("Falha em todos os modelos Vision: %s", last_error)
        print(f"[Stage3] Vision falhou após fallback: {last_error}")
    return None


def extract_ncs_from_images_batch(
    pdf_path: str,
    candidate_page_numbers: List[int],
) -> List[Dict[str, Any]]:
    """
    Envia TODAS as imagens candidatas numa única chamada ao Gemini.
    Retorna lista de grupos no formato nc_groups (pages, format, data, method).
    """
    if not candidate_page_numbers:
        return []
    images_b64: List[str] = []
    for page_num in candidate_page_numbers:
        img_b64 = page_to_base64(pdf_path, page_num)
        if img_b64:
            images_b64.append(img_b64)
        else:
            print(f"[Stage3] Não foi possível converter página {page_num} para imagem")
    if not images_b64:
        return []
    print(f"[Stage3] Enviando {len(images_b64)} imagem(ns) em uma única chamada Vision")
    # Informar ao modelo o número de página de cada imagem para "pages" no JSON
    pages_note = (
        f"As imagens enviadas correspondem, em ordem, às páginas do documento: "
        f"{candidate_page_numbers}. Use esses números no campo \"pages\" de cada NC."
    )
    prompt = STAGE3_VISION_MULTI_PROMPT + "\n\n" + pages_note
    text = _call_gemini_vision_with_fallback(
        prompt,
        images_base64=images_b64,
    )
    if not text:
        return []
    try:
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        data = json.loads(text)
    except json.JSONDecodeError as exc:  # noqa: BLE001
        logger.warning("Resposta Vision não é JSON válido: %s", exc)
        print(f"[Stage3] Resposta Vision inválida: {exc}")
        return []
    ncs_found = data.get("ncs_found", 0)
    ncs_list = data.get("ncs") or []
    if not ncs_list or ncs_found == 0:
        print("[Stage3] Nenhuma NC encontrada nas imagens")
        return []
    nc_groups: List[Dict[str, Any]] = []
    for nc in ncs_list:
        if not isinstance(nc, dict):
            continue
        pages = nc.get("pages") or []
        if not pages:
            continue
        # data para merge_nc_data e Stage3NC: numero_nc, ug_emitente, destinos, valor_total, confianca
        nc_data = {k: v for k, v in nc.items() if k != "pages"}
        # Deduplicação após extração por Gemini Vision
        _apply_deduplication_and_recalc(nc_data)
        nc_groups.append({
            "pages": pages,
            "format": "image_siafi",
            "data": nc_data,
            "method": "gemini_vision",
        })
        print(f"[Stage3] NC extraída via Vision (páginas {pages})")
    return nc_groups


def filter_candidate_pages(
    image_pages: List[int],
    all_pages: Dict[str, str],
    exclude_pages: Optional[List[int]] = None,
    total_pages: int = 0,
) -> List[int]:
    """
    Filtra páginas-imagem ANTES de enviar ao Gemini: descarta as que
    claramente não são NC (certidões, despachos, requisição, início/fim do doc).
    """
    if exclude_pages is None:
        exclude_pages = []
    exclude_set = set(exclude_pages)
    # Texto que indica que a página NÃO é NC (rodapé ou conteúdo mínimo extraído)
    discard_patterns = [
        r"SICAF",
        r"CADIN",
        r"Consulta Consolidada",
        r"Despacho",
        r"Termo de Abertura",
        r"TCU",
        r"certid[aã]o",
        r"negativa\s+de\s+debitos",
    ]
    pattern = re.compile("|".join(discard_patterns), re.IGNORECASE)
    filtered: List[int] = []
    for page_num in image_pages:
        if page_num in exclude_set:
            print(f"[Stage3] Página {page_num} ignorada (já identificada por outro estágio)")
            continue
        # Descartar páginas muito no início (1-3) ou últimas 2
        if page_num <= 3:
            print(f"[Stage3] Página {page_num} ignorada (início do documento)")
            continue
        if total_pages >= 2 and page_num >= total_pages - 1:
            print(f"[Stage3] Página {page_num} ignorada (final do documento)")
            continue
        key = f"pagina_{page_num}"
        text = (all_pages.get(key) or "").strip()
        if pattern.search(text):
            print(f"[Stage3] Página {page_num} ignorada (rodapé/texto indica certidão ou despacho)")
            continue
        filtered.append(page_num)
    filtered.sort()
    print(f"[Stage3] Páginas-imagem candidatas após filtro: {filtered}")
    return filtered


def extract_nc_web(text: str) -> Dict[str, Any]:
    """
    Extrai campos de NC em formato web (modelos 1 e 4).

    Implementação principal por regex, com fallback para IA quando necessário.
    """
    header = _parse_web_header(text)
    destinos = _parse_web_destinos(text)

    if not header.get("numero_nc") and not destinos:
        # Fallback completo para IA
        return _extract_with_ai(text)

    data: Dict[str, Any] = {
        "numero_nc": header.get("numero_nc"),
        "ug_emitente": header.get("ug_emitente"),
        "destinos": destinos,
    }
    # Deduplicação após parse web (destinos)
    _apply_deduplication_and_recalc(data)

    print("STAGE3 DEBUG | dados Web extraídos (antes do merge):", data)
    return data


def extract_nc_siafi(text: str) -> Dict[str, Any]:
    """
    Extrai campos de NC em formato SIAFI (modelos 2 e 3).

    Implementação principal por regex seguindo a estrutura de 2 linhas por evento.
    A regra de eventos (evento mais recente por ND) é aplicada explicitamente.
    """
    header = _parse_siafi_header(text)
    events = _parse_siafi_events(text)

    if not header.get("numero_nc") and not events:
        # Fallback completo para IA
        return _extract_with_ai(text)

    destinos: List[Dict[str, Any]] = []
    for ev in events:
        destinos.append(
            {
                "esfera": ev.get("esfera"),
                "ptres": ev.get("ptres"),
                "fonte": ev.get("fonte"),
                "nd": ev.get("nd"),
                "ugr": ev.get("ugr"),
                "pi": ev.get("pi"),
                "valor": ev.get("valor"),
                "evento": ev.get("evento"),
            }
        )

    data: Dict[str, Any] = {
        "numero_nc": header.get("numero_nc"),
        "ug_emitente": header.get("ug_emitente"),
        "destinos": destinos,
    }
    # Deduplicação após parse_siafi_events
    _apply_deduplication_and_recalc(data)

    print("STAGE3 DEBUG | dados SIAFI extraídos (antes do merge):", data)
    return data


def extract_nc_from_requisition(
    all_pages: Dict[str, str],
    req_pages: List[int],
) -> Dict[str, Any]:
    """
    Fallback: extrai dados parciais do Tópico 2 da requisição.
    Busca por PTRES, ND, Fonte, etc.
    """
    if not req_pages:
        return {}

    textos: List[str] = []
    for page_num in req_pages:
        key = f"pagina_{page_num}"
        textos.append(all_pages.get(key, "") or "")
    text = "\n".join(textos)
    upper = text.upper()

    data: Dict[str, Any] = {}

    m_ptres = re.search(r"PTRES\s*[:\-]?\s*(\d{4,6})", upper)
    if m_ptres:
        data["ptres"] = m_ptres.group(1)

    m_nd = re.search(r"\bND\s*[:\-]?\s*(\d{6})", upper)
    if m_nd:
        data["nd"] = m_nd.group(1)

    m_fonte = re.search(r"FONTE\s+DE\s+RECURSOS\s*[:\-]?\s*(\d{7,10})", upper)
    if m_fonte:
        data["fonte"] = m_fonte.group(1)

    m_esf = re.search(r"\bESF(?:ERA)?\s*[:\-]?\s*(\d+)", upper)
    if m_esf:
        data["esfera"] = m_esf.group(1)

    m_ugr = re.search(r"\bUGR\s*[:\-]?\s*(16\d{4})", upper)
    if m_ugr:
        data["ugr"] = m_ugr.group(1)

    logger.debug("Stage3: dados parciais extraídos do tópico 2 da requisição: %s", data)
    return data


def merge_nc_data(nc_data: Dict[str, Any], req_data: Dict[str, Any]) -> Tuple[Dict[str, Any], bool, List[str]]:
    """
    Mescla dados da NC (extração principal) com dados da requisição.
    - Dados da NC têm prioridade.
    - Campos nulos na NC podem ser preenchidos com dados da requisição.
    Retorna (dados_mesclados, complementado, campos_faltantes).
    """
    merged: Dict[str, Any] = dict(nc_data or {})
    complementado = False

    for key in ("numero_nc", "ug_emitente"):
        if not merged.get(key) and req_data.get(key):
            merged[key] = req_data[key]
            complementado = True

    destinos_raw = merged.get("destinos") or []
    destinos: List[Dict[str, Any]] = []
    for d in destinos_raw:
        if not isinstance(d, dict):
            continue
        dest = dict(d)
        for key in ("esfera", "ptres", "fonte", "nd", "ugr", "pi"):
            if (dest.get(key) is None or dest.get(key) == "") and req_data.get(key):
                dest[key] = req_data[key]
                complementado = True
        destinos.append(dest)
    merged["destinos"] = destinos

    # Valor total calculado, se não informado.
    if merged.get("valor_total") is None and destinos:
        total_dec = Decimal("0.00")
        for d in destinos:
            v = _safe_decimal(d.get("valor"))
            if v is not None:
                total_dec += v
        merged["valor_total"] = float(total_dec)

    campos_faltantes: List[str] = []
    topo_expected = ["numero_nc", "ug_emitente", "valor_total"]
    for key in topo_expected:
        if not merged.get(key):
            campos_faltantes.append(key)

    for idx, dest in enumerate(destinos):
        for key in ("esfera", "ptres", "fonte", "nd", "ugr", "pi", "valor"):
            if dest.get(key) in (None, "", []):
                campos_faltantes.append(f"destino[{idx}].{key}")

    return merged, complementado, campos_faltantes


def run(
    all_pages: Dict[str, str],
    req_pages: Optional[List[int]] = None,
    pdf_path: Optional[str] = None,
    image_pages: Optional[List[int]] = None,
    total_pages: int = 0,
) -> Dict[str, Any]:
    """
    Executa o Estágio 3 usando todas as páginas extraídas.

    Parâmetros:
        all_pages: mapa "pagina_n" -> texto bruto.
        req_pages: lista de páginas da peça da requisição (tópico 2), se conhecida.
        pdf_path: caminho do PDF (para converter páginas-imagem via Vision).
        image_pages: lista de números de página que são imagens (1-indexed).
        total_pages: total de páginas do PDF (para filtro de páginas-imagem).
    """
    if not all_pages:
        result = Stage3Result(status="error", ncs=[])
        return result.model_dump()

    req_pages_list = req_pages or []
    nc_groups = find_nc_pages(
        all_pages,
        image_pages=image_pages,
        pdf_path=pdf_path,
        total_pages=total_pages,
        req_pages=req_pages_list,
    )
    if not nc_groups:
        result = Stage3Result(status="error", ncs=[])
        return result.model_dump()

    req_data = extract_nc_from_requisition(all_pages, req_pages_list) if req_pages_list else {}

    ncs: List[Stage3NC] = []

    for group in nc_groups:
        group_pages: List[int] = group["pages"]
        fmt = group.get("format") or "unknown"
        nc_raw: Optional[Dict[str, Any]] = None

        if group.get("method") == "gemini_vision" and group.get("data"):
            nc_raw = group["data"]
            fmt = "image_siafi"
            print(
                "[Stage3] Usando NC extraída por Vision para páginas",
                group_pages,
            )
        else:
            texts = [
                (all_pages.get(f"pagina_{p}", "") or "")
                for p in group_pages
            ]
            nc_text = "\n".join(texts)
            fmt = detect_nc_format(nc_text)
            logger.debug(
                "Stage3: formato detectado para grupo de páginas %s: %s",
                group_pages,
                fmt,
            )
            print(
                "[Stage3] Formato detectado para grupo de páginas",
                group_pages,
                "=>",
                fmt,
            )
            print(
                "[Stage3] Trecho bruto da NC (primeiros 600 chars):",
                nc_text[:600],
            )
            if fmt in ("siafi_complete", "siafi_partial", "siafi"):
                nc_raw = extract_nc_siafi(nc_text)
            elif fmt in ("web_complete", "web_standard", "web"):
                nc_raw = extract_nc_web(nc_text)
            else:
                nc_raw = _extract_with_ai(nc_text)

        if not nc_raw:
            continue

        merged, complementado, campos_faltantes = merge_nc_data(nc_raw, req_data)
        numero_nc = merged.get("numero_nc")
        ug_emitente = merged.get("ug_emitente")

        destinos_raw = merged.get("destinos") or []
        destinos: List[Stage3Destination] = []
        for d in destinos_raw:
            if not isinstance(d, dict):
                continue
            destinos.append(
                Stage3Destination(
                    esfera=d.get("esfera"),
                    ptres=d.get("ptres"),
                    fonte=d.get("fonte"),
                    nd=d.get("nd"),
                    ugr=d.get("ugr"),
                    pi=d.get("pi"),
                    valor=float(_safe_decimal(d.get("valor")) or 0)
                    if d.get("valor") is not None
                    else None,
                    evento=str(d.get("evento")) if d.get("evento") is not None else None,
                )
            )

        valor_total_dec = _safe_decimal(merged.get("valor_total"))
        if valor_total_dec is None and destinos:
            valor_total_dec = sum(
                _safe_decimal(dest.valor) or Decimal("0.00") for dest in destinos
            )
        valor_total = float(
            valor_total_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ) if valor_total_dec is not None else None

        conf_raw = merged.get("confianca")
        try:
            conf_geral = int(conf_raw) if conf_raw is not None else 0
        except (TypeError, ValueError):
            conf_geral = 0

        # Heurística adicional de confiança se IA não fornecer valor.
        if conf_geral == 0:
            score = 50
            if numero_nc:
                score += 10
            if ug_emitente:
                score += 10
            if destinos:
                score += 10
            if not campos_faltantes:
                score += 10
            conf_geral = max(0, min(100, score))

        nc = Stage3NC(
            numero_nc=numero_nc,
            formato_detectado=fmt,
            ug_emitente=ug_emitente,
            valor_total=valor_total,
            destinos=destinos,
            campos_faltantes=campos_faltantes,
            complementado_pela_requisicao=complementado,
            confidence=Stage3NCConfidence(geral=conf_geral),
        )
        ncs.append(nc)

    if not ncs:
        status = "error"
    elif any(nc.campos_faltantes for nc in ncs):
        status = "partial"
    else:
        status = "success"

    result = Stage3Result(status=status, ncs=ncs)
    return result.model_dump()

