from backend.models import Stage2Item
from backend.stages.stage2_analysis import _merge_image_table_results


def test_merge_image_table_results_prefers_vision_total_when_azure_total_disagrees_with_item_sum():
    azure_items = [
        Stage2Item(item=13, valor_total=1000.00),
        Stage2Item(item=14, valor_total=500.00),
    ]
    azure_data = {
        "items": azure_items,
        "fornecedor": None,
        "cnpj": "11.111.111/0001-11",
        "valor_total_geral": 1200.00,
    }
    vision_data = {
        "items": [],
        "fornecedor": "Fornecedor Vision",
        "cnpj": None,
        "valor_total_geral": 1500.00,
    }

    items, fornecedor, cnpj, total = _merge_image_table_results(azure_data, vision_data)

    assert [item.item for item in items] == [13, 14]
    assert fornecedor == "Fornecedor Vision"
    assert cnpj == "11.111.111/0001-11"
    assert total == 1500.0


def test_merge_image_table_results_keeps_azure_itemization_and_prefers_matching_azure_total():
    azure_items = [
        Stage2Item(item=1, valor_total=400.00),
        Stage2Item(item=2, valor_total=600.00),
    ]
    azure_data = {
        "items": azure_items,
        "fornecedor": "Fornecedor Azure",
        "cnpj": "22.222.222/0001-22",
        "valor_total_geral": 1000.00,
    }
    vision_data = {
        "items": [Stage2Item(item=9, valor_total=999.00)],
        "fornecedor": "Fornecedor Vision",
        "cnpj": "33.333.333/0001-33",
        "valor_total_geral": 999.00,
    }

    items, fornecedor, cnpj, total = _merge_image_table_results(azure_data, vision_data)

    assert [item.item for item in items] == [1, 2]
    assert fornecedor == "Fornecedor Vision"
    assert cnpj == "33.333.333/0001-33"
    assert total == 1000.0
