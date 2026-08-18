from backend.stages.stage2_analysis import (
    extract_uasg_candidates,
    resolve_uasg,
)


def _resolve_single(text: str) -> dict:
    cands = extract_uasg_candidates(text, section="requisicao")
    return resolve_uasg(cands)


def test_uasg_narrativo_com_rotulo():
    text = "por meio do Pregão Eletrônico nº 90005/2025 gerenciado pela UASG 160142 – 9º Batalhão de Suprimento."
    res = _resolve_single(text)
    uasg = res["uasg"]
    assert uasg is not None
    assert uasg["codigo"] == "160142"
    assert res["confidence"] > 60


def test_uasg_narrativo_sem_rotulo_explicito():
    text = "por meio do Pregão Eletrônico nº 90005/2025 gerenciado pela 160078 – Colégio Militar de Campo Grande."
    res = _resolve_single(text)
    uasg = res["uasg"]
    assert uasg is not None
    assert uasg["codigo"] == "160078"
    assert res["confidence"] > 50


def test_uasg_telegráfico_com_ger():
    text = "CONTRATO N° 28/2026, UASG 160142 (GER)."
    res = _resolve_single(text)
    uasg = res["uasg"]
    assert uasg is not None
    assert uasg["codigo"] == "160142"
    assert res["confidence"] > 40


def test_uasg_telegráfico_participante():
    text = "PE 90005/2025 UASG: 160078-CMCG - (Part)"
    res = _resolve_single(text)
    uasg = res["uasg"]
    assert uasg is not None
    assert uasg["codigo"] == "160078"
    assert res["confidence"] > 40


def test_uasg_ug_simples():
    text = "UG 160136"
    res = _resolve_single(text)
    uasg = res["uasg"]
    assert uasg is not None
    assert uasg["codigo"] == "160136"
    assert res["confidence"] > 20


def test_uasg_codigo_enriquecido_pelo_banco():
    # 160142 está no seed da 9ª RM em backend/database.py
    text = "UASG 160142"
    res = _resolve_single(text)
    uasg = res["uasg"]
    assert uasg is not None
    assert uasg["codigo"] == "160142"
    # Mesmo sem nome textual, deve enriquecer via banco/cache e ter boa confiança.
    assert res["confidence"] > 30


def test_uasg_codigo_e_nome_coerentes():
    text = "UASG 160142 – 9º Batalhão de Suprimento"
    res = _resolve_single(text)
    uasg = res["uasg"]
    assert uasg is not None
    assert uasg["codigo"] == "160142"
    assert "coerente com o nome cadastrado" in (res["reason"] or "")


def test_uasg_codigo_e_nome_divergentes():
    text = "UASG 160142 – OM Fictícia Divergente"
    res = _resolve_single(text)
    # Ainda pode resolver um código, mas a confiança deve ser penalizada.
    assert res["uasg"] is None or res["confidence"] < 60


def test_uasg_consenso_aumenta_confianca():
    t1 = "UASG 160142 – 9º Batalhão de Suprimento"
    t2 = "CONTRATO N° 28/2026, UASG 160142 (GER)."
    res_single = _resolve_single(t1)
    res_both = _resolve_single(t1 + " " + t2)
    assert res_single["uasg"] is not None
    assert res_both["uasg"] is not None
    assert res_both["confidence"] >= res_single["confidence"]


def test_uasg_codigo_seis_digitos_contexto_fraco_nao_confiavel():
    texto = "O código do PTRES é 160142 e a natureza de despesa é 339039."
    res = _resolve_single(texto)
    # Pode haver candidato fraco, mas não deve promover UASG confiável.
    assert res["uasg"] is None or res["confidence"] == 0

