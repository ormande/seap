"""
Persistência de análises em SQLite (arquivo analyses.db na pasta backend).
Cria a tabela automaticamente na inicialização se não existir.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Caminho do banco na pasta backend
DB_PATH = Path(__file__).resolve().parent / "analyses.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
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
    data_analise TEXT,
    dados_completos TEXT
);
"""


def _get_conn() -> sqlite3.Connection:
    """Abre conexão com o SQLite (autocommit off)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Cria a tabela analyses se não existir. Chamado na inicialização do FastAPI."""
    conn = _get_conn()
    try:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def _extract_summary(dados_completos: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai campos resumidos dos estágios para as colunas da tabela."""
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


def insert_analysis(
    dados_completos: Dict[str, Any],
    tempo_analise_sec: int = 0,
    data_analise_iso: Optional[str] = None,
) -> str:
    """
    Insere uma análise no banco. Retorna o id (UUID) gerado.
    data_analise_iso: se None, usa datetime atual em ISO.
    """
    import datetime
    id_ = str(uuid.uuid4())
    summary = _extract_summary(dados_completos)
    if data_analise_iso is None:
        data_analise_iso = datetime.datetime.utcnow().isoformat() + "Z"
    dados_json = json.dumps(dados_completos, ensure_ascii=False)

    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO analyses (
                id, nup, requisicao, om, om_sigla,
                instrumento_tipo, instrumento_numero, uasg_codigo, uasg_nome,
                fornecedor, cnpj, valor_total, qtd_itens,
                veredicto, despacho, tempo_analise, data_analise, dados_completos
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id_,
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
                dados_json,
            ),
        )
        conn.commit()
        return id_
    finally:
        conn.close()


def get_all_analyses() -> List[Dict[str, Any]]:
    """Lista todas as análises sem dados_completos, ordenado por data_analise desc."""
    conn = _get_conn()
    try:
        cur = conn.execute(
            """
            SELECT id, nup, requisicao, om, om_sigla,
                   instrumento_tipo, instrumento_numero, uasg_codigo, uasg_nome,
                   fornecedor, cnpj, valor_total, qtd_itens,
                   veredicto, despacho, tempo_analise, data_analise
            FROM analyses
            ORDER BY data_analise DESC
            """
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_analysis_by_id(id_: str) -> Optional[Dict[str, Any]]:
    """Retorna uma análise completa (com dados_completos) ou None."""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "SELECT * FROM analyses WHERE id = ?",
            (id_,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        d = dict(row)
        raw = d.get("dados_completos")
        if isinstance(raw, str):
            try:
                d["dados_completos"] = json.loads(raw)
            except json.JSONDecodeError:
                d["dados_completos"] = {}
        return d
    finally:
        conn.close()


def delete_analysis(id_: str) -> bool:
    """Remove a análise. Retorna True se existia e foi removida."""
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM analyses WHERE id = ?", (id_,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
