"""
Cache em memória de UASGs (código -> nome), carregado do banco e atualizado
quando o usuário adiciona uma nova UASG. Usado pelo stage2 para resolver
o nome da OM a partir do código.
"""

from __future__ import annotations

from typing import Dict, Optional

# Cache: codigo (str) -> nome (str). Preenchido no startup e ao adicionar UASG.
_UASG_CACHE: Dict[str, str] = {}


def get_uasg_nome(codigo: Optional[str]) -> Optional[str]:
    """Retorna o nome da OM para o código UASG, ou None se não estiver no banco."""
    if not codigo or not isinstance(codigo, str):
        return None
    return _UASG_CACHE.get(codigo.strip())


def set_uasg_in_cache(codigo: str, nome: str) -> None:
    """Atualiza o cache com uma UASG (após inserção no banco)."""
    codigo = (codigo or "").strip()
    if codigo:
        _UASG_CACHE[codigo] = (nome or "").strip()


def load_uasg_cache_from_dict(mapping: Dict[str, str]) -> None:
    """Preenche o cache a partir de um dicionário (ex.: resultado do banco)."""
    _UASG_CACHE.clear()
    for codigo, nome in (mapping or {}).items():
        if codigo and isinstance(codigo, str):
            _UASG_CACHE[codigo.strip()] = (nome or "").strip()


def get_uasg_cache_snapshot() -> Dict[str, str]:
    """Retorna cópia do cache (para debug ou listagem)."""
    return dict(_UASG_CACHE)
