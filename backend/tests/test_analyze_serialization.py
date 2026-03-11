import json

from backend.analyze_payloads import (
    build_analyze_full_payload,
    build_analyze_summary_payload,
)
from backend.models import (
    AnalyzeMetadata,
    AnalyzeStages,
    AnalyzeResponse,
    Stage1Confidence,
    Stage1Data,
    Stage1OM,
    Stage1Requisicao,
    Stage1Result,
    Stage2CNPJDetails,
    Stage2Confidence,
    Stage2Data,
    Stage2Instrument,
    Stage2Result,
    Stage2TipoEmpenho,
    Stage2UASG,
    Stage2UASGDetails,
)


def _build_minimal_analyze_response() -> AnalyzeResponse:
    meta = AnalyzeMetadata(
        total_paginas=2,
        paginas_com_texto=2,
        paginas_sem_texto=0,
        paginas_escaneadas=[],
    )
    stage1 = Stage1Result(
        status="success",
        method="regex",
        data=Stage1Data(
            nup="12345",
            requisicao=Stage1Requisicao(numero=1, ano=2025, texto_original=""),
            om=Stage1OM(nome="OM X", sigla="OMX", validada=True, confianca=90),
        ),
        confidence=Stage1Confidence(nup=90, requisicao=80, om=95, geral=88),
    )
    stage2_data = Stage2Data(
        instrumento=Stage2Instrument(
            tipo="Pregao Eletronico",
            numero="90004/2025",
            confidence=95,
            source="topico1_narrativo",
            matched_text="Pregao Eletronico no 90004/2025",
            normalized_text="Pregao Eletronico 90004/2025",
            resolution_reason="Padrao forte.",
            candidates=[{"tipo": "Pregao Eletronico", "numero": "90004/2025"}],
        ),
        uasg=Stage2UASG(codigo="160142", nome="9o Batalhao de Suprimento"),
        uasg_details=Stage2UASGDetails(
            codigo="160142",
            nome="9o Batalhao de Suprimento",
            confidence=95,
            source="narrativo_gerenciado",
            matched_text="UASG 160142 - 9o Batalhao de Suprimento",
            normalized_text="160142 - 9o Batalhao de Suprimento",
            resolution_reason="Base local.",
            candidates=[{"codigo": "160142"}],
        ),
        tipo_empenho="Ordinario",
        tipo_empenho_details=Stage2TipoEmpenho(
            value="Ordinario",
            confidence=90,
            source="header_label",
            matched_text="Tipo de Empenho: Ordinario",
            normalized_text="Ordinario",
            resolution_reason="Cabecalho explicito.",
            candidates=[{"value": "Ordinario"}],
        ),
        fornecedor="ACME LTDA",
        cnpj="04.252.011/0001-10",
        cnpj_details=Stage2CNPJDetails(
            value="04252011000110",
            formatted_value="04.252.011/0001-10",
            confidence=90,
            source="label_cnpj",
            matched_text="CNPJ: 04.252.011/0001-10",
            normalized_text="04.252.011/0001-10",
            resolution_reason="Rotulo explicito.",
            candidates=[{"formatted_value": "04.252.011/0001-10"}],
        ),
        valor_total=1000.0,
        nd_req="30.07",
        itens=[
            {
                "item": 1,
                "catmat": "123",
                "descricao_completa": "PEITO DE FRANGO",
                "descricao_resumida": "PEITO DE FRANGO",
                "unidade": "KG",
                "quantidade": 10,
                "nd_si": "30.07",
                "nd_si_display": "30/07",
                "nd_si_original": "30/07",
                "nd_si_raw": "30.07",
                "nd_si_candidates": [{"canonical": "30.07"}],
                "nd_si_resolution_reason": "Par completo.",
                "nd_si_ambigua": False,
                "valor_unitario": 100.0,
                "valor_total": 1000.0,
            }
        ],
        verificacao_calculos=None,
        extracted_by_ai=False,
    )
    stage2 = Stage2Result(
        status="success",
        method="regex",
        data=stage2_data,
        confidence=Stage2Confidence(
            instrumento=80,
            uasg=90,
            tipo_empenho=85,
            fornecedor=80,
            cnpj=90,
            valor_total=90,
            itens=90,
            geral=88,
        ),
        inactive_fields=[],
    )
    stages = AnalyzeStages(
        stage1=stage1,
        stage2=stage2,
        stage3=None,
        stage4=None,
        stage5=None,
        stage6=None,
    )

    return AnalyzeResponse(
        extraction={"pagina_1": "texto 1", "pagina_2": "texto 2"},
        metadata=meta,
        stages=stages,
    )


def test_summary_vs_full_payload_structure() -> None:
    """Garante que summary poda o excesso e full preserva a auditoria."""
    analyze_response = _build_minimal_analyze_response()
    full_payload = build_analyze_full_payload(analyze_response)
    summary_payload = build_analyze_summary_payload(analyze_response)

    assert "extraction" not in summary_payload
    assert summary_payload["metadata"]["total_paginas"] == 2
    assert "stage1" in summary_payload["stages"]
    assert "stage2" in summary_payload["stages"]

    stage2_data = summary_payload["stages"]["stage2"]["data"]
    assert "uasg_details" not in stage2_data
    assert "tipo_empenho_details" not in stage2_data
    assert "cnpj_details" not in stage2_data
    assert stage2_data["instrumento"]["tipo"] == "Pregao Eletronico"
    assert "candidates" not in stage2_data["instrumento"]
    assert "matched_text" not in stage2_data["instrumento"]
    assert "nd_si_candidates" not in stage2_data["itens"][0]
    assert "nd_si_resolution_reason" not in stage2_data["itens"][0]
    assert "nd_si_ambigua" not in stage2_data["itens"][0]

    assert "extraction" in full_payload
    assert full_payload["extraction"]["pagina_1"] == "texto 1"
    assert "uasg_details" in full_payload["stages"]["stage2"]["data"]
    assert "candidates" in full_payload["stages"]["stage2"]["data"]["instrumento"]

    json.dumps(full_payload)
    json.dumps(summary_payload)
