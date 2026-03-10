from backend.stages.stage2_analysis import (
    extract_instrument_candidates,
    resolve_instrument,
)


def _resolve_single(text: str) -> dict:
    cands = extract_instrument_candidates(text, section="requisicao")
    return resolve_instrument(cands)


def test_instrument_pregao_eletronico_narrativo():
    text = "por meio do Pregão Eletrônico nº 90005/2025 gerenciado pela UASG 160078 – 3º B Sup."
    res = _resolve_single(text)
    instr = res["instrument"]
    assert instr is not None
    assert instr["tipo"] == "Pregão Eletrônico"
    assert instr["numero"] == "90005/2025"
    assert res["confidence"] > 60


def test_instrument_pe_sigla_curta():
    text = "PE 90005/2025 UASG: 160078-CMCG - (Part)"
    res = _resolve_single(text)
    instr = res["instrument"]
    assert instr is not None
    assert instr["tipo"] == "Pregão Eletrônico"
    assert instr["numero"] == "90005/2025"
    assert res["confidence"] > 40


def test_instrument_contrato_telegráfico_campo6():
    text = "CONTRATO N° 28/2026, UASG 160142 (GER)."
    res = _resolve_single(text)
    instr = res["instrument"]
    assert instr is not None
    assert instr["tipo"] == "Contrato"
    assert instr["numero"] == "28/2026"
    assert res["confidence"] > 40


def test_instrument_pregao_curto_campo6():
    text = "PREGÃO N° 90003/2025, UASG 160142 (GER)."
    res = _resolve_single(text)
    instr = res["instrument"]
    assert instr is not None
    assert instr["tipo"] == "Pregão Eletrônico"
    assert instr["numero"] == "90003/2025"
    assert res["confidence"] > 40


def test_instrument_pregao_eletronico_ano_2_digitos():
    text = "por meio do Pregão Eletrônico nº 90021/25 gerenciado pela UASG 160078."
    res = _resolve_single(text)
    instr = res["instrument"]
    assert instr is not None
    # Ano deve ser normalizado para 4 dígitos.
    assert instr["numero"].endswith("/2025")


def test_instrument_false_positive_egfc_contrato():
    text = "Equipe de Gestão e Fiscalização de Contrato (EGFC) designada pela Portaria nº 123."
    res = _resolve_single(text)
    # Não deve promover isso como instrumento confiável.
    assert res["instrument"] is None or res["confidence"] == 0


def test_instrument_false_positive_lei_14133():
    text = "Nos termos da Lei Federal Nr 14.133, de 1º de abril de 2021, fica designado o Gestor de Contrato."
    res = _resolve_single(text)
    assert res["instrument"] is None or res["confidence"] == 0


def test_instrument_consensus_between_topico1_and_campo6():
    texto_topico1 = "por meio do Pregão Eletrônico nº 90005/2025 gerenciado pela UASG 160078."
    texto_campo6 = "PE 90005/2025 UASG: 160078-CMCG - (Part)"

    res_topico1 = _resolve_single(texto_topico1)
    res_ambos = _resolve_single(texto_topico1 + " " + texto_campo6)

    assert res_topico1["instrument"] is not None
    assert res_ambos["instrument"] is not None
    # Confiança com consenso (tópico 1 + campo 6) deve ser maior ou igual.
    assert res_ambos["confidence"] >= res_topico1["confidence"]


def test_instrument_resolution_exposes_diagnostics_for_persistence():
    text = "por meio do Pregão Eletrônico nº 90005/2025 gerenciado pela UASG 160078."
    res = _resolve_single(text)

    assert res["instrument"] is not None
    assert res["source"] == "topico1_narrativo"
    assert "90005/2025" in (res["matched_text"] or "")
    assert res["normalized_text"] == "Pregão Eletrônico 90005/2025"
    assert isinstance(res["candidates"], list) and len(res["candidates"]) >= 1
    assert isinstance(res["reason"], str) and res["reason"]

