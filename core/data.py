"""Carga, cache e gravação dos dados do sistema."""

from __future__ import annotations

import csv
import re
import unicodedata
from datetime import date

import pandas as pd
import streamlit as st

from core.db import ROOT, TABLES, get_backend

ETAPAS = [
    "Confirmação do Gestor",
    "Confirmação do Fornecedor",
    "Agendamento do Encontro",
    "Confirmar encontro (Gestor)",
    "Confirmar encontro (Fornecedor)",
    "Reunião Inicial",
    "Elaboração da proposta (Fornecedor)",
    "Confirmação da proposta (Gestor)",
    "Confirmação da proposta (Cliente)",
    "Anexo da OS (UGAL)",
    "Anexo do Contrato (Gestor)",
    "Assinatura do Contrato (Gerente)",
    "Assinatura do Contrato (Cliente)",
    "Pagamento (Cliente)",
    "Aguardando Início da Consultoria (Fornecedor)",
    "Execução do projeto",
    "Confirmação e assinatura do Relatório Final (Gestor)",
    "Reunião Final",
    "Avaliação do Serviço",
    "Liberação do Pagamento (Gestor)",
    "Consultoria Finalizada",
]
ETAPA_FINAL = len(ETAPAS)

# Agrupamento das 21 etapas em fases (usado no quadro e nas análises)
FASES = [
    ("Articulação", 1, 6),
    ("Proposta", 7, 9),
    ("Contratação", 10, 14),
    ("Execução", 15, 16),
    ("Encerramento", 17, 21),
]


def fase_da_etapa(status_id: int) -> str:
    for nome, ini, fim in FASES:
        if ini <= int(status_id) <= fim:
            return nome
    return FASES[-1][0]

CATEGORIAS_CLIENTE = [
    "Produtor Rural",
    "MEI",
    "Micro Empresa - ME",
    "Empresa de Pequeno Porte",
    "Artesão",
    "Outro",
]
TIPOS_EVENTO = ["Reunião inicial", "Reunião final", "Visita", "Prazo", "Outro"]
PRIORIDADES = ["Alta", "Normal", "Baixa"]


def norm(text) -> str:
    """Texto sem acento, minúsculo e sem espaços extras — para comparar nomes."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def responsavel_da_etapa(nome: str) -> str:
    m = re.search(r"\(([^)]+)\)", nome)
    return m.group(1) if m else "Geral"


def nome_curto_etapa(nome: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", nome).strip()


# ---------------------------------------------------------------- carga

@st.cache_data(ttl="10m", show_spinner=False)
def _load_tables(_backend_name: str) -> dict[str, pd.DataFrame]:
    backend = get_backend()
    return {t: pd.DataFrame(backend.select(t)) for t in TABLES}


def tables() -> dict[str, pd.DataFrame]:
    return _load_tables(get_backend().name)


def refresh() -> None:
    _load_tables.clear()


def bootstrap() -> None:
    """Preenche as tabelas de referência na primeira execução."""
    t = tables()
    backend = get_backend()
    changed = False
    if t["etapas_status"].empty:
        backend.insert(
            "etapas_status",
            [
                {"id": i, "nome": n, "responsavel": responsavel_da_etapa(n)}
                for i, n in enumerate(ETAPAS, start=1)
            ],
        )
        changed = True
    if t["cidades"].empty:
        with open(ROOT / "data" / "municipios_pb.csv", encoding="utf-8") as fh:
            rows = [
                {"codigo_ibge": int(r["codigo_ibge"]), "nome": r["nome"], "mesorregiao": r["mesorregiao"]}
                for r in csv.DictReader(fh)
            ]
        backend.insert("cidades", rows)
        changed = True
    if changed:
        refresh()


def _df(name: str, columns: list[str]) -> pd.DataFrame:
    df = tables()[name]
    for c in columns:
        if c not in df.columns:
            df[c] = None
    return df


def consultorias_view(today: date | None = None) -> pd.DataFrame:
    """Consultorias com nomes de cliente, cidade, fornecedor e etapa, prontas para análise."""
    today = pd.Timestamp(today or date.today())
    c = _df(
        "consultorias",
        ["id", "acao", "inicio_processamento", "area", "cliente_id", "cidade_id", "fornecedor_id",
         "ficha_tecnica", "valor_total", "valor_hora", "carga_horaria", "subsidio", "contrapartida",
         "status_id", "status_desde", "data_inicio", "data_fim", "observacoes"],
    ).copy()
    cli = _df("clientes", ["id", "nome", "categoria"])[["id", "nome", "categoria"]]
    cid = _df("cidades", ["id", "nome", "codigo_ibge", "mesorregiao"])[["id", "nome", "codigo_ibge", "mesorregiao"]]
    forn = _df("fornecedores", ["id", "nome"])[["id", "nome"]]
    eta = _df("etapas_status", ["id", "nome", "responsavel"])[["id", "nome", "responsavel"]]

    c = (
        c.merge(cli.rename(columns={"id": "cliente_id", "nome": "cliente"}), on="cliente_id", how="left")
        .merge(cid.rename(columns={"id": "cidade_id", "nome": "cidade"}), on="cidade_id", how="left")
        .merge(forn.rename(columns={"id": "fornecedor_id", "nome": "fornecedor"}), on="fornecedor_id", how="left")
        .merge(eta.rename(columns={"id": "status_id", "nome": "status"}), on="status_id", how="left")
    )
    for col in ["valor_total", "valor_hora", "carga_horaria", "subsidio", "contrapartida"]:
        c[col] = pd.to_numeric(c[col], errors="coerce").fillna(0.0)
    for col in ["inicio_processamento", "status_desde", "data_inicio", "data_fim"]:
        c[col] = pd.to_datetime(c[col], errors="coerce")
    c["status_id"] = pd.to_numeric(c["status_id"], errors="coerce").fillna(1).astype(int)
    c["etapa"] = c["status_id"].astype(str).str.zfill(2) + ". " + c["status"].fillna("")
    c["fase"] = c["status_id"].map(fase_da_etapa)
    c["finalizada"] = c["status_id"] >= ETAPA_FINAL
    c["dias_na_etapa"] = (today - c["status_desde"]).dt.days
    c["dias_para_fim"] = (c["data_fim"] - today).dt.days
    c["progresso"] = c["status_id"] / ETAPA_FINAL
    c["mes"] = c["inicio_processamento"].dt.to_period("M").dt.to_timestamp()
    for col in ["cliente", "cidade", "fornecedor", "categoria", "area", "ficha_tecnica"]:
        c[col] = c[col].fillna("—")
    return c


def historico_view() -> pd.DataFrame:
    h = _df("historico_status", ["id", "consultoria_id", "status_id", "data", "usuario", "observacao"]).copy()
    h["data"] = pd.to_datetime(h["data"], errors="coerce")
    h["status_id"] = pd.to_numeric(h["status_id"], errors="coerce")
    return h.sort_values(["consultoria_id", "data", "id"])


def tempo_por_etapa() -> pd.DataFrame:
    """Dias que cada consultoria passou em cada etapa, a partir do histórico."""
    h = historico_view().dropna(subset=["data", "status_id"])
    if h.empty:
        return pd.DataFrame(columns=["consultoria_id", "status_id", "dias"])
    h = h.copy()
    h["saida"] = h.groupby("consultoria_id")["data"].shift(-1).fillna(pd.Timestamp(date.today()))
    h["dias"] = (h["saida"] - h["data"]).dt.days
    return h[["consultoria_id", "status_id", "dias"]]


def nomes_etapas() -> list[str]:
    """Nomes das 21 etapas como estão no banco (editáveis em Dados e cadastros)."""
    df = _df("etapas_status", ["id", "nome"])
    if len(df) != ETAPA_FINAL:
        return list(ETAPAS)
    return list(df.sort_values("id")["nome"].fillna("").astype(str))


def options(name: str) -> dict[int, str]:
    """{id: nome} de uma tabela de cadastro, para selectboxes."""
    df = _df(name, ["id", "nome"])
    if df.empty:
        return {}
    return dict(zip(df["id"].astype(int), df["nome"]))


# ---------------------------------------------------------------- gravação

def _clean(values: dict) -> dict:
    out = {}
    for k, v in values.items():
        if isinstance(v, (date, pd.Timestamp)):
            v = v.strftime("%Y-%m-%d")
        elif hasattr(v, "item"):  # numpy -> python
            v = v.item()
        if isinstance(v, float) and pd.isna(v):
            v = None
        out[k] = v
    return out


def insert(table: str, values: dict | list[dict]) -> list[dict]:
    rows = [_clean(v) for v in (values if isinstance(values, list) else [values])]
    out = get_backend().insert(table, rows)
    refresh()
    return out


def update(table: str, row_id: int, values: dict) -> None:
    get_backend().update(table, int(row_id), _clean(values))
    refresh()


def delete(table: str, row_id: int) -> None:
    get_backend().delete(table, int(row_id))
    refresh()


def usuario_atual() -> str:
    return st.session_state.get("user_email", "")


def criar_consultoria(values: dict) -> int:
    values = {**values, "status_desde": values.get("status_desde") or date.today()}
    row = insert("consultorias", values)[0]
    insert(
        "historico_status",
        {"consultoria_id": row["id"], "status_id": values.get("status_id", 1),
         "data": values["status_desde"], "usuario": usuario_atual(), "observacao": "Cadastro"},
    )
    return int(row["id"])


def mudar_etapa(consultoria_id: int, novo_status: int, observacao: str = "", quando: date | None = None) -> None:
    quando = quando or date.today()
    novo_status = max(1, min(ETAPA_FINAL, int(novo_status)))
    update("consultorias", consultoria_id, {"status_id": novo_status, "status_desde": quando})
    insert(
        "historico_status",
        {"consultoria_id": int(consultoria_id), "status_id": novo_status, "data": quando,
         "usuario": usuario_atual(), "observacao": observacao or None},
    )


def get_or_create(table: str, nome: str, extra: dict | None = None) -> int:
    df = _df(table, ["id", "nome"])
    match = df[df["nome"].map(norm) == norm(nome)] if not df.empty else df
    if not match.empty:
        return int(match.iloc[0]["id"])
    return int(insert(table, {"nome": nome.strip(), **(extra or {})})[0]["id"])


def _sem_preposicoes(text: str) -> str:
    return " ".join(w for w in norm(text).split() if w not in {"de", "da", "do", "das", "dos", "d'"})


def cidade_id_por_nome(nome: str) -> int | None:
    df = _df("cidades", ["id", "nome"])
    match = df[df["nome"].map(norm) == norm(nome)]
    if match.empty:  # ex.: "Poço José de Moura" x "Poço de José de Moura" (IBGE)
        match = df[df["nome"].map(_sem_preposicoes) == _sem_preposicoes(nome)]
    return int(match.iloc[0]["id"]) if not match.empty else None
