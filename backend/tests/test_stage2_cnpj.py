from backend.stages.stage2_analysis import (
    extract_cnpj_candidates,
    resolve_cnpj,
)


def _resolve_single(text: str) -> dict:
    cands = extract_cnpj_candidates(text, section="requisicao")
    return resolve_cnpj(cands)


def test_cnpj_rotulo_simples_formatado():
    text = "Fornecedor: ACME LTDA - CNPJ: 04.252.011/0001-10"
    res = _resolve_single(text)
    assert res["formatted_value"] == "04.252.011/0001-10"
    assert res["confidence"] > 60


def test_cnpj_cpf_cnpj_label():
    text = "CPF/CNPJ: 04.252.011/0001-10 - Razão social ACME LTDA"
    res = _resolve_single(text)
    assert res["formatted_value"] == "04.252.011/0001-10"
    assert res["confidence"] > 60


def test_cnpj_inscrita_no_cnpj():
    text = "A empresa ACME LTDA, inscrita no CNPJ sob o nº 04.252.011/0001-10, sediada nesta capital."
    res = _resolve_single(text)
    assert res["formatted_value"] == "04.252.011/0001-10"
    assert res["confidence"] > 60


def test_cnpj_sem_mascara_com_contexto_forte():
    text = "Empresa ACME LTDA, inscrita no CNPJ sob o nº 04252011000110, com sede em Brasília."
    res = _resolve_single(text)
    assert res["formatted_value"] == "04.252.011/0001-10"
    assert res["confidence"] > 60


def test_cnpj_invalido_falha_digito_verificador():
    text = "Fornecedor: Empresa X - CNPJ: 11.111.111/1111-11"
    res = _resolve_single(text)
    assert res["formatted_value"] is None or res["confidence"] == 0


def test_numero_administrativo_nao_vira_cnpj():
    texto = "O NUP do processo é 12345678901234 e o PTRES é 160142."
    res = _resolve_single(texto)
    assert res["formatted_value"] is None or res["confidence"] == 0


def test_cnpj_consenso_aumenta_confianca():
    t1 = "Fornecedor: ACME LTDA - CNPJ: 04.252.011/0001-10"
    t2 = "A empresa ACME LTDA, inscrita no CNPJ sob o nº 04.252.011/0001-10."
    res_single = _resolve_single(t1)
    res_both = _resolve_single(t1 + "\n" + t2)
    assert res_single["formatted_value"] == "04.252.011/0001-10"
    assert res_both["formatted_value"] == "04.252.011/0001-10"
    assert res_both["confidence"] >= res_single["confidence"]


def test_cnpj_sem_contexto_nao_confiavel():
    texto = "04252011000110"
    res = _resolve_single(texto)
    assert res["formatted_value"] is None or res["confidence"] == 0

