"""
Cruzamento ND × Itens — Estágio 3 complementar.

Responsável por verificar se a Natureza da Despesa (ND) utilizada na
Nota de Crédito (NC) é compatível com os itens da requisição
classificados no Estágio 2.

Fluxo:
- Usa uma classificação rápida por palavras‑chave (sem IA) para itens óbvios;
- Quando necessário, chama Gemini para uma classificação detalhada;
- Retorna estrutura própria (Stage3NDCrosscheck) anexada ao resultado do
  Estágio 3.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

import logging

try:
    from ..ai_processor import GeminiProcessor
except ImportError:  # pragma: no cover - fallback para execução local
    from ai_processor import GeminiProcessor

try:
    from ..models import (
        Stage2Item,
        Stage3Destination,
        Stage3NDCrossItem,
        Stage3NDCrosscheck,
    )
except ImportError:  # pragma: no cover
    from models import (
        Stage2Item,
        Stage3Destination,
        Stage3NDCrossItem,
        Stage3NDCrosscheck,
    )

try:
    from ..nd_database import ND_ELEMENTS
except ImportError:  # pragma: no cover
    from nd_database import ND_ELEMENTS


logger = logging.getLogger(__name__)


def get_element(nd: Optional[str]) -> Optional[str]:
    """
    Extrai o elemento (2 dígitos) a partir de uma ND.

    Regras:
    - Formato 6 dígitos (ex.: 339039) → últimos 2 dígitos ("39");
    - Formato EE.SS (ex.: 30.24) → primeiros 2 dígitos ("30");
    - Outros formatos → melhor esforço (2 últimos dígitos).
    """
    if not nd:
        return None

    s = str(nd).strip()
    if not s:
        return None

    # Formato EE.SS (normalização do estágio 2)
    if "." in s:
        parts = s.split(".")
        if len(parts[0]) == 2 and parts[0].isdigit():
            return parts[0]

    nd_clean = s.replace(".", "").replace("/", "")
    if len(nd_clean) >= 6 and nd_clean.isdigit():
        return nd_clean[4:6]
    if len(nd_clean) >= 2:
        return nd_clean[-2:]
    return nd_clean or None


def quick_classify(descricao: str) -> str:
    """
    Classificação rápida por palavras‑chave, sem IA.

    Retorna:
    - "39" para serviços de terceiros PJ;
    - "52" para equipamentos permanentes;
    - "30" como padrão (material de consumo).
    """
    desc_lower = (descricao or "").lower()

    service_words = [
        "manutenção",
        "instalação",
        "reparo",
        "serviço",
        "conservação",
        "limpeza",
        "vigilância",
        "locação",
        "consultoria",
        "treinamento",
        "preventiva",
        "corretiva",
        "remanejamento",
    ]

    equipment_words = [
        "equipamento",
        "aparelho",
        "máquina",
        "maquina",
        "veículo",
        "veiculo",
        "computador",
        "impressora",
        "monitor",
        "notebook",
        "servidor",
        "mobiliário",
        "cadeira",
        "mesa",
    ]

    for word in service_words:
        if word in desc_lower:
            return "39"

    for word in equipment_words:
        if word in desc_lower:
            return "52"

    return "30"


def _element_label(element: Optional[str]) -> Optional[str]:
    """Retorna rótulo amigável (Material, Serviço, Equipamento) para um elemento."""
    if not element:
        return None
    info = ND_ELEMENTS.get(element)
    if not info:
        return None
    nome = info.get("nome") or ""
    tipo = info.get("tipo") or ""
    if tipo == "material":
        base = "Material"
    elif tipo == "servico":
        base = "Serviço"
    elif tipo == "equipamento":
        base = "Equipamento"
    else:
        base = nome or tipo or element
    return f"{base} ({element})"


def _build_fallback_item(
    item: Union[Stage2Item, Dict[str, Any]],
    nc_nd: Optional[str],
    nd_req_value: Optional[str],
    quick_element: str,
) -> Stage3NDCrossItem:
    """
    Constrói um resultado mínimo quando a IA não está disponível
    (classificação rápida apenas).
    """
    desc_full = getattr(item, "descricao_resumida", None) or getattr(
        item, "descricao_completa", None
    )
    if isinstance(item, dict):
        desc_full = (
            item.get("descricao_resumida")
            or item.get("descricao_completa")
            or item.get("descricao")
        )

    unidade = getattr(item, "unidade", None)
    if isinstance(item, dict):
        unidade = unidade or item.get("unidade")

    item_num = getattr(item, "item", None)
    if isinstance(item, dict):
        item_num = item.get("item")

    nc_element = get_element(nc_nd)
    req_element = get_element(nd_req_value)

    nd_nc_compativel = nc_element == quick_element if nc_element else None
    nd_req_compativel = req_element == quick_element if req_element else None

    # Considera compatível apenas se nenhuma das duas for explicitamente incompatível.
    compativel: Optional[bool]
    if nd_nc_compativel is False or nd_req_compativel is False:
        compativel = False
    elif nd_nc_compativel is None and nd_req_compativel is None:
        compativel = None
    else:
        compativel = True

    return Stage3NDCrossItem(
        item=item_num,
        descricao=desc_full,
        unidade=unidade,
        nd_nc=nc_nd,
        nd_req=nd_req_value,
        classificacao_sugerida=quick_element,
        classificacao_label=_element_label(quick_element),
        subelemento_sugerido=None,
        nome_subelemento=None,
        nd_nc_compativel=nd_nc_compativel,
        nd_req_compativel=nd_req_compativel,
        compativel=compativel,
        metodo="palavras_chave_fallback",
        justificativa=(
            "Classificação estimada por palavras‑chave, sem uso de IA "
            "por falta de disponibilidade da API."
        ),
        confianca=70,
    )


STAGE3_ND_CHECK_PROMPT = """
Você é um especialista em classificação orçamentária do governo brasileiro.

Analise o item abaixo e determine sua classificação correta:

ITEM: {descricao_item}
UNIDADE: {unidade}
ND NA NC: {nd_nc} ({nome_nd_nc})
ND NA REQUISIÇÃO: {nd_req} ({nome_nd_req})

A ND (Natureza da Despesa) classifica o tipo de gasto:
- Elemento 30: Material de Consumo (compra de bens físicos)
- Elemento 39: Serviços de Terceiros PJ (contratação de serviços)
- Elemento 52: Equipamentos e Material Permanente (bens duráveis)

Determine:
1. O item é material (30), serviço (39) ou equipamento (52)?
2. A ND da NC está correta para este item?
3. A ND da requisição está correta para este item?
4. Qual o subelemento mais adequado?

Use também, quando útil, a seguinte tabela resumida de ND e subelementos:
{nd_tabela_json}

Retorne APENAS JSON:
{{
  "classificacao_correta": "30|39|52",
  "subelemento_sugerido": "17",
  "nome_subelemento": "Manutenção e Conservação de Máquinas e Equipamentos",
  "nd_nc_compativel": true,
  "nd_req_compativel": true,
  "justificativa": "O item descreve serviço de manutenção, portanto deve ser classificado como elemento 39 (Serviços)",
  "confianca": 95
}}
""".strip()


async def classify_item_nd(
    item: Union[Stage2Item, Dict[str, Any]],
    nc_nd: Optional[str],
    nd_req_value: Optional[str],
) -> Stage3NDCrossItem:
    """
    Usa Gemini para classificação detalhada ND × Item.

    Parâmetros:
    - item: Stage2Item (ou dict equivalente) do Estágio 2;
    - nc_nd: ND completa (6 dígitos) usada na NC;
    - nd_req_value: ND/SI da requisição para o item (formato livre).
    """
    desc_full = getattr(item, "descricao_completa", None)
    desc_resumida = getattr(item, "descricao_resumida", None)
    if isinstance(item, dict):
        desc_full = desc_full or item.get("descricao_completa")
        desc_resumida = desc_resumida or item.get("descricao_resumida")

    descricao_item = desc_full or desc_resumida or ""

    unidade = getattr(item, "unidade", None)
    if isinstance(item, dict):
        unidade = unidade or item.get("unidade")

    item_num = getattr(item, "item", None)
    if isinstance(item, dict):
        item_num = item.get("item")

    # ND da requisição por item: usa nd_si normalizado quando disponível.
    nd_si = getattr(item, "nd_si", None)
    nd_si_original = getattr(item, "nd_si_original", None)
    if isinstance(item, dict):
        nd_si = nd_si or item.get("nd_si")
        nd_si_original = nd_si_original or item.get("nd_si_original")

    nd_req_display = nd_req_value or nd_si_original or nd_si

    nc_element = get_element(nc_nd)
    req_element = get_element(nd_req_display)

    nome_nd_nc = ND_ELEMENTS.get(nc_element or "", {}).get("nome", "") if nc_element else ""
    nome_nd_req = ND_ELEMENTS.get(req_element or "", {}).get("nome", "") if req_element else ""

    # Classificação rápida para fallback e comparação.
    quick_element = quick_classify(descricao_item)

    try:
        proc = GeminiProcessor()
    except ValueError as exc:  # GEMINI_API_KEY ausente ou inválida
        logger.warning("Gemini indisponível para cruzamento ND × Itens: %s", exc)
        return _build_fallback_item(item, nc_nd, nd_req_display, quick_element)

    prompt = STAGE3_ND_CHECK_PROMPT.format(
        descricao_item=descricao_item,
        unidade=unidade or "",
        nd_nc=nc_nd or "não informada",
        nome_nd_nc=nome_nd_nc or "não identificado",
        nd_req=nd_req_display or "não informada",
        nome_nd_req=nome_nd_req or "não identificado",
        nd_tabela_json=str(ND_ELEMENTS),
    )

    try:
        result, _, _ = proc._generate(prompt, "stage3_nd_crosscheck")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao classificar item ND com IA: %s", exc)
        return _build_fallback_item(item, nc_nd, nd_req_display, quick_element)

    if not isinstance(result, dict):
        return _build_fallback_item(item, nc_nd, nd_req_display, quick_element)

    classificacao = str(result.get("classificacao_correta") or "").strip()
    if classificacao not in {"30", "39", "52"}:
        classificacao = quick_element

    subelemento = result.get("subelemento_sugerido")
    if subelemento is not None:
        subelemento = str(subelemento).zfill(2)

    nome_subelemento = result.get("nome_subelemento")

    def _as_bool(value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "t", "1", "sim"}:
                return True
            if v in {"false", "f", "0", "nao", "não"}:
                return False
        return None

    nd_nc_compativel = _as_bool(result.get("nd_nc_compativel"))
    nd_req_compativel = _as_bool(result.get("nd_req_compativel"))

    justificativa = result.get("justificativa")
    if isinstance(justificativa, (list, dict)):
        justificativa = str(justificativa)

    conf_raw = result.get("confianca")
    try:
        confianca = int(conf_raw) if conf_raw is not None else None
    except (TypeError, ValueError):
        confianca = None

    # Compatibilidade geral: false se qualquer um for explicitamente falso.
    if nd_nc_compativel is False or nd_req_compativel is False:
        compativel = False
    elif nd_nc_compativel is None and nd_req_compativel is None:
        compativel = None
    else:
        compativel = True

    return Stage3NDCrossItem(
        item=item_num,
        descricao=descricao_item or desc_resumida,
        unidade=unidade,
        nd_nc=nc_nd,
        nd_req=nd_req_display,
        classificacao_sugerida=classificacao,
        classificacao_label=_element_label(classificacao),
        subelemento_sugerido=subelemento,
        nome_subelemento=nome_subelemento,
        nd_nc_compativel=nd_nc_compativel,
        nd_req_compativel=nd_req_compativel,
        compativel=compativel,
        metodo="ia",
        justificativa=justificativa,
        confianca=confianca,
    )


async def cross_check_nd_items(
    nc_destinos: Sequence[Union[Stage3Destination, Dict[str, Any]]],
    items: Sequence[Union[Stage2Item, Dict[str, Any]]],
    nd_req: Optional[str] = None,
) -> Stage3NDCrosscheck:
    """
    Cruza ND da NC com os itens da requisição.

    Parâmetros:
    - nc_destinos: destinos da NC com ND (lista de Stage3Destination ou dict);
    - items: itens do Estágio 2 (lista de Stage2Item ou dict);
    - nd_req: ND agregada da requisição (opcional). Quando não informada,
      usa‑se a ND/SI por item (nd_si / nd_si_original).
    """
    resultados: List[Stage3NDCrossItem] = []

    if not nc_destinos or not items:
        return Stage3NDCrosscheck(cruzamentos=[], todos_compativeis=True, inconsistencias=[])

    # Agrupar NDs únicas da NC.
    nc_nds: List[str] = []
    seen: set[str] = set()
    for dest in nc_destinos:
        nd_value: Optional[str]
        if isinstance(dest, dict):
            nd_value = dest.get("nd")
        else:
            nd_value = dest.nd
        if not nd_value:
            continue
        if nd_value not in seen:
            seen.add(nd_value)
            nc_nds.append(nd_value)

    if not nc_nds:
        return Stage3NDCrosscheck(cruzamentos=[], todos_compativeis=True, inconsistencias=[])

    # Para cada item, verificar contra cada ND distinta da NC.
    for item in items:
        desc_full = getattr(item, "descricao_completa", None)
        desc_resumida = getattr(item, "descricao_resumida", None)
        if isinstance(item, dict):
            desc_full = desc_full or item.get("descricao_completa")
            desc_resumida = desc_resumida or item.get("descricao_resumida") or item.get(
                "descricao"
            )

        descricao_base = desc_full or desc_resumida or ""
        if not descricao_base.strip():
            continue

        # ND da requisição em nível de item (se disponível).
        nd_si = getattr(item, "nd_si", None)
        nd_si_original = getattr(item, "nd_si_original", None)
        if isinstance(item, dict):
            nd_si = nd_si or item.get("nd_si")
            nd_si_original = nd_si_original or item.get("nd_si_original")
        nd_req_item = nd_si_original or nd_si or nd_req

        for nc_nd in nc_nds:
            quick_element = quick_classify(descricao_base)
            nc_element = get_element(nc_nd)
            req_element = get_element(nd_req_item)

            # Se a classificação rápida já bate com a ND da NC, tentamos
            # evitar chamada à IA quando não há forte indício de conflito.
            if quick_element == nc_element and (
                not req_element or req_element == quick_element
            ):
                resultados.append(
                    Stage3NDCrossItem(
                        item=getattr(item, "item", None)
                        if not isinstance(item, dict)
                        else item.get("item"),
                        descricao=descricao_base,
                        unidade=(
                            getattr(item, "unidade", None)
                            if not isinstance(item, dict)
                            else item.get("unidade")
                        ),
                        nd_nc=nc_nd,
                        nd_req=nd_req_item,
                        classificacao_sugerida=quick_element,
                        classificacao_label=_element_label(quick_element),
                        subelemento_sugerido=None,
                        nome_subelemento=None,
                        nd_nc_compativel=True,
                        nd_req_compativel=True if req_element else None,
                        compativel=True,
                        metodo="palavras_chave",
                        justificativa=(
                            "Classificação rápida por palavras‑chave coerente com a ND da NC "
                            "e com a ND da requisição (quando informada)."
                        ),
                        confianca=80,
                    )
                )
            else:
                # Usar IA para classificação detalhada.
                resultado_item = await classify_item_nd(item, nc_nd, nd_req_item)
                resultados.append(resultado_item)

    if not resultados:
        return Stage3NDCrosscheck(cruzamentos=[], todos_compativeis=True, inconsistencias=[])

    inconsistencias = [
        r
        for r in resultados
        if r.compativel is False
        or r.nd_nc_compativel is False
        or r.nd_req_compativel is False
    ]

    todos_compativeis = len(inconsistencias) == 0

    return Stage3NDCrosscheck(
        cruzamentos=resultados,
        todos_compativeis=todos_compativeis,
        inconsistencias=inconsistencias,
    )

