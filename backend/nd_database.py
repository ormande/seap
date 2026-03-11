from __future__ import annotations

"""
Base de dados de Natureza de Despesa (ND) e subelementos.

Fonte de verdade:
- tabela oficial exportada do fluxo atual do Comprasnet, mantida em JSON;
- enriquecimento semântico local para apoiar o cruzamento ND × Itens.
"""

from json import loads
from pathlib import Path
from typing import Any, Dict


_OFFICIAL_JSON_PATH = Path(__file__).with_name("nd_official_mar26.json")


def _load_official_nd_table() -> Dict[str, Dict[str, Any]]:
    raw = loads(_OFFICIAL_JSON_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Tabela oficial de ND inválida: raiz não é objeto JSON.")
    return raw


ND_CLASSES: Dict[str, Dict[str, Any]] = _load_official_nd_table()


# Camada semântica usada pelo Stage 3 para contextualizar Material/Serviço/Equipamento.
_ELEMENT_SEMANTICS: Dict[str, Dict[str, Any]] = {
    "30": {
        "nome": "Material de Consumo",
        "tipo": "material",
        "descricao": "Aquisição de bens físicos consumíveis",
        "palavras_chave": [
            "aquisição",
            "compra",
            "fornecimento",
            "material",
            "produto",
            "unidade",
            "peça",
            "kit",
        ],
    },
    "39": {
        "nome": "Outros Serviços de Terceiros PJ",
        "tipo": "servico",
        "descricao": "Contratação de serviços de pessoa jurídica",
        "palavras_chave": [
            "manutenção",
            "serviço",
            "contratação",
            "instalação",
            "reparo",
            "conservação",
            "locação",
            "limpeza",
            "vigilância",
            "consultoria",
            "treinamento",
        ],
    },
    "52": {
        "nome": "Equipamentos e Material Permanente",
        "tipo": "equipamento",
        "descricao": "Aquisição de bens duráveis/permanentes",
        "palavras_chave": [
            "equipamento",
            "aparelho",
            "máquina",
            "veículo",
            "mobiliário",
            "permanente",
        ],
    },
}


def _title_case_ascii(value: str) -> str:
    return " ".join(part.capitalize() for part in (value or "").strip().split())


def _build_nd_elements() -> Dict[str, Dict[str, Any]]:
    elements: Dict[str, Dict[str, Any]] = {}

    for nd_code, info in ND_CLASSES.items():
        if not isinstance(info, dict) or len(nd_code) < 2:
            continue

        element = nd_code[-2:]
        sub_map = info.get("subelementos") or {}
        semantics = _ELEMENT_SEMANTICS.get(element, {})
        official_desc = str(info.get("descricao") or "").strip()

        elements[element] = {
            "codigo_classe": nd_code,
            "nome": semantics.get("nome") or _title_case_ascii(official_desc),
            "tipo": semantics.get("tipo"),
            "descricao": semantics.get("descricao") or official_desc,
            "palavras_chave": list(semantics.get("palavras_chave") or []),
            "subelementos": {
                str(k).zfill(2): str(v).strip() for k, v in sub_map.items() if str(k).strip()
            },
        }

    return elements


ND_ELEMENTS: Dict[str, Dict[str, Any]] = _build_nd_elements()
