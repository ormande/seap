"""
Estágio 4 — Documentação (CADIN, TCU, SICAF).

Verificação automática de certidões e documentos de habilitação do fornecedor,
cruzamento de CNPJ com o extraído no Estágio 2, e busca por documentos
complementares via IA quando houver reprovação.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from ..ai_processor import GeminiProcessor
from ..models import Stage4Result

logger = logging.getLogger(__name__)

# --- Âncoras por tipo de documento ---
CADIN_ANCHORS = [
    r"Cadastro Informativo de Cr[eé]ditos",
    r"CADIN",
    r"Consulta Contratante",
]
TCU_ANCHORS = [
    r"Consulta Consolidada de Pessoa Jur[ií]dica",
    r"Tribunal de Contas",
    r"TCU",
    r"Resultados da Consulta Eletr[oô]nica",
]
SICAF_ANCHORS = [
    r"SICAF",
    r"Sistema de Cadastramento Unificado",
    r"Dados do Fornecedor",
    r"N[ií]veis cadastrados",
]

# --- Regex auxiliares ---
CNPJ_REGEX = re.compile(
    r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14}"
)
CNPJ_STRICT = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")


def _normalize_cnpj(cnpj: Optional[str]) -> str:
    """Retorna apenas dígitos do CNPJ para comparação."""
    if not cnpj:
        return ""
    return re.sub(r"\D", "", cnpj)


def find_documentation_pages(
    all_pages: Dict[str, str],
    used_pages: Optional[Dict[str, Set[int]]] = None,
) -> Dict[str, List[int]]:
    """
    Identifica páginas de CADIN, TCU e SICAF por âncoras.
    used_pages: dict opcional com chaves ex.: "requisition", "stage1" com sets de números.
    Retorna: {"cadin": [...], "tcu": [...], "sicaf": [...], "other": [...]}
    """
    if used_pages is None:
        used_pages = {}
    used_set: Set[int] = set()
    for pages in used_pages.values():
        used_set |= set(pages)

    cadin_pages: List[int] = []
    tcu_pages: List[int] = []
    sicaf_pages: List[int] = []
    other_pages: List[int] = []

    for key, text in all_pages.items():
        if not key.startswith("pagina_"):
            continue
        try:
            page_num = int(key.replace("pagina_", ""))
        except ValueError:
            continue

        t = (text or "").upper()
        is_cadin = any(re.search(a, text or "", re.IGNORECASE) for a in CADIN_ANCHORS)
        is_tcu = any(re.search(a, text or "", re.IGNORECASE) for a in TCU_ANCHORS)
        is_sicaf = any(re.search(a, text or "", re.IGNORECASE) for a in SICAF_ANCHORS)

        if is_cadin:
            cadin_pages.append(page_num)
        elif is_tcu:
            tcu_pages.append(page_num)
        elif is_sicaf:
            sicaf_pages.append(page_num)
        elif page_num not in used_set:
            other_pages.append(page_num)

    return {
        "cadin": sorted(cadin_pages),
        "tcu": sorted(tcu_pages),
        "sicaf": sorted(sicaf_pages),
        "other": sorted(other_pages),
    }


def extract_cadin(text: str) -> Dict[str, Any]:
    """
    Extração mecânica por regex do CADIN.
    Retorna: {cnpj, situacao, data_emissao, aprovado}.
    """
    result: Dict[str, Any] = {
        "cnpj": None,
        "situacao": None,
        "data_emissao": None,
        "aprovado": False,
    }
    if not text:
        return result

    # CNPJ próximo a "CPF / CNPJ:"
    m_cnpj = re.search(
        r"CPF\s*/\s*CNPJ\s*:\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})",
        text,
        re.IGNORECASE,
    )
    if m_cnpj:
        result["cnpj"] = m_cnpj.group(1)
    else:
        first_cnpj = CNPJ_STRICT.search(text)
        if first_cnpj:
            result["cnpj"] = first_cnpj.group(0)

    # Situação para a Esfera Federal
    m_sit = re.search(
        r"Situa[çc][aã]o\s+para\s+a\s+Esfera\s+Federal\s*:\s*(\w+)",
        text,
        re.IGNORECASE,
    )
    if m_sit:
        result["situacao"] = m_sit.group(1).strip().upper()

    # Data de emissão
    m_data = re.search(r"Emiss[aã]o\s+em\s+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    if m_data:
        result["data_emissao"] = m_data.group(1)

    result["aprovado"] = (result.get("situacao") or "").strip() == "REGULAR"
    return result


def extract_tcu(text: str) -> Dict[str, Any]:
    """
    Extração mecânica dos 4 blocos TCU.
    Retorna: {cnpj, data_consulta, verificacoes: [{cadastro, orgao, resultado, aprovado}], aprovado}.
    """
    result: Dict[str, Any] = {
        "cnpj": None,
        "data_consulta": None,
        "verificacoes": [],
        "aprovado": False,
    }
    if not text:
        return result

    first_cnpj = CNPJ_STRICT.search(text)
    if first_cnpj:
        result["cnpj"] = first_cnpj.group(0)

    m_data = re.search(
        r"Consulta\s+realizada\s+em\s*:\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE
    )
    if m_data:
        result["data_consulta"] = m_data.group(1)
    if not result["data_consulta"]:
        m_data = re.search(
            r"Data\s+(?:da\s+)?consulta\s*[:\s]+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE
        )
        if m_data:
            result["data_consulta"] = m_data.group(1)

    # Blocos: Órgão Gestor / Cadastro / Resultado da consulta
    block_re = re.compile(
        r"[ÓO]rg[aã]o\s+Gestor\s*:\s*(.+?)\n.*?Cadastro\s*:\s*(.+?)\n.*?Resultado\s+(?:da\s+)?consulta\s*:\s*(\S.*?)(?=\n\n|\n[ÓO]rg|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    for m in block_re.finditer(text):
        orgao = m.group(1).strip()[:80]
        cadastro = m.group(2).strip()[:120]
        resultado = m.group(3).strip().split("\n")[0].strip()[:60]
        nada_consta = "nada consta" in resultado.lower()
        result["verificacoes"].append({
            "cadastro": cadastro,
            "orgao": orgao,
            "resultado": resultado,
            "aprovado": nada_consta,
        })

    # Se não encontrou blocos, tentar linhas simples
    if not result["verificacoes"]:
        alt = re.findall(
            r"Resultado\s+(?:da\s+)?consulta\s*:\s*([^\n]+)",
            text,
            re.IGNORECASE,
        )
        for r in alt[:4]:
            r = r.strip()[:60]
            result["verificacoes"].append({
                "cadastro": "",
                "orgao": "",
                "resultado": r,
                "aprovado": "nada consta" in r.lower(),
            })

    result["aprovado"] = (
        len(result["verificacoes"]) >= 4
        and all(v.get("aprovado") for v in result["verificacoes"])
    )
    return result


def _parse_date_br(s: Optional[str]) -> Optional[datetime]:
    """Converte DD/MM/YYYY para datetime."""
    if not s or not re.match(r"\d{2}/\d{2}/\d{4}", s):
        return None
    try:
        return datetime.strptime(s, "%d/%m/%Y")
    except ValueError:
        return None


def extract_sicaf(text: str, analysis_date: str) -> Dict[str, Any]:
    """
    Extração mecânica do SICAF e comparação de validades com analysis_date (DD/MM/YYYY).
    Retorna: {cnpj, razao_social, situacao, data_emissao, niveis, ocorrencias, itens_vencidos, aprovado}.
    """
    result: Dict[str, Any] = {
        "cnpj": None,
        "razao_social": None,
        "situacao_fornecedor": None,
        "data_emissao": None,
        "niveis": [],
        "ocorrencias": {},
        "itens_vencidos": [],
        "aprovado": True,
    }
    if not text:
        result["aprovado"] = False
        return result

    m_cnpj = re.search(r"CNPJ\s*:\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", text, re.IGNORECASE)
    if m_cnpj:
        result["cnpj"] = m_cnpj.group(1)
    else:
        first = CNPJ_STRICT.search(text)
        if first:
            result["cnpj"] = first.group(0)

    m_razao = re.search(r"Raz[aã]o\s+Social\s*[:\s]+([^\n]+)", text, re.IGNORECASE)
    if m_razao:
        result["razao_social"] = m_razao.group(1).strip()[:200]

    m_sit = re.search(
        r"Situa[çc][aã]o\s+do\s+Fornecedor\s*:\s*(\S+)",
        text,
        re.IGNORECASE,
    )
    if m_sit:
        result["situacao_fornecedor"] = m_sit.group(1).strip()[:60]
    if (result.get("situacao_fornecedor") or "").upper() != "CREDENCIADO":
        result["aprovado"] = False
        result.setdefault("itens_vencidos", []).append("Situação do fornecedor não é Credenciado")

    # Rodapé do SICAF: "Emitido em: 09/02/2026 15:50" — capturar só a data
    m_emissao = re.search(r"Emitido\s+em\s*:\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    if m_emissao:
        result["data_emissao"] = m_emissao.group(1)
    if not result["data_emissao"]:
        m_emissao = re.search(
            r"Emiss[aã]o\s*[:\s]+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE
        )
        if m_emissao:
            result["data_emissao"] = m_emissao.group(1)

    # Níveis SICAF: exatamente 6, cada um com a primeira validade que aparece após o nome
    SICAF_NIVEIS_ORDEM = [
        "Receita Federal e PGFN",
        "FGTS",
        "Trabalhista",
        "Receita Estadual/Distrital",
        "Receita Municipal",
        "Qualificação Econômico-Financeira",
    ]
    analysis_dt = _parse_date_br(analysis_date)
    for nivel_nome in SICAF_NIVEIS_ORDEM:
        pattern = (
            re.escape(nivel_nome)
            + r".*?Validade\s*:\s*(\d{2}/\d{2}/\d{4})"
        )
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if m:
            val_str = m.group(1)
            val_dt = _parse_date_br(val_str)
            vencido = analysis_dt and val_dt and val_dt < analysis_dt
            result["niveis"].append({
                "nivel": nivel_nome,
                "validade": val_str,
                "vencido": vencido,
                "tipo": "Manual",
            })
            if vencido:
                result["aprovado"] = False
                result["itens_vencidos"].append(
                    f"{nivel_nome} vencida em {val_str}"
                )
    result["motivos_reprovacao"] = result.get("itens_vencidos", [])[:]

    # Ocorrências: extrair valor após cada rótulo; "Nada Consta" = aprovado,
    # outro texto = reprovado, não encontrado/vazio = "Não identificado" (amarelo)
    OCORRENCIAS_LABELS: Dict[str, str] = {
        "ocorrencia": "Ocorrência",
        "impedimento_licitar": "Impedimento de Licitar",
        "vinculo_servico_publico": "Vínculo com Serviço Público",
        "ocorrencias_impeditivas": "Ocorrências Impeditivas Indiretas",
    }
    occ_patterns = [
        (r"Ocorr[eê]ncia\s*:\s*(Nada Consta|.+?)(?:\n|$)", "ocorrencia"),
        (r"Impedimento\s+de\s+Licitar\s*:\s*(Nada Consta|.+?)(?:\n|$)", "impedimento_licitar"),
        (r"V[ií]nculo.*?Servi[çc]o\s+P[uú]blico.*?:\s*(Nada Consta|.+?)(?:\n|$)", "vinculo_servico_publico"),
        (r"Ocorr[eê]ncias\s+Impeditivas.*?:\s*(Nada Consta|.+?)(?:\n|$)", "ocorrencias_impeditivas"),
    ]
    for pattern, key in occ_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()[:80]
        else:
            val = "Não identificado"
        if not val or val == "—":
            val = "Não identificado"
        result["ocorrencias"][key] = val
        # Só reprova se valor não for "Nada Consta" e não for "Não identificado"
        if val != "Não identificado" and "nada consta" not in val.lower():
            result["aprovado"] = False
            result["itens_vencidos"].append(
                f"{OCORRENCIAS_LABELS.get(key, key)}: {val}"
            )

    return result


def cross_check_cnpj(
    stage2_cnpj: Optional[str],
    cadin_cnpj: Optional[str],
    tcu_cnpj: Optional[str],
    sicaf_cnpj: Optional[str],
) -> Dict[str, Any]:
    """
    Compara todos os CNPJs com o do Estágio 2.
    Retorna: {consistente: bool, cnpj_referencia: str, divergencias: [{doc, cnpj_doc, esperado}]}.
    """
    ref = _normalize_cnpj(stage2_cnpj)
    result: Dict[str, Any] = {
        "cnpj_referencia": stage2_cnpj or "",
        "consistente": True,
        "divergencias": [],
    }
    if not ref:
        return result

    for doc_name, cnpj in [
        ("CADIN", cadin_cnpj),
        ("TCU", tcu_cnpj),
        ("SICAF", sicaf_cnpj),
    ]:
        if not cnpj:
            continue
        doc_digits = _normalize_cnpj(cnpj)
        if doc_digits and doc_digits != ref:
            result["consistente"] = False
            result["divergencias"].append({
                "doc": doc_name,
                "cnpj_doc": cnpj,
                "esperado": stage2_cnpj or "",
            })
    return result


STAGE4_COMPLEMENTARY_PROMPT = """Você é um especialista em documentos de licitação do governo brasileiro.

As seguintes irregularidades foram encontradas no processo:
{lista_irregularidades}

O CNPJ do fornecedor é: {cnpj}

Analise os textos abaixo (páginas diversas do processo) e identifique se há algum documento que COMPROVE A REGULARIDADE do fornecedor para as irregularidades listadas.

Documentos que podem comprovar regularidade:
- Certidão de regularidade fiscal (receita federal, estadual, municipal)
- Certidão negativa de débitos (prefeitura, estado)
- Certidão de regularidade trabalhista
- Certidão de regularidade do FGTS
- Qualquer certidão ou declaração de órgão público

Para cada irregularidade, responda:
{{
  "irregularidades": [
    {{
      "descricao": "ex: SICAF - Receita Municipal vencida em 09/03/2026",
      "documento_encontrado": true/false,
      "documento_descricao": "descrição do documento encontrado ou vazio",
      "pagina": número da página ou null,
      "anula_reprovacao": true/false,
      "confianca": 0-100
    }}
  ]
}}

Se não encontrar documentos complementares, retorne documento_encontrado: false.
Retorne APENAS JSON válido."""


def search_complementary_docs(
    all_pages: Dict[str, str],
    other_pages: List[int],
    irregularities: List[str],
    cnpj: str,
) -> List[Dict[str, Any]]:
    """
    Envia páginas não classificadas ao Gemini para buscar documentos que anulem reprovações.
    Só deve ser chamado quando houver irregularidades.
    """
    if not irregularities or not other_pages:
        return []
    try:
        proc = GeminiProcessor()
    except ValueError:
        logger.warning("Gemini indisponível para busca de documentos complementares.")
        return []

    lista_irr = "\n".join(f"- {i}" for i in irregularities)
    prompt = STAGE4_COMPLEMENTARY_PROMPT.format(
        lista_irregularidades=lista_irr,
        cnpj=cnpj or "não informado",
    )
    texts: List[str] = []
    for p in other_pages[:15]:  # Limitar páginas para não estourar contexto
        key = f"pagina_{p}"
        texts.append(f"--- Página {p} ---\n{(all_pages.get(key) or '')[:4000]}")
    prompt += "\n\nTextos das páginas:\n\n" + "\n\n".join(texts)

    try:
        result, _, _ = proc._generate(prompt, "stage4_complementary")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao buscar documentos complementares: %s", exc)
        return []

    irr_list = result.get("irregularidades") or []
    return [i for i in irr_list if isinstance(i, dict)]


def run(
    all_pages: Dict[str, str],
    stage2_data: Optional[Dict[str, Any]] = None,
    used_pages: Optional[Dict[str, Set[int]]] = None,
    analysis_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Orquestra o Estágio 4: identifica páginas de CADIN/TCU/SICAF, extrai,
    cruza CNPJ e opcionalmente busca documentos complementares.
    """
    if analysis_date is None:
        analysis_date = datetime.now().strftime("%d/%m/%Y")

    stage2_data = stage2_data or {}
    cnpj_ref = (stage2_data.get("data") or {}).get("cnpj") if isinstance(stage2_data.get("data"), dict) else (stage2_data.get("cnpj") if isinstance(stage2_data, dict) else None)
    if not cnpj_ref and isinstance(stage2_data, dict) and "data" in stage2_data:
        cnpj_ref = (stage2_data["data"] or {}).get("cnpj")

    doc_pages = find_documentation_pages(all_pages, used_pages)
    cadin_data: Optional[Dict[str, Any]] = None
    tcu_data: Optional[Dict[str, Any]] = None
    sicaf_data: Optional[Dict[str, Any]] = None

    if doc_pages["cadin"]:
        text = " ".join(
            (all_pages.get(f"pagina_{p}") or "") for p in doc_pages["cadin"]
        )
        cadin_data = extract_cadin(text)
        cadin_data["encontrado"] = True
    else:
        cadin_data = {"encontrado": False, "aprovado": False}

    if doc_pages["tcu"]:
        text = " ".join(
            (all_pages.get(f"pagina_{p}") or "") for p in doc_pages["tcu"]
        )
        tcu_data = extract_tcu(text)
        tcu_data["encontrado"] = True
    else:
        tcu_data = {"encontrado": False, "aprovado": False}

    if doc_pages["sicaf"]:
        # Usar o SICAF mais recente (última página listada = costuma ser a mais recente)
        text = " ".join(
            (all_pages.get(f"pagina_{p}") or "") for p in doc_pages["sicaf"]
        )
        sicaf_data = extract_sicaf(text, analysis_date)
        sicaf_data["encontrado"] = True
    else:
        sicaf_data = {"encontrado": False, "aprovado": False}

    cnpj_cruzamento = cross_check_cnpj(
        cnpj_ref,
        cadin_data.get("cnpj") if cadin_data else None,
        tcu_data.get("cnpj") if tcu_data else None,
        sicaf_data.get("cnpj") if sicaf_data else None,
    )

    irregularities: List[str] = []
    if not cnpj_cruzamento.get("consistente"):
        for d in cnpj_cruzamento.get("divergencias") or []:
            irregularities.append(
                f"CNPJ divergente: {d.get('doc')} possui {d.get('cnpj_doc')}, esperado {d.get('esperado')}"
            )
    if cadin_data and not cadin_data.get("aprovado") and cadin_data.get("encontrado"):
        irregularities.append(f"CADIN: situação {cadin_data.get('situacao', '?')} (não REGULAR)")
    if tcu_data and not tcu_data.get("aprovado") and tcu_data.get("encontrado"):
        irregularities.append("TCU: algum cadastro não está Nada Consta")
    if sicaf_data and not sicaf_data.get("aprovado") and sicaf_data.get("encontrado"):
        for mot in sicaf_data.get("motivos_reprovacao") or sicaf_data.get("itens_vencidos") or []:
            irregularities.append(f"SICAF: {mot}")

    complementares: List[Dict[str, Any]] = []
    if irregularities:
        complementares = search_complementary_docs(
            all_pages,
            doc_pages["other"],
            irregularities,
            cnpj_ref or "",
        )

    # Veredicto
    all_ok = (
        cnpj_cruzamento.get("consistente", True)
        and (cadin_data or {}).get("aprovado", True)
        and (tcu_data or {}).get("aprovado", True)
        and (sicaf_data or {}).get("aprovado", True)
    )
    if all_ok:
        status = "approved"
    elif complementares and any(c.get("anula_reprovacao") for c in complementares):
        status = "partial"  # aprovado com ressalva
    else:
        status = "rejected"

    confidence_geral = 85
    if not cadin_data or not cadin_data.get("encontrado"):
        confidence_geral -= 10
    if not tcu_data or not tcu_data.get("encontrado"):
        confidence_geral -= 10
    if not sicaf_data or not sicaf_data.get("encontrado"):
        confidence_geral -= 10
    confidence_geral = max(0, min(100, confidence_geral))

    result = Stage4Result(
        status=status,
        cadin=cadin_data or {},
        tcu=tcu_data or {},
        sicaf=sicaf_data or {},
        cnpj_cruzamento=cnpj_cruzamento,
        complementares=complementares,
        confidence={"geral": confidence_geral},
    )
    return result.model_dump()
