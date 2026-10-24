"""Importação da planilha de consultorias (formato usado pelo gestor)."""

from __future__ import annotations

import re

import pandas as pd

from core import data

# prefixo do cabeçalho normalizado -> campo
COLUNAS = [
    ("acao", "acao"),
    ("inicio do processamento", "inicio_processamento"),
    ("area", "area"),
    ("nome do cliente", "cliente"),
    ("cliente", "cliente"),
    ("cidade", "cidade"),
    ("valor total", "valor_total"),
    ("valor por hora", "valor_hora"),
    ("carga horaria", "carga_horaria"),
    ("subsidio", "subsidio"),
    ("contra", "contrapartida"),
    ("fornecedor", "fornecedor"),
    ("ficha tecnica", "ficha_tecnica"),
    ("status", "status"),
    ("data de inicio", "data_inicio"),
    ("data do fim", "data_fim"),
    ("data de fim", "data_fim"),
    ("categoria", "categoria"),
]


def _campo(header: str) -> str | None:
    h = data.norm(header)
    for prefixo, campo in COLUNAS:
        if h.startswith(prefixo):
            return campo
    return None


def status_id(nome: str) -> int | None:
    alvo = data.norm(nome)
    if not alvo:
        return None
    if alvo.isdigit():
        return int(alvo) if 1 <= int(alvo) <= data.ETAPA_FINAL else None
    alvo = re.sub(r"^\d+\.\s*", "", alvo)
    for i, etapa in enumerate(data.ETAPAS, start=1):
        if alvo in (data.norm(etapa), data.norm(data.nome_curto_etapa(etapa))):
            return i
    for i, etapa in enumerate(data.ETAPAS, start=1):
        if alvo in data.norm(etapa):
            return i
    return None


def ler_planilha(arquivo) -> tuple[pd.DataFrame, list[str]]:
    """Lê o Excel e devolve as linhas no formato do sistema, mais avisos para o usuário."""
    bruto = pd.read_excel(arquivo)
    renomear = {}
    for col in bruto.columns:
        campo = _campo(col)
        if campo and campo not in renomear.values():
            renomear[col] = campo
    df = bruto.rename(columns=renomear)[list(renomear.values())]
    df = df.dropna(how="all")
    df = df[df.get("cliente").notna()] if "cliente" in df else df.iloc[0:0]

    avisos = []
    faltando = {"cliente", "cidade", "fornecedor"} - set(df.columns)
    if faltando:
        avisos.append(f"Colunas não encontradas: {', '.join(sorted(faltando))}.")
        return df, avisos

    df["cidade_id"] = df["cidade"].map(lambda c: data.cidade_id_por_nome(c))
    for c in df.loc[df["cidade_id"].isna(), "cidade"].unique():
        avisos.append(f"Cidade não encontrada na Paraíba: “{c}” (ficará sem cidade).")
    if "status" in df:
        df["status_id"] = df["status"].map(status_id)
        for s in df.loc[df["status_id"].isna(), "status"].dropna().unique():
            avisos.append(f"Status não reconhecido: “{s}” (entrará na etapa 1).")
        df["status_id"] = df["status_id"].fillna(1).astype(int)
    else:
        df["status_id"] = 1
    for col in ["inicio_processamento", "data_inicio", "data_fim"]:
        if col in df:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    for col in ["valor_total", "valor_hora", "carga_horaria", "subsidio", "contrapartida"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0) if col in df else 0.0
    sem_total = df["valor_total"] == 0
    df.loc[sem_total, "valor_total"] = df["valor_hora"] * df["carga_horaria"]
    df.loc[df["subsidio"] == 0, "subsidio"] = df["valor_total"] * 0.7
    df.loc[df["contrapartida"] == 0, "contrapartida"] = df["valor_total"] - df["subsidio"]
    return df.reset_index(drop=True), avisos


def _chave(cliente_id, ficha, inicio) -> tuple:
    ini = pd.to_datetime(inicio, errors="coerce")
    return (int(cliente_id), data.norm(ficha), None if pd.isna(ini) else ini.date())


def importar(df: pd.DataFrame) -> tuple[int, int]:
    """Grava as linhas, criando clientes e fornecedores. Ignora consultorias já existentes."""
    existentes = data.tables()["consultorias"]
    chaves = set()
    if not existentes.empty:
        chaves = {_chave(r["cliente_id"], r["ficha_tecnica"], r["inicio_processamento"])
                  for _, r in existentes.iterrows() if pd.notna(r["cliente_id"])}

    novos, repetidos = 0, 0
    for _, r in df.iterrows():
        cidade_id = None if pd.isna(r["cidade_id"]) else int(r["cidade_id"])
        categoria = r.get("categoria") if pd.notna(r.get("categoria")) else None
        cli_id = data.get_or_create("clientes", str(r["cliente"]), {"categoria": categoria, "cidade_id": cidade_id})
        chave = _chave(cli_id, r.get("ficha_tecnica"), r.get("inicio_processamento"))
        if chave in chaves:
            repetidos += 1
            continue
        chaves.add(chave)

        def val(col):
            v = r.get(col)
            return None if v is None or (not isinstance(v, str) and pd.isna(v)) else v

        hoje = pd.Timestamp.today().normalize()
        data.criar_consultoria({
            "acao": val("acao") or "Sebraetec",
            "inicio_processamento": val("inicio_processamento"),
            "area": val("area"),
            "cliente_id": cli_id,
            "cidade_id": cidade_id,
            "fornecedor_id": data.get_or_create("fornecedores", str(r["fornecedor"])),
            "ficha_tecnica": val("ficha_tecnica"),
            "valor_total": round(float(r["valor_total"]), 2),
            "valor_hora": float(r["valor_hora"]),
            "carga_horaria": float(r["carga_horaria"]),
            "subsidio": round(float(r["subsidio"]), 2),
            "contrapartida": round(float(r["contrapartida"]), 2),
            "status_id": int(r["status_id"]),
            # em execução: a etapa começou na data de início da proposta
            "status_desde": val("data_inicio") if int(r["status_id"]) == 16 and val("data_inicio") else hoje,
            "data_inicio": val("data_inicio"),
            "data_fim": val("data_fim"),
        })
        novos += 1
    return novos, repetidos
