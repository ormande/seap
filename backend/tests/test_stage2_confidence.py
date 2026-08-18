from backend.models import (
    Stage2Data,
    Stage2Instrument,
    Stage2Item,
    Stage2UASG,
)
from backend.stages.stage2_analysis import _compute_confidence


def test_compute_confidence_recalibrates_uasg_when_final_data_is_consistent():
    data = Stage2Data(
        instrumento=Stage2Instrument(tipo="Pregão Eletrônico", numero="90017/2025"),
        uasg=Stage2UASG(codigo="160136", nome="9º Grupamento Logístico"),
        itens=[],
    )

    confidence = _compute_confidence(
        data,
        uasg_conf_override=25,
    )

    assert confidence.uasg >= 90


def test_compute_confidence_recalibrates_fornecedor_and_cnpj_with_corroborating_items():
    data = Stage2Data(
        fornecedor="Fornecedor Exemplo LTDA",
        cnpj="12.345.678/0001-90",
        itens=[
            Stage2Item(item=1, valor_total=100.0),
        ],
    )

    confidence = _compute_confidence(data, cnpj_conf_override=45)

    assert confidence.fornecedor == 95
    assert confidence.cnpj == 95
