import pytest

from backend.stages.stage2_analysis import _parse_table_result


def _build_single_item_result(item_dict):
    return {
        "fornecedor": None,
        "cnpj": None,
        "valor_total_geral": None,
        "itens": [item_dict],
    }


@pytest.mark.parametrize(
    "item_raw,expected_canonical,expected_display,expected_original",
    [
        (
            {
                "item": 1,
                "descricao": "Aquisição de gêneros alimentícios",
                "nd_si": "33.90",
                "nd": "33.90.30.07",
            },
            "30.07",
            "30/07",
            "33.90.30.07",
        ),
        (
            {
                "item": 1,
                "descricao": "Aquisição de gêneros alimentícios",
                "nd_si": "33.90.30.07",
            },
            "30.07",
            "30/07",
            "33.90.30.07",
        ),
        (
            {
                "item": 1,
                "descricao": "Aquisição de equipamentos permanentes",
                "nd_si": "44.90.52",
                "nd": "44.90.52/12",
            },
            "52.12",
            "52/12",
            "44.90.52/12",
        ),
        (
            {
                "item": 1,
                "descricao": "Aquisição de equipamentos permanentes",
                "nd_si": "44.90.52",
                "nd": "44.90.52/04",
            },
            "52.04",
            "52/04",
            "44.90.52/04",
        ),
    ],
)
def test_nd_si_item_prefers_full_pair_over_prefix(
    item_raw, expected_canonical, expected_display, expected_original
):
    result = _build_single_item_result(item_raw)
    items, fornecedor, cnpj, valor_total_geral = _parse_table_result(result)

    assert len(items) == 1
    item = items[0]

    # Canonical final deve preservar o par completo (elemento.subelemento)
    assert item.nd_si == expected_canonical
    # Display amigável mantém formato elemento/subelemento
    assert item.nd_si_display == expected_display
    # Original deve refletir o valor mais rico disponível na linha da tabela
    assert item.nd_si_original == expected_original
    # Não deve cair para prefixos genéricos como 33.90 ou 44.90.52
    assert item.nd_si_original not in {"33.90", "44.90.52"}


@pytest.mark.parametrize(
    "raw_value",
    [
        "30/07",
        "30/19",
    ],
)
def test_nd_si_item_simple_pairs_are_preserved(raw_value: str):
    result = _build_single_item_result(
        {
            "item": 1,
            "descricao": "Item qualquer",
            "nd_si": raw_value,
        }
    )
    items, fornecedor, cnpj, valor_total_geral = _parse_table_result(result)

    assert len(items) == 1
    item = items[0]

    # O valor bruto deve ser preservado em nd_si_original
    assert item.nd_si_original == raw_value
    # O display deve manter o formato elemento/subelemento
    assert item.nd_si_display == raw_value
    # O canônico final não pode ser nulo quando o par está completo
    assert item.nd_si is not None


def test_item_number_preserves_real_first_column_non_sequential_values():
    result = {
        "fornecedor": None,
        "cnpj": None,
        "valor_total_geral": None,
        "itens": [
            {"item": 29, "descricao": "Item 29", "nd_si": "30/07"},
            {"item": 204, "descricao": "Item 204", "nd_si": "30/19"},
        ],
    }

    items, fornecedor, cnpj, valor_total_geral = _parse_table_result(result)

    assert [item.item for item in items] == [29, 204]


@pytest.mark.parametrize(
    "raw_item_value,expected_item",
    [
        ("29", 29),
        ("029", 29),
        ("Item 29", 29),
        ("29.", 29),
        ("029 -", 29),
    ],
)
def test_item_number_normalization_accepts_common_ocr_formats(raw_item_value, expected_item):
    result = _build_single_item_result(
        {
            "item": raw_item_value,
            "descricao": "Item qualquer",
            "nd_si": "30/07",
        }
    )

    items, fornecedor, cnpj, valor_total_geral = _parse_table_result(result)

    assert len(items) == 1
    assert items[0].item == expected_item

