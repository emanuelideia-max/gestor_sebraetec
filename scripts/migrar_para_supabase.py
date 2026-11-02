"""Copia os dados do banco local (data/local.db) para o Supabase.

Uso (na pasta do projeto, depois de preencher [supabase] no .streamlit/secrets.toml
e de rodar supabase/schema.sql no projeto):

    .venv\\Scripts\\python scripts\\migrar_para_supabase.py

Pede o e-mail e a senha do usuário criado no Supabase (Authentication → Users).
Os ids mudam no Supabase; as ligações entre tabelas são remapeadas automaticamente.
Pode rodar de novo com segurança: o que já existe (mesmo nome / mesma chave) não é duplicado.
"""

from __future__ import annotations

import getpass
import json
import sqlite3
import sys
import tomllib
from pathlib import Path

from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "data" / "local.db"
SECRETS = ROOT / ".streamlit" / "secrets.toml"


def linhas(con: sqlite3.Connection, tabela: str) -> list[dict]:
    return [dict(r) for r in con.execute(f"select * from {tabela} order by id")]


def sem(d: dict, *chaves: str) -> dict:
    return {k: v for k, v in d.items() if k not in chaves}


def main() -> None:
    if not LOCAL.exists():
        sys.exit("Banco local não encontrado em data/local.db.")
    cfg = tomllib.loads(SECRETS.read_text(encoding="utf-8")).get("supabase", {}) if SECRETS.exists() else {}
    if not (cfg.get("url") and cfg.get("key")):
        sys.exit("Preencha [supabase] url e key em .streamlit/secrets.toml antes de migrar.")

    sb = create_client(cfg["url"], cfg["key"])
    for tentativa in range(1, 4):
        email = input("E-mail do usuário no Supabase: ").strip()
        senha = getpass.getpass("Senha (não aparece enquanto você digita): ")
        try:
            sb.auth.sign_in_with_password({"email": email, "password": senha})
            break
        except Exception as e:
            msg = str(e)
            if "not confirmed" in msg.lower():
                print("\nE-mail ainda não confirmado. No Supabase, em Authentication → Users, confirme o usuário.\n")
            else:
                print(f"\nNão foi possível entrar ({msg}). Confira o e-mail e a senha. Tentativa {tentativa} de 3.\n")
    else:
        sys.exit("Login não realizado. Redefina a senha do usuário no Supabase e rode o script de novo.")
    print("Login ok.\n")

    con = sqlite3.connect(LOCAL)
    con.row_factory = sqlite3.Row

    def existentes(tabela: str) -> list[dict]:
        return sb.table(tabela).select("*").execute().data

    def inserir(tabela: str, valores: dict) -> int:
        return sb.table(tabela).insert(valores).execute().data[0]["id"]

    # 1. Etapas (ids fixos 1..21)
    etapas = linhas(con, "etapas_status")
    sb.table("etapas_status").upsert(etapas).execute()
    print(f"Etapas: {len(etapas)}")

    # 2. Cidades: casadas pelo código do IBGE
    cid_sb = {c["codigo_ibge"]: c["id"] for c in existentes("cidades")}
    novas = [sem(c, "id") for c in linhas(con, "cidades") if c["codigo_ibge"] not in cid_sb]
    for i in range(0, len(novas), 200):
        sb.table("cidades").insert(novas[i:i + 200]).execute()
    cid_sb = {c["codigo_ibge"]: c["id"] for c in existentes("cidades")}
    mapa_cidade = {c["id"]: cid_sb[c["codigo_ibge"]] for c in linhas(con, "cidades")}
    print(f"Cidades: {len(cid_sb)}")

    # 3. Fornecedores: casados pelo nome
    forn_sb = {f["nome"]: f["id"] for f in existentes("fornecedores")}
    mapa_forn = {}
    for f in linhas(con, "fornecedores"):
        mapa_forn[f["id"]] = forn_sb.get(f["nome"]) or inserir("fornecedores", sem(f, "id", "created_at"))
    print(f"Fornecedores: {len(mapa_forn)}")

    # 4. Clientes: casados pelo nome
    cli_sb = {c["nome"]: c["id"] for c in existentes("clientes")}
    mapa_cli = {}
    for c in linhas(con, "clientes"):
        v = sem(c, "id", "created_at")
        v["cidade_id"] = mapa_cidade.get(v["cidade_id"])
        mapa_cli[c["id"]] = cli_sb.get(c["nome"]) or inserir("clientes", v)
    print(f"Clientes: {len(mapa_cli)}")

    # 5. Consultorias: casadas por cliente + solução + início do processamento
    chave = lambda c: (c["cliente_id"], c["ficha_tecnica"], c["inicio_processamento"])  # noqa: E731
    cons_sb = {chave(c): c["id"] for c in existentes("consultorias")}
    mapa_cons, novas_cons = {}, set()
    for c in linhas(con, "consultorias"):
        v = sem(c, "id", "created_at")
        v["cliente_id"] = mapa_cli.get(v["cliente_id"])
        v["cidade_id"] = mapa_cidade.get(v["cidade_id"])
        v["fornecedor_id"] = mapa_forn.get(v["fornecedor_id"])
        if chave(v) in cons_sb:
            mapa_cons[c["id"]] = cons_sb[chave(v)]
        else:
            mapa_cons[c["id"]] = inserir("consultorias", v)
            novas_cons.add(c["id"])
    print(f"Consultorias: {len(mapa_cons)} ({len(novas_cons)} novas)")

    # 6. Histórico: só das consultorias que acabaram de ser criadas (evita duplicar)
    hist = [dict(sem(h, "id", "created_at"), consultoria_id=mapa_cons[h["consultoria_id"]])
            for h in linhas(con, "historico_status") if h["consultoria_id"] in novas_cons]
    if hist:
        sb.table("historico_status").insert(hist).execute()
    print(f"Histórico: {len(hist)}")

    # 7. Agenda e lembretes: casados por título + data
    for tabela in ("agenda", "lembretes"):
        ja = {(r["titulo"], r["data"]) for r in existentes(tabela)}
        novos = []
        for r in linhas(con, tabela):
            if (r["titulo"], r["data"]) in ja:
                continue
            v = sem(r, "id", "created_at")
            v["consultoria_id"] = mapa_cons.get(v["consultoria_id"])
            if tabela == "lembretes":
                v["concluido"] = bool(v["concluido"])
            novos.append(v)
        if novos:
            sb.table(tabela).insert(novos).execute()
        print(f"{tabela.capitalize()}: {len(novos)} novos")

    # 8. Configurações (aparência e alertas)
    conf = linhas(con, "configuracoes")
    if conf:
        dados = conf[0]["dados"]
        sb.table("configuracoes").upsert({"id": 1, "dados": json.loads(dados) if isinstance(dados, str) else dados}).execute()
        print("Configurações: copiadas")

    print("\nMigração concluída. Abra o app e entre com o mesmo e-mail e senha.")


if __name__ == "__main__":
    main()
