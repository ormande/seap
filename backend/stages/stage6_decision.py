"""
Estágio 6 — Decisão Final.

Responsável por:
- Cruzar os resultados dos estágios 1–5.
- Identificar reprovações, ressalvas e pendências informativas.
- Gerar (opcionalmente) um despacho formal sugerido via IA (Gemini).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..ai_processor import GeminiProcessor
from ..models import (
    Stage1Result,
    Stage2Result,
    Stage3Result,
    Stage4Result,
    Stage5Result,
    Stage6Issue,
    Stage6Result,
)

logger = logging.getLogger(__name__)


def _format_brl(value: Optional[float]) -> str:
    """Formata número em reais no padrão brasileiro (R$ X.XXX,YY)."""
    if value is None:
        return "-"
    try:
        s = f"{value:,.2f}"
    except Exception:  # noqa: BLE001
        return "-"
    # "1,234.56" -> "1.234,56"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def collect_issues(
    stage1: Optional[Stage1Result],
    stage2: Optional[Stage2Result],
    stage3: Optional[Stage3Result],
    stage4: Optional[Stage4Result],
    stage5: Optional[Stage5Result],
) -> Dict[str, Any]:
    """
    Percorre resultados de todos os estágios e coleta:
    - reprovacoes: lista de problemas graves.
    - ressalvas: lista de problemas menores.
    - pendencias_despachos: pendências do Estágio 5 (informativas).
    - pontos_positivos: aspectos que estão OK.
    """
    reprovacoes: List[Stage6Issue] = []
    ressalvas: List[Stage6Issue] = []
    pendencias_despachos: List[Stage6Issue] = []
    pontos_positivos: List[str] = []

    # --- Estágio 2: cálculos e campos principais ---
    if stage2 and stage2.data:
        data2 = stage2.data
        conf2 = stage2.confidence

        # Cálculos divergentes → ressalva.
        vc = data2.verificacao_calculos
        if vc and not vc.correto and vc.divergencias:
            for d in vc.divergencias:
                if d.tipo == "total":
                    desc = "Divergência no valor total da requisição."
                    detalhes = (
                        f"Valor informado: R$ {_format_brl(d.encontrado)}; "
                        f"Valor calculado: R$ {_format_brl(d.esperado)}."
                    )
                else:
                    desc = f"Divergência de cálculo no item {d.item or '?'}."
                    detalhes = (
                        f"Esperado: R$ {_format_brl(d.esperado)}; "
                        f"Encontrado: R$ {_format_brl(d.encontrado)}."
                    )
                ressalvas.append(
                    Stage6Issue(
                        estagio=2,
                        tipo="ressalva",
                        descricao=desc,
                        detalhes=detalhes,
                    )
                )
        elif vc and vc.correto:
            pontos_positivos.append("Cálculos da tabela de itens conferem com os valores informados.")

        # Campos não identificados (instrumento, UASG) com confiança baixa (< 70) → ressalva.
        if conf2:
            if (not data2.instrumento) or conf2.instrumento < 70:
                ressalvas.append(
                    Stage6Issue(
                        estagio=2,
                        tipo="ressalva",
                        descricao="Instrumento da contratação com baixa confiança ou não identificado.",
                        detalhes=f"Confiança do instrumento: {conf2.instrumento}%",
                    )
                )
            if (not data2.uasg) or conf2.uasg < 70:
                ressalvas.append(
                    Stage6Issue(
                        estagio=2,
                        tipo="ressalva",
                        descricao="UASG/UG gerenciadora com baixa confiança ou não identificada.",
                        detalhes=f"Confiança da UASG: {conf2.uasg}%",
                    )
                )

    # --- Estágio 3: Notas de Crédito ---
    if stage3:
        ncs = stage3.ncs or []
        if not ncs:
            # NC pode não existir, mas registrar como ressalva leve.
            ressalvas.append(
                Stage6Issue(
                    estagio=3,
                    tipo="ressalva",
                    descricao="Nenhuma Nota de Crédito foi identificada.",
                    detalhes="O processo pode não exigir NC, mas recomenda-se verificar a compatibilidade orçamentária.",
                )
            )
        else:
            # Valor da NC < valor da requisição → ressalva.
            total_nc = 0.0
            for nc in ncs:
                if nc.valor_total is not None:
                    total_nc += float(nc.valor_total)
            if stage2 and stage2.data and stage2.data.valor_total is not None:
                valor_req = float(stage2.data.valor_total)
                if total_nc + 0.01 < valor_req:  # margem pequena
                    detalhes = (
                        f"Valor total das NCs: R$ {_format_brl(total_nc)}; "
                        f"Valor da requisição: R$ {_format_brl(valor_req)}."
                    )
                    ressalvas.append(
                        Stage6Issue(
                            estagio=3,
                            tipo="ressalva",
                            descricao="Somatório das Notas de Crédito inferior ao valor da requisição.",
                            detalhes=detalhes,
                        )
                    )
                else:
                    pontos_positivos.append("Notas de Crédito compatíveis com o valor total da requisição.")

    # --- Estágio 4: Documentação (CADIN, TCU, SICAF, CNPJ) ---
    if stage4:
        cadin = stage4.cadin or {}
        tcu = stage4.tcu or {}
        sicaf = stage4.sicaf or {}
        cnpj_cruz = stage4.cnpj_cruzamento or {}
        complementares = stage4.complementares or []

        # CADIN ≠ REGULAR → reprovação.
        if cadin.get("encontrado") and not cadin.get("aprovado"):
            situacao = cadin.get("situacao") or "Situação não REGULAR"
            reprovacoes.append(
                Stage6Issue(
                    estagio=4,
                    tipo="reprovacao",
                    descricao="CADIN em situação irregular.",
                    detalhes=f"Situação CADIN: {situacao}.",
                )
            )

        # TCU com constatação → reprovação.
        if tcu.get("encontrado") and not tcu.get("aprovado"):
            reprovacoes.append(
                Stage6Issue(
                    estagio=4,
                    tipo="reprovacao",
                    descricao="Consulta TCU com constatações impeditivas.",
                    detalhes="Algum cadastro do TCU não retornou 'Nada Consta'.",
                )
            )

        # SICAF vencido / irregular.
        sicaf_encontrado = bool(sicaf.get("encontrado"))
        sicaf_aprovado = bool(sicaf.get("aprovado"))
        if sicaf_encontrado and not sicaf_aprovado:
            # Verifica se há documento complementar que anula a reprovação.
            has_complement = any(c.get("anula_reprovacao") for c in complementares or [])
            if has_complement:
                ressalvas.append(
                    Stage6Issue(
                        estagio=4,
                        tipo="ressalva",
                        descricao="SICAF com pendência sanada por documento complementar.",
                        detalhes="Há documento complementar que comprova a regularidade, mas o SICAF principal está vencido/irregular.",
                    )
                )
            else:
                motivos = sicaf.get("motivos_reprovacao") or sicaf.get("itens_vencidos") or []
                detalhes = "; ".join(str(m) for m in motivos) if motivos else "Pendências de regularidade no SICAF."
                reprovacoes.append(
                    Stage6Issue(
                        estagio=4,
                        tipo="reprovacao",
                        descricao="SICAF em situação irregular/vencida sem comprovação complementar.",
                        detalhes=detalhes,
                    )
                )
        elif sicaf_encontrado and sicaf_aprovado:
            pontos_positivos.append("SICAF regular.")

        # CNPJ divergente → reprovação.
        if not cnpj_cruz.get("consistente", True):
            divergencias = cnpj_cruz.get("divergencias") or []
            detalhes = "; ".join(
                f"{d.get('doc')}: {d.get('cnpj_doc')} (esperado {d.get('esperado')})"
                for d in divergencias
                if isinstance(d, dict)
            )
            reprovacoes.append(
                Stage6Issue(
                    estagio=4,
                    tipo="reprovacao",
                    descricao="Divergência de CNPJ entre documentos.",
                    detalhes=detalhes or "CNPJ divergente entre CADIN, TCU, SICAF e a requisição.",
                )
            )
        elif cnpj_cruz:
            pontos_positivos.append("CNPJ consistente em todos os documentos de habilitação.")

    # --- Estágio 5: Pendências de despachos (não reprovam) ---
    if stage5:
        for pend in stage5.exigencias_pendentes or []:
            pendencias_despachos.append(
                Stage6Issue(
                    estagio=5,
                    tipo="pendencia_despacho",
                    descricao=pend.descricao,
                    detalhes=f"Origem: Despacho {pend.despacho_origem}.",
                )
            )

    # --- Confiança baixa em campos extraídos (< 70%) → ressalvas gerais ---
    if stage1 and stage1.confidence and stage1.confidence.geral < 70:
        ressalvas.append(
            Stage6Issue(
                estagio=1,
                tipo="ressalva",
                descricao="Confiança baixa na identificação do processo (Estágio 1).",
                detalhes=f"Confiança geral: {stage1.confidence.geral}%.",
            )
        )
    if stage2 and stage2.confidence and stage2.confidence.geral < 70:
        ressalvas.append(
            Stage6Issue(
                estagio=2,
                tipo="ressalva",
                descricao="Confiança baixa na análise da peça da requisição.",
                detalhes=f"Confiança geral: {stage2.confidence.geral}%.",
            )
        )

    return {
        "reprovacoes": reprovacoes,
        "ressalvas": ressalvas,
        "pendencias_despachos": pendencias_despachos,
        "pontos_positivos": pontos_positivos,
    }


def determine_verdict(issues: Dict[str, Any]) -> str:
    """
    Determina o veredicto final a partir das listas de problemas.
    - Se há reprovacoes → "reprovado"
    - Senão, se há ressalvas → "aprovado_com_ressalva"
    - Senão → "aprovado"
    """
    reprovacoes = issues.get("reprovacoes") or []
    ressalvas = issues.get("ressalvas") or []

    if reprovacoes:
        return "reprovado"
    if ressalvas:
        return "aprovado_com_ressalva"
    return "aprovado"


STAGE6_DISPATCH_PROMPT = """Você é um analista de processos licitatórios 
do Exército Brasileiro. Gere um despacho formal baseado na análise abaixo.

VEREDICTO: {verdict}

PROBLEMAS ENCONTRADOS:
{lista_problemas}

RESSALVAS:
{lista_ressalvas}

REGRAS DO DESPACHO:
- SEMPRE começar com "Informo que"
- NÃO citar NUP, número da requisição, nome da OM, nome do fornecedor ou CNPJ
  no corpo do despacho (essas informações já constam em outras peças do processo)
- Datas no formato militar: DD MES AA (ex: 16 FEV 26)
  Meses abreviados: JAN, FEV, MAR, ABR, MAI, JUN, JUL, AGO, SET, OUT, NOV, DEZ
- Tom formal, direto, objetivo
- Ser EXTREMAMENTE objetivo e curto, focando APENAS no problema e na consequência
- Citar valores e datas específicos quando necessário
- Máximo de 4 a 5 linhas de texto, mesmo com múltiplos problemas
- Se APROVADO: "Informo que após análise formal e legal, o processo 
  encontra-se apto para prosseguimento."
- Se APROVADO COM RESSALVA: descrever o problema e indicar que o 
  processo pode seguir apesar dele
- Se REPROVADO com 1 problema: descrever e finalizar com 
  "o que impede o andamento do processo"
- Se REPROVADO com múltiplos problemas: usar alíneas (a, b, c) e 
  finalizar com "Solicito a regularização das pendências para 
  prosseguimento"
- NÃO incluir cabeçalho, número de despacho ou assinatura
- NÃO colocar o texto inteiro entre aspas ou crases
- Retornar APENAS o texto do despacho, sem JSON, sem aspas ao redor e 
  sem markdown"""


def generate_dispatch(
    verdict: str,
    issues: Dict[str, Any],
    stages_data: Dict[str, Any],
) -> str:
    """
    Usa Gemini para gerar o texto do despacho conforme o veredicto.

    REGRA CRÍTICA: se veredicto = "aprovado", NÃO chama Gemini e retorna string vazia.
    """
    if verdict == "aprovado":
        # Nenhum despacho é necessário em caso de aprovação integral.
        return ""

    stage1: Optional[Stage1Result] = stages_data.get("stage1")
    stage2: Optional[Stage2Result] = stages_data.get("stage2")

    # Dados principais do processo para o prompt.
    nup = stage1.data.nup if stage1 and stage1.data else ""
    req_str = ""
    if stage1 and stage1.data and stage1.data.requisicao:
        r = stage1.data.requisicao
        if r.numero and r.ano:
            req_str = f"{r.numero}/{r.ano}"
        elif r.texto_original:
            req_str = r.texto_original
    om = stage1.data.om.nome if stage1 and stage1.data and stage1.data.om else ""

    instrumento = ""
    fornecedor = ""
    valor_str = "-"
    if stage2 and stage2.data:
        d2 = stage2.data
        if d2.instrumento:
            if d2.instrumento.tipo and d2.instrumento.numero:
                instrumento = f"{d2.instrumento.tipo} nº {d2.instrumento.numero}"
            else:
                instrumento = (d2.instrumento.tipo or "") or (d2.instrumento.numero or "")
        fornecedor = d2.fornecedor or ""
        valor_str = _format_brl(d2.valor_total)

    # Monta listas de problemas e ressalvas em texto.
    problemas_texto_parts: List[str] = []
    for issue in issues.get("reprovacoes") or []:
        problemas_texto_parts.append(f"- [Estágio {issue.estagio}] {issue.descricao} {issue.detalhes or ''}".strip())
    lista_problemas = "\n".join(problemas_texto_parts) or "Nenhum problema impeditivo identificado."

    ressalvas_texto_parts: List[str] = []
    for issue in issues.get("ressalvas") or []:
        ressalvas_texto_parts.append(f"- [Estágio {issue.estagio}] {issue.descricao} {issue.detalhes or ''}".strip())
    lista_ressalvas = "\n".join(ressalvas_texto_parts) or "Nenhuma ressalva relevante identificada."

    prompt = STAGE6_DISPATCH_PROMPT.format(
        verdict=verdict.upper(),
        nup=nup or "não identificado",
        requisicao=req_str or "não identificada",
        om=om or "não identificada",
        instrumento=instrumento or "não identificado",
        fornecedor=fornecedor or "não identificado",
        valor=valor_str,
        lista_problemas=lista_problemas,
        lista_ressalvas=lista_ressalvas,
    )

    try:
        proc = GeminiProcessor()
    except ValueError as exc:
        logger.warning("Gemini indisponível para geração do despacho (estágio 6): %s", exc)
        return ""

    try:
        # Aqui esperamos texto puro, não JSON, então chamamos o modelo diretamente.
        response = proc._model.generate_content(  # type: ignore[attr-defined]
            prompt
        )
        text = (getattr(response, "text", None) or "").strip()

        # Remove possíveis blocos ```markdown``` que o modelo possa ter incluído.
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Limpeza adicional: remover aspas ou crases no início/fim, se existirem.
        text = text.strip()
        # Remove crases simples em volta
        if text.startswith("`") and text.endswith("`") and len(text) > 1:
            text = text[1:-1].strip()
        # Remove aspas duplas em volta
        if text.startswith('"') and text.endswith('"') and len(text) > 1:
            text = text[1:-1].strip()
        # Remove aspas simples em volta
        if text.startswith("'") and text.endswith("'") and len(text) > 1:
            text = text[1:-1].strip()
        # Limpa crases residuais nas extremidades
        text = text.strip("`").strip()

        return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao gerar despacho no estágio 6 com IA: %s", exc)
        return ""


def run(all_stages: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o Estágio 6:
    - Coleta issues dos estágios 1–5.
    - Determina veredicto.
    - Opcionalmente gera um despacho sugerido.
    """
    stage1: Optional[Stage1Result] = all_stages.get("stage1")
    stage2: Optional[Stage2Result] = all_stages.get("stage2")
    stage3: Optional[Stage3Result] = all_stages.get("stage3")
    stage4: Optional[Stage4Result] = all_stages.get("stage4")
    stage5: Optional[Stage5Result] = all_stages.get("stage5")

    issues = collect_issues(stage1, stage2, stage3, stage4, stage5)
    verdict = determine_verdict(issues)

    # Despacho só é gerado para aprovado_com_ressalva ou reprovado.
    despacho_text = generate_dispatch(verdict, issues, all_stages)

    # Converte listas de Stage6Issue para dicts.
    reprovacoes_dicts = [i.model_dump() for i in issues["reprovacoes"]]
    ressalvas_dicts = [i.model_dump() for i in issues["ressalvas"]]
    pendencias_dicts = [i.model_dump() for i in issues["pendencias_despachos"]]

    # Heurística simples de confiança geral.
    if verdict == "aprovado":
        conf_geral = 95
    elif verdict == "aprovado_com_ressalva":
        conf_geral = 90
    else:
        conf_geral = 88

    status_map = {
        "aprovado": "aprovado",
        "aprovado_com_ressalva": "aprovado_com_ressalva",
        "reprovado": "reprovado",
    }
    status = status_map.get(verdict, verdict)
    veredicto_legivel = {
        "aprovado": "Aprovado",
        "aprovado_com_ressalva": "Aprovado com Ressalva",
        "reprovado": "Reprovado",
    }.get(verdict, verdict)

    result = Stage6Result(
        status=status,
        veredicto=veredicto_legivel,
        problemas=reprovacoes_dicts + ressalvas_dicts + pendencias_dicts,
        reprovacoes=reprovacoes_dicts,
        ressalvas=ressalvas_dicts,
        pendencias_despachos=pendencias_dicts,
        despacho=despacho_text,
        confidence={"geral": conf_geral},
    )
    return result.model_dump()

