"""
Persistência de análises em PostgreSQL via asyncpg.

Cada análise é associada a um usuário (Google OAuth) por user_id.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

import asyncpg

DATABASE_URL = os.environ.get("DATABASE_URL")

pool: Optional[asyncpg.Pool] = None


async def init_db() -> None:
    """
    Inicializa o pool de conexões e cria as tabelas, se necessário.
    Chamado na inicialização do FastAPI.
    """
    global pool
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL não definida. Configure a URL do PostgreSQL no ambiente."
        )

    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)

    async with pool.acquire() as conn:  # type: ignore[union-attr]
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                image TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                nup TEXT,
                requisicao TEXT,
                om TEXT,
                om_sigla TEXT,
                instrumento_tipo TEXT,
                instrumento_numero TEXT,
                uasg_codigo TEXT,
                uasg_nome TEXT,
                fornecedor TEXT,
                cnpj TEXT,
                valor_total REAL,
                qtd_itens INTEGER,
                veredicto TEXT,
                despacho TEXT,
                tempo_analise INTEGER,
                data_analise TIMESTAMP DEFAULT NOW(),
                dados_completos JSONB
            )
            """
        )


def _extract_summary(dados_completos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrai campos resumidos dos estágios para popular as colunas da tabela analyses.
    """
    out: Dict[str, Any] = {
        "nup": None,
        "requisicao": None,
        "om": None,
        "om_sigla": None,
        "instrumento_tipo": None,
        "instrumento_numero": None,
        "uasg_codigo": None,
        "uasg_nome": None,
        "fornecedor": None,
        "cnpj": None,
        "valor_total": None,
        "qtd_itens": 0,
        "veredicto": None,
        "despacho": None,
    }
    stages = dados_completos.get("stages") or {}

    # Estágio 1
    s1 = stages.get("stage1") or {}
    s1_data = s1.get("data") or {}
    out["nup"] = s1_data.get("nup")
    req = s1_data.get("requisicao") or {}
    if isinstance(req, dict):
        num, ano = req.get("numero"), req.get("ano")
        if num is not None and ano is not None:
            out["requisicao"] = f"Req {num}/{ano}"
        elif req.get("texto_original"):
            out["requisicao"] = str(req.get("texto_original"))[:80]
    om = s1_data.get("om") or {}
    if isinstance(om, dict):
        out["om"] = om.get("nome")
        out["om_sigla"] = om.get("sigla")

    # Estágio 2
    s2 = stages.get("stage2") or {}
    s2_data = s2.get("data") or {}
    inst = s2_data.get("instrumento") or {}
    if isinstance(inst, dict):
        out["instrumento_tipo"] = inst.get("tipo")
        out["instrumento_numero"] = inst.get("numero")
    uasg = s2_data.get("uasg") or {}
    if isinstance(uasg, dict):
        out["uasg_codigo"] = uasg.get("codigo")
        out["uasg_nome"] = uasg.get("nome")
    out["fornecedor"] = s2_data.get("fornecedor")
    out["cnpj"] = s2_data.get("cnpj")
    out["valor_total"] = s2_data.get("valor_total")
    itens = s2_data.get("itens") or []
    out["qtd_itens"] = len(itens) if isinstance(itens, list) else 0

    # Estágio 6
    s6 = stages.get("stage6") or {}
    out["veredicto"] = s6.get("status") or s6.get("veredicto")
    out["despacho"] = s6.get("despacho")

    return out


async def get_or_create_user(user_id: str, email: str, name: str) -> Dict[str, Any]:
    """Busca ou cria usuário a partir do id (sub do Google)."""
    if pool is None:
        raise RuntimeError("Pool de conexões não inicializado.")

    async with pool.acquire() as conn:  # type: ignore[union-attr]
        user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        if not user:
            await conn.execute(
                "INSERT INTO users (id, email, name) VALUES ($1, $2, $3)",
                user_id,
                email,
                name,
            )
            user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return dict(user) if user else {"id": user_id, "email": email, "name": name}


async def save_analysis(
    user_id: str,
    dados_completos: Dict[str, Any],
    tempo_analise_sec: int = 0,
    data_analise_iso: Optional[str] = None,
) -> str:
    """
    Salva uma análise associada ao usuário.
    data_analise_iso é opcional; se None, usa NOW() no banco.
    """
    if pool is None:
        raise RuntimeError("Pool de conexões não inicializado.")

    analysis_id = str(uuid.uuid4())
    summary = _extract_summary(dados_completos)

    async with pool.acquire() as conn:  # type: ignore[union-attr]
        await conn.execute(
            """
            INSERT INTO analyses (
                id,
                user_id,
                nup,
                requisicao,
                om,
                om_sigla,
                instrumento_tipo,
                instrumento_numero,
                uasg_codigo,
                uasg_nome,
                fornecedor,
                cnpj,
                valor_total,
                qtd_itens,
                veredicto,
                despacho,
                tempo_analise,
                data_analise,
                dados_completos
            )
            VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, $8, $9, $10, $11, $12,
                $13, $14, $15, $16, $17,
                COALESCE($18::timestamp, NOW()),
                $19::jsonb
            )
            """,
            analysis_id,
            user_id,
            summary.get("nup"),
            summary.get("requisicao"),
            summary.get("om"),
            summary.get("om_sigla"),
            summary.get("instrumento_tipo"),
            summary.get("instrumento_numero"),
            summary.get("uasg_codigo"),
            summary.get("uasg_nome"),
            summary.get("fornecedor"),
            summary.get("cnpj"),
            summary.get("valor_total"),
            summary.get("qtd_itens") or 0,
            summary.get("veredicto"),
            summary.get("despacho"),
            tempo_analise_sec,
            data_analise_iso,
            json.dumps(dados_completos, ensure_ascii=False),
        )

    return analysis_id


async def get_user_analyses(user_id: str) -> List[Dict[str, Any]]:
    """Retorna o histórico de análises de um usuário (sem dados_completos)."""
    if pool is None:
        raise RuntimeError("Pool de conexões não inicializado.")

    async with pool.acquire() as conn:  # type: ignore[union-attr]
        rows = await conn.fetch(
            """
            SELECT
                id,
                nup,
                requisicao,
                om,
                om_sigla,
                instrumento_tipo,
                instrumento_numero,
                uasg_codigo,
                uasg_nome,
                fornecedor,
                cnpj,
                valor_total,
                qtd_itens,
                veredicto,
                despacho,
                tempo_analise,
                data_analise
            FROM analyses
            WHERE user_id = $1
            ORDER BY data_analise DESC
            """,
            user_id,
        )
        return [dict(r) for r in rows]


async def get_analysis(analysis_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Retorna uma análise completa (com dados_completos) se pertencer ao usuário."""
    if pool is None:
        raise RuntimeError("Pool de conexões não inicializado.")

    async with pool.acquire() as conn:  # type: ignore[union-attr]
        row = await conn.fetchrow(
            "SELECT * FROM analyses WHERE id = $1 AND user_id = $2",
            analysis_id,
            user_id,
        )
        if not row:
            return None
        d = dict(row)
        raw = d.get("dados_completos")
        if raw is None:
            d["dados_completos"] = {}
        return d


async def delete_analysis(analysis_id: str, user_id: str) -> bool:
    """Exclui uma análise se ela pertencer ao usuário."""
    if pool is None:
        raise RuntimeError("Pool de conexões não inicializado.")

    async with pool.acquire() as conn:  # type: ignore[union-attr]
        result = await conn.execute(
            "DELETE FROM analyses WHERE id = $1 AND user_id = $2",
            analysis_id,
            user_id,
        )
        # asyncpg retorna strings como "DELETE 1"
        return result.upper().startswith("DELETE 1")

