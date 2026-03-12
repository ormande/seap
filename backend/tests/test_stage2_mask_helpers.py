from backend.stages.stage2_analysis import (
    _apply_mask_header_dash,
    _apply_preferred_nd_to_mask,
    _apply_preferred_om_to_mask,
    _format_budget_nd_display,
    _infer_mask_uasg_role,
    _mask_contains_preferred_nd,
    _mask_om_label,
    _normalize_mask_date,
    _normalize_mask_text,
    _resolve_mask_nd,
)


def test_normalize_mask_date_from_long_portuguese_format():
    assert _normalize_mask_date("10 de fevereiro de 2026") == "10 FEV 26"


def test_normalize_mask_date_keeps_maio_extenso():
    assert _normalize_mask_date("15/05/2025") == "15 MAIO 25"


def test_resolve_mask_nd_prefers_budget_nd_when_compatible_with_items():
    nd, warnings = _resolve_mask_nd({"nd_orcamentaria": "339030"}, "30.07")

    assert nd == "339030"
    assert warnings == []


def test_resolve_mask_nd_falls_back_to_item_consistent_nd_on_conflict():
    nd, warnings = _resolve_mask_nd({"nd_orcamentaria": "339039"}, "30.07")

    assert nd == "339030"
    assert warnings


def test_normalize_mask_text_uppercases_and_closes_with_period():
    text = "9º B Sup, req 46, aqs de salmão, nd 339030, pe 90005/2025, uasg 160136 (ger)"

    assert _normalize_mask_text(text) == (
        "9º B SUP, REQ 46, AQS DE SALMÃO, ND 339030, PE 90005/2025, UASG 160136 (GER)."
    )


def test_infer_mask_uasg_role_detects_gerenciado_pela_uasg():
    text = "Pregão Eletrônico nº 90005/2025 gerenciado pela UASG 160136 - 9º Grupamento Logístico."

    assert _infer_mask_uasg_role(text) == "GER"


def test_apply_preferred_nd_to_mask_rewrites_item_level_nd_to_budget_nd():
    mask = "9º B SUP, REQ 46, AQS DE GORDURA, ND 30/07, PE 90005/2025, UASG 160136 (GER)."

    assert _apply_preferred_nd_to_mask(mask, "339030", "30.07") == (
        "9º B SUP, REQ 46, AQS DE GORDURA, ND 33.90.30, PE 90005/2025, UASG 160136 (GER)."
    )


def test_mask_contains_preferred_nd_accepts_formatted_budget_nd():
    mask = "9º B SUP, REQ 46, AQS DE GORDURA, ND 33.90.30, PE 90005/2025, UASG 160136 (GER)."

    assert _mask_contains_preferred_nd(mask, "339030") is True


def test_format_budget_nd_display_formats_budget_nd_with_dots():
    assert _format_budget_nd_display("339030") == "33.90.30"


def test_mask_om_label_prefers_abbreviated_om_name():
    text = "9º Batalhão de Suprimento, Req 45/2026"

    assert _mask_om_label(text, None) == "9º B SUP"


def test_apply_preferred_om_to_mask_rewrites_full_om_name():
    mask = "9º BATALHÃO DE SUPRIMENTO, REQ 45, ND 33.90.30, PE 90005/2025, UASG 160136 (GER)."

    assert _apply_preferred_om_to_mask(mask, "9º B SUP") == (
        "9º B SUP, REQ 45, ND 33.90.30, PE 90005/2025, UASG 160136 (GER)."
    )


def test_apply_mask_header_dash_rewrites_only_om_to_req_separator():
    mask = "9º GPT LOG, REQ Nº 45-CL I/C OP SUP/ CMDO, NC 2026NC401104, ND 33.90.30, PE 90005/2025, UASG 160136 (GER)."

    assert _apply_mask_header_dash(mask) == (
        "9º GPT LOG - REQ Nº 45-CL I/C OP SUP/ CMDO, NC 2026NC401104, ND 33.90.30, PE 90005/2025, UASG 160136 (GER)."
    )
