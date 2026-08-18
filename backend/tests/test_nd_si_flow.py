import pytest

from backend.stages.stage2_analysis import parse_nd_si, resolve_nd_candidate, compute_nd_req_from_items
from backend.models import Stage2Item


def test_parse_partial_prefix_3390_invalid():
    parsed = parse_nd_si("33.90")
    assert parsed["parse_type"] == "partial_prefix"
    assert parsed["canonical"] is None
    assert parsed["valid"] is False
    assert parsed["valid_element"] is False
    assert parsed["valid_pair"] is False
    assert parsed["is_partial"] is True


@pytest.mark.parametrize(
    "raw,expected_display,expected_canonical",
    [
        ("33.90.30/07", "30/07", "30.07"),
        ("30/07", "30/07", "30.07"),
        ("30.07", "30/07", "30.07"),
    ],
)
def test_parse_full_nd_si_variants(raw, expected_display, expected_canonical):
    parsed = parse_nd_si(raw)
    assert parsed["element"] == "30"
    assert parsed["subelement"] == "07"
    assert parsed["display"] == expected_display
    assert parsed["canonical"] == expected_canonical
    assert parsed["valid"] is True
    assert parsed["valid_element"] is True
    assert parsed["valid_pair"] is True
    assert parsed["is_partial"] is False


@pytest.mark.parametrize("raw", ["33.90", "33.90.30", "339030"])
def test_generic_nd_not_promoted_as_final(raw: str):
    """
    Valores genéricos/parciais como 33.90, 33.90.30 ou 339030 não devem virar ND/SI
    final confiável do item.
    """
    res = resolve_nd_candidate(raw_nd=raw, descricao_item="aquisição de material", nd_processo="30")
    assert res["chosen"] is None
    assert res["ambiguous"] is True
    assert isinstance(res["candidates"], list) and len(res["candidates"]) >= 1


def test_deduplication_of_equivalent_candidates():
    """
    Candidatos equivalentes (ex.: 33.90.30/07 e 30/07) devem ser deduplicados.
    """
    res = resolve_nd_candidate(
        raw_nd="33.90.30/07",
        descricao_item="gêneros alimentícios",
        nd_processo="30",
        candidatos_extras=["30/07"],
    )
    cand_list = res["candidates"]
    # chosen deve ser um par completo válido (30.07)
    chosen = res["chosen"]
    assert chosen is not None
    assert chosen.get("canonical") == "30.07"
    assert chosen.get("element") == "30"
    assert chosen.get("subelement") == "07"
    canonicals = {c.get("canonical") for c in cand_list}
    # Apenas um canônico final para o par 30.07
    assert "30.07" in canonicals
    # Não deve haver dois registros distintos com mesmo trio (canonical, element, subelement)
    triplets = {
        (c.get("canonical"), c.get("element"), c.get("subelement")) for c in cand_list
    }
    assert len(triplets) == len(cand_list)


def test_nd_processo_influences_score():
    """
    ND do processo deve influenciar o score, favorecendo o elemento coerente.
    """
    # Mesmo bruto, mas candidatos extras conflitantes; nd_processo deve empurrar o resultado.
    res_30 = resolve_nd_candidate(
        raw_nd="30/07",
        descricao_item="aquisição de material de expediente",
        nd_processo="30",
        candidatos_extras=["39/17"],
    )
    res_39 = resolve_nd_candidate(
        raw_nd="30/07",
        descricao_item="serviço de manutenção de equipamentos",
        nd_processo="39",
        candidatos_extras=["39/17"],
    )

    chosen_30 = res_30["chosen"]
    chosen_39 = res_39["chosen"]
    assert chosen_30 is not None
    assert chosen_39 is not None
    # Quando nd_processo é 30, esperamos manter o elemento 30
    assert chosen_30.get("element") == "30"
    # Quando nd_processo é 39 e há candidato 39/17 válido, ele deve ser favorecido
    assert chosen_39.get("element") == "39"


def test_compute_nd_req_from_items_conflict_and_consensus():
    # Caso de consenso em 30.07
    items_consensus = [
        Stage2Item(
            item=1,
            catmat=None,
            descricao_completa=None,
            descricao_resumida=None,
            unidade=None,
            quantidade=None,
            nd_si="30.07",
            nd_si_display="30/07",
            nd_si_original="30/07",
            nd_si_raw="30/07",
            nd_si_candidates=[],
            nd_si_resolution_reason=None,
            nd_si_ambigua=False,
            valor_unitario=None,
            valor_total=None,
        ),
        Stage2Item(
            item=2,
            catmat=None,
            descricao_completa=None,
            descricao_resumida=None,
            unidade=None,
            quantidade=None,
            nd_si="30.07",
            nd_si_display="30/07",
            nd_si_original="33.90.30/07",
            nd_si_raw="33.90.30/07",
            nd_si_candidates=[],
            nd_si_resolution_reason=None,
            nd_si_ambigua=False,
            valor_unitario=None,
            valor_total=None,
        ),
    ]
    assert compute_nd_req_from_items(items_consensus) == "30.07"

    # Caso de conflito entre itens (30.07 x 30.17) → não agregamos.
    items_conflict = [
        items_consensus[0],
        Stage2Item(
            item=3,
            catmat=None,
            descricao_completa=None,
            descricao_resumida=None,
            unidade=None,
            quantidade=None,
            nd_si="30.17",
            nd_si_display="30/17",
            nd_si_original="30/17",
            nd_si_raw="30/17",
            nd_si_candidates=[],
            nd_si_resolution_reason=None,
            nd_si_ambigua=False,
            valor_unitario=None,
            valor_total=None,
        ),
    ]
    assert compute_nd_req_from_items(items_conflict) is None

