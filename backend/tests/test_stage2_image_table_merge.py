from backend.models import Stage2Item
from backend.stages.stage2_analysis import (
    _normalize_supplier_name,
    _parse_table_result,
    verify_calculations,
)


def test_verify_calculations_flags_divergence_when_quantity_times_unit_price_differs_from_total():
    items = [
        Stage2Item(item=1, quantidade=10.0, valor_unitario=5.00, valor_total=50.00),
        Stage2Item(item=2, quantidade=3.0, valor_unitario=25.00, valor_total=80.00),  # Erro: 3 * 25 = 75 != 80
    ]

    verif = verify_calculations(items, valor_total_documento=130.00)

    assert verif.correto is False
    assert len(verif.divergencias) == 1
    assert verif.divergencias[0].tipo == "item"
    assert verif.divergencias[0].item == 2
    assert verif.divergencias[0].esperado == 75.00
    assert verif.divergencias[0].encontrado == 80.00


def test_verify_calculations_flags_exact_one_cent_divergence():
    # 10 * 10.00 = 100.00, mas documento informou 100.01 (divergência exata de 1 centavo)
    items = [
        Stage2Item(item=1, quantidade=10.0, valor_unitario=10.00, valor_total=100.01),
    ]

    verif = verify_calculations(items, valor_total_documento=100.01)

    assert verif.correto is False
    assert len(verif.divergencias) == 1
    assert verif.divergencias[0].tipo == "item"
    assert verif.divergencias[0].item == 1
    assert verif.divergencias[0].esperado == 100.00
    assert verif.divergencias[0].encontrado == 100.01


def test_verify_calculations_passes_when_all_items_math_is_accurate():
    items = [
        Stage2Item(item=1, quantidade=100.0, valor_unitario=2.50, valor_total=250.00),
        Stage2Item(item=2, quantidade=20.0, valor_unitario=28.00, valor_total=560.00),
    ]

    verif = verify_calculations(items, valor_total_documento=810.00)

    assert verif.correto is True
    assert len(verif.divergencias) == 0
    assert verif.valor_total_calculado == 810.00


def test_parse_table_result_parses_gemini_vision_output():
    vision_raw = {
        "fornecedor": "PAPELARIA E COPIADORA MILITAR LTDA",
        "cnpj": "15.571.482/0001-07",
        "valor_total_geral": 250.00,
        "itens": [
            {
                "item": 1,
                "catmat": "150234",
                "descricao": "Caneta esferográfica azul",
                "unidade": "UND",
                "quantidade": 100.0,
                "valor_unitario": 2.50,
                "valor_total": 250.00,
                "nd_subelemento": "33.90.30.24",
            }
        ],
    }

    items, fornecedor, cnpj, total = _parse_table_result(vision_raw)

    assert len(items) == 1
    assert items[0].item == 1
    assert items[0].catmat == "150234"
    assert items[0].quantidade == 100.0
    assert items[0].valor_unitario == 2.50
    assert items[0].valor_total == 250.00
    assert fornecedor == "PAPELARIA E COPIADORA MILITAR LTDA"
    assert cnpj == "15.571.482/0001-07"
    assert float(total) == 250.00


def test_normalize_supplier_name_prefers_razao_social_and_uppercases():
    supplier = _normalize_supplier_name(
        {
            "nome": "Empório da Carne de Campo Grande",
            "razao_social": "Cooperativa Agrícola de Campo Grande",
        }
    )

    assert supplier == "COOPERATIVA AGRÍCOLA DE CAMPO GRANDE"
