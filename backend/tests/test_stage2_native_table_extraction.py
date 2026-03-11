from pathlib import Path

from backend.stages.stage2_analysis import (
    _extract_native_item_table_tsv,
    _merge_native_table_hints,
)


FIXTURES_DIR = (
    Path(__file__).resolve().parent / "fixtures" / "stage2_requisicoes" / "nativas"
)


def _fixture_path(pattern: str) -> Path:
    matches = sorted(FIXTURES_DIR.glob(pattern))
    assert matches, f"Fixture não encontrada para o padrão: {pattern}"
    return matches[0]


def test_native_table_tsv_preserves_supplier_item_number_and_si_for_795():
    pdf = _fixture_path("*000795_2026-48.pdf")

    tsv = _extract_native_item_table_tsv(pdf, [1, 2, 3], image_pages=[])

    assert tsv is not None
    assert "Nome da Empresa: ROSILENE APARECIDA HERNANDES LTDA" in tsv
    assert "07\t317762" in tsv
    assert "44.90.52 /12" in tsv


def test_native_table_tsv_preserves_non_sequential_item_numbers_and_subelement_for_813():
    pdf = _fixture_path("*000813_2026-91.pdf")

    tsv = _extract_native_item_table_tsv(pdf, [1, 2, 3, 4, 5, 6], image_pages=[])

    assert tsv is not None
    assert "Nome da Empresa: LUVI COMERCIO DE MERCADORIAS E SERVICOS CORPORATIVOS LTDA" in tsv
    assert "6\t334043" in tsv
    assert "84\t446195" in tsv
    assert "44.90.52 /12" in tsv
    assert "/04" in tsv


def test_merge_native_table_hints_enriches_generic_nd_with_exact_subelement():
    result = {
        "fornecedor": None,
        "cnpj": None,
        "valor_total_geral": None,
        "itens": [
            {
                "item": 7,
                "catmat": "317762",
                "descricao": "Sanduicheira",
                "nd_si": "44.90.52",
            }
        ],
    }
    native_tsv = (
        "Nome da Empresa: ROSILENE APARECIDA HERNANDES LTDA\t\t\t\t\t\t\t\t\t\n"
        "ÍTEM\tCÓD CatMat/ CatServ\tDESCRIÇÃO DO MATERIAL/ SERVIÇO\tUND\tQTD\tND / S.I.\tP. UNT\tP TOTAL\n"
        "07\t317762\tSanduicheira\tUnidade\t01\t44.90.52 /12\t950,00\t950,00\n"
        "TOTAL (R$)\t\t\t\t\t\t\t950,00\n"
    )

    merged = _merge_native_table_hints(result, native_tsv)

    assert merged["fornecedor"] == "ROSILENE APARECIDA HERNANDES LTDA"
    assert merged["valor_total_geral"] == 950.0
    assert merged["itens"][0]["item"] == 7
    assert merged["itens"][0]["nd"] == "44.90.52 /12"
