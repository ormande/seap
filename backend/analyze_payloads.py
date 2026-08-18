from __future__ import annotations

from typing import Any, Dict

try:
    from .models import AnalyzeResponse, AnalyzeSummary
except ImportError:
    from models import AnalyzeResponse, AnalyzeSummary


SUMMARY_EXCLUDE = {
    "extraction": True,
    "stages": {
        "stage2": {
            "data": {
                "uasg_details": True,
                "tipo_empenho_details": True,
                "cnpj_details": True,
                "instrumento": {
                    "confidence": True,
                    "source": True,
                    "matched_text": True,
                    "normalized_text": True,
                    "resolution_reason": True,
                    "candidates": True,
                },
                "itens": {
                    "__all__": {
                        "nd_si_candidates": True,
                        "nd_si_resolution_reason": True,
                        "nd_si_ambigua": True,
                    }
                },
            }
        }
    },
}


def build_analyze_full_payload(analyze_response: AnalyzeResponse) -> Dict[str, Any]:
    """Serializa o resultado completo com texto bruto e trilhas diagnósticas."""
    return analyze_response.model_dump(mode="json")


def build_analyze_summary_payload(analyze_response: AnalyzeResponse) -> Dict[str, Any]:
    """
    Serializa uma versão enxuta para UI/download padrão.

    Remove texto bruto e trilhas diagnósticas profundas, preservando o
    resultado consolidado por estágio.
    """
    summary_dict = analyze_response.model_dump(mode="json", exclude=SUMMARY_EXCLUDE)
    summary_model = AnalyzeSummary.model_validate(summary_dict)
    return summary_model.model_dump(mode="json", exclude=SUMMARY_EXCLUDE)
