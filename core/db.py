"""Acesso ao banco.

Dois backends com a mesma interface:
- SupabaseBackend: usado quando `[supabase]` está configurado em secrets.toml (produção).
- SQLiteBackend: arquivo local `data/local.db`, para testar o sistema sem Supabase.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
SQLITE_PATH = Path(os.environ.get("GESTOR_DB", ROOT / "data" / "local.db"))

TABLES = [
    "cidades",
    "etapas_status",
    "fornecedores",
    "clientes",
    "consultorias",
    "historico_status",
    "agenda",
    "lembretes",
    "configuracoes",
]

SQLITE_SCHEMA = """
create table if not exists cidades (
    id integer primary key autoincrement, codigo_ibge integer unique not null,
    nome text not null, mesorregiao text);
create table if not exists etapas_status (
    id integer primary key, nome text not null, responsavel text);
create table if not exists fornecedores (
    id integer primary key autoincrement, nome text not null unique, cnpj text,
    contato text, email text, telefone text, created_at text default current_timestamp);
create table if not exists clientes (
    id integer primary key autoincrement, nome text not null, categoria text,
    cidade_id integer references cidades(id), documento text, contato text, email text,
    telefone text, created_at text default current_timestamp);
create table if not exists consultorias (
    id integer primary key autoincrement, acao text default 'Sebraetec',
    inicio_processamento text, area text, cliente_id integer references clientes(id),
    cidade_id integer references cidades(id), fornecedor_id integer references fornecedores(id),
    ficha_tecnica text, valor_total real default 0, valor_hora real default 0,
    carga_horaria real default 0, subsidio real default 0, contrapartida real default 0,
    status_id integer default 1, status_desde text default current_date,
    data_inicio text, data_fim text, observacoes text,
    created_at text default current_timestamp);
create table if not exists historico_status (
    id integer primary key autoincrement,
    consultoria_id integer references consultorias(id) on delete cascade,
    status_id integer, data text default current_date, usuario text, observacao text,
    created_at text default current_timestamp);
create table if not exists agenda (
    id integer primary key autoincrement, titulo text not null, data text not null, hora text,
    tipo text, local text, descricao text,
    consultoria_id integer references consultorias(id) on delete set null,
    created_at text default current_timestamp);
create table if not exists lembretes (
    id integer primary key autoincrement, titulo text not null, data text not null,
    prioridade text default 'Normal', concluido integer default 0,
    consultoria_id integer references consultorias(id) on delete set null,
    created_at text default current_timestamp);
create table if not exists configuracoes (id integer primary key, dados text);
"""


def _check_table(table: str) -> None:
    if table not in TABLES:
        raise ValueError(f"Tabela desconhecida: {table}")


class SQLiteBackend:
    name = "local"

    def __init__(self, path: Path = SQLITE_PATH):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as con:
            con.executescript(SQLITE_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("pragma foreign_keys = on")
        return con

    def select(self, table: str) -> list[dict]:
        _check_table(table)
        with self._conn() as con:
            return [dict(r) for r in con.execute(f"select * from {table} order by id")]

    def insert(self, table: str, rows: dict | list[dict]) -> list[dict]:
        _check_table(table)
        rows = [rows] if isinstance(rows, dict) else rows
        out = []
        with self._conn() as con:
            for row in rows:
                cols = list(row)
                cur = con.execute(
                    f"insert into {table} ({', '.join(cols)}) values ({', '.join('?' * len(cols))})",
                    [row[c] for c in cols],
                )
                out.append({**row, "id": cur.lastrowid})
        return out

    def update(self, table: str, row_id: int, values: dict) -> None:
        _check_table(table)
        cols = list(values)
        with self._conn() as con:
            con.execute(
                f"update {table} set {', '.join(f'{c} = ?' for c in cols)} where id = ?",
                [values[c] for c in cols] + [row_id],
            )

    def delete(self, table: str, row_id: int) -> None:
        _check_table(table)
        with self._conn() as con:
            con.execute(f"delete from {table} where id = ?", [row_id])


class SupabaseBackend:
    name = "supabase"
    PAGE = 1000

    def __init__(self, client):
        self.client = client

    def select(self, table: str) -> list[dict]:
        _check_table(table)
        rows, start = [], 0
        while True:
            batch = (
                self.client.table(table)
                .select("*")
                .order("id")
                .range(start, start + self.PAGE - 1)
                .execute()
                .data
            )
            rows.extend(batch)
            if len(batch) < self.PAGE:
                return rows
            start += self.PAGE

    def insert(self, table: str, rows: dict | list[dict]) -> list[dict]:
        _check_table(table)
        return self.client.table(table).insert(rows).execute().data

    def update(self, table: str, row_id: int, values: dict) -> None:
        _check_table(table)
        self.client.table(table).update(values).eq("id", row_id).execute()

    def delete(self, table: str, row_id: int) -> None:
        _check_table(table)
        self.client.table(table).delete().eq("id", row_id).execute()


def supabase_config() -> dict | None:
    try:
        cfg = st.secrets.get("supabase")
    except FileNotFoundError:
        return None
    if cfg and cfg.get("url") and cfg.get("key"):
        return dict(cfg)
    return None


@st.cache_resource
def _sqlite_backend() -> SQLiteBackend:
    return SQLiteBackend()


def get_backend():
    """Backend da sessão atual (o cliente Supabase guarda o login do usuário)."""
    if supabase_config():
        client = st.session_state.get("sb_client")
        if client is None:
            raise RuntimeError("Sessão sem login.")
        return SupabaseBackend(client)
    return _sqlite_backend()
