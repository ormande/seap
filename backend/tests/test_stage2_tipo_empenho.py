from backend.stages.stage2_analysis import (
    extract_tipo_empenho_candidates,
    resolve_tipo_empenho,
)


def _resolve_single(text: str) -> dict:
    cands = extract_tipo_empenho_candidates(text, section="requisicao")
    return resolve_tipo_empenho(cands)


def test_tipo_empenho_header_ordinario():
    text = "Tipo de empenho: Ordinário"
    res = _resolve_single(text)
    assert res["value"] == "Ordinário"
    assert res["confidence"] > 60


def test_tipo_empenho_header_estimativo():
    text = "Tipo de empenho: Estimativo"
    res = _resolve_single(text)
    assert res["value"] == "Estimativo"
    assert res["confidence"] > 60


def test_tipo_empenho_header_global():
    text = "Tipo de empenho: Global"
    res = _resolve_single(text)
    assert res["value"] == "Global"
    assert res["confidence"] > 60


def test_tipo_empenho_header_sem_acento():
    text = "Tipo de empenho: Ordinario"
    res = _resolve_single(text)
    assert res["value"] == "Ordinário"
    assert res["confidence"] > 60


def test_tipo_empenho_header_caixa_alta():
    text = "TIPO DE EMPENHO: ORDINARIO"
    res = _resolve_single(text)
    assert res["value"] == "Ordinário"
    assert res["confidence"] > 60


def test_tipo_empenho_topico_especifico():
    texto = """4. Tipo de Empenho
O presente processo será executado sob o regime de empenho ordinário,
conforme legislação vigente."""
    res = _resolve_single(texto)
    assert res["value"] == "Ordinário"
    assert res["confidence"] > 50


def test_tipo_empenho_fora_de_contexto_nao_confiavel():
    texto = """
O impacto global da medida será avaliado em estudos posteriores.
Trata-se apenas de estimativa preliminar dos efeitos econômicos.
Não há qualquer referência a empenho neste trecho.
"""
    res = _resolve_single(texto)
    # Pode até haver candidatos fracos, mas não deve promover valor confiável.
    assert res["value"] is None or res["confidence"] == 0


def test_tipo_empenho_consenso_aumenta_confianca():
    header = "Tipo de empenho: Ordinário"
    corpo = "O empenho será ordinário, conforme definido no cabeçalho."
    res_header = _resolve_single(header)
    res_ambos = _resolve_single(header + "\n\n" + corpo)

    assert res_header["value"] == "Ordinário"
    assert res_ambos["value"] == "Ordinário"
    assert res_ambos["confidence"] >= res_header["confidence"]


def test_tipo_empenho_conflito_reduz_confianca_e_marca_ambiguidade():
    texto = """
Tipo de empenho: Ordinário
(...)
Tipo de empenho: Estimativo
"""
    res = _resolve_single(texto)
    # Deve reconhecer ambiguidade ou reduzir confiança de forma significativa.
    assert res.get("ambiguous") is True or res["confidence"] < 50

