import io

import pandas as pd
import streamlit as st

from core import data, importer
from core.db import ROOT

SECOES = ["Consultorias", "Clientes", "Fornecedores", "Compromissos", "Lembretes", "Histórico de etapas",
          "Etapas do fluxo", "Importar planilha", "Exportar"]

secao = st.pills("Seção", SECOES, default="Consultorias", key="cad_secao", label_visibility="collapsed",
                 persist_state="session") or "Consultorias"

if secao not in ("Importar planilha", "Exportar"):
    st.caption(
        ":material/edit: Clique numa célula para editar · **+** no fim da tabela para acrescentar · "
        "selecione linhas e use o ícone de lixeira para excluir · depois clique em **Salvar alterações**."
    )


def _tabela(nome: str, colunas: list[str], datas: tuple[str, ...] = ()) -> pd.DataFrame:
    df = data.tables()[nome]
    df = df.reindex(columns=["id", *colunas]) if not df.empty else pd.DataFrame(columns=["id", *colunas])
    for c in datas:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    return df.reset_index(drop=True)


def _limpo(valores: dict, colunas: list[str]) -> dict:
    return {k: (None if (v is None or (isinstance(v, float) and pd.isna(v)) or v == "") else v)
            for k, v in valores.items() if k in colunas}


def salvar_edicoes(tabela: str, original: pd.DataFrame, key: str, colunas: list[str],
                   obrigatorios: tuple[str, ...] = ("nome",), ao_editar=None, ao_inserir=None) -> None:
    """Aplica no banco as linhas acrescentadas, editadas e excluídas no data_editor."""
    estado = st.session_state[key]
    erros = []
    for idx, mudancas in estado["edited_rows"].items():
        valores = _limpo(mudancas, colunas)
        if not valores:
            continue
        row_id = int(original.iloc[int(idx)]["id"])
        if ao_editar:
            ao_editar(row_id, valores, original.iloc[int(idx)])
        else:
            data.update(tabela, row_id, valores)
    for nova in estado["added_rows"]:
        valores = _limpo(nova, colunas)
        faltando = [c for c in obrigatorios if not valores.get(c)]
        if faltando:
            erros.append(f"Linha nova ignorada: preencha {', '.join(faltando)}.")
            continue
        (ao_inserir or (lambda v: data.insert(tabela, v)))(valores)
    for idx in estado["deleted_rows"]:
        linha = original.iloc[int(idx)]
        try:
            data.delete(tabela, int(linha["id"]))
        except Exception:
            erros.append(f"“{linha.get('nome', linha['id'])}” está ligado a outros registros e não pode ser excluído.")
    for e in erros:
        st.warning(e, icon=":material/warning:")
    if not erros:
        st.toast("Alterações salvas.", icon=":material/check_circle:")
        st.rerun()


def editor(tabela: str, df: pd.DataFrame, colunas: list[str], config: dict, key: str, alt: str,
           dinamico: bool = True, **kw) -> None:
    st.data_editor(df, key=key, num_rows="dynamic" if dinamico else "fixed", hide_index=True, placeholder="",
                   column_order=colunas, column_config=config, alt=alt)
    if st.button("Salvar alterações", type="primary", icon=":material/save:", key=f"salvar_{key}"):
        salvar_edicoes(tabela, df, key, colunas, **kw)


def _fmt(opcoes: dict):
    return lambda i: opcoes.get(int(i), "") if pd.notna(i) else ""


clientes, fornecedores, cidades = data.options("clientes"), data.options("fornecedores"), data.options("cidades")
etapas = {i: f"{i:02d}. {n}" for i, n in enumerate(data.nomes_etapas(), start=1)}
consultorias = {int(r["id"]): f"{r['cliente']} · {r['ficha_tecnica']}" for _, r in data.consultorias_view().iterrows()}

SEL = st.column_config.SelectboxColumn

if secao == "Consultorias":
    cols = ["cliente_id", "cidade_id", "fornecedor_id", "area", "ficha_tecnica", "valor_hora", "carga_horaria",
            "valor_total", "subsidio", "contrapartida", "status_id", "inicio_processamento", "data_inicio",
            "data_fim", "observacoes"]
    df = _tabela("consultorias", cols, ("inicio_processamento", "data_inicio", "data_fim"))

    def editar_consultoria(row_id: int, valores: dict, antes: pd.Series) -> None:
        novo_status = valores.pop("status_id", None)
        # mudou hora ou carga sem mexer no total: recalcula total, subsídio (70%) e contrapartida
        if ({"valor_hora", "carga_horaria"} & set(valores)) and "valor_total" not in valores:
            vh = float(valores.get("valor_hora", antes["valor_hora"]) or 0)
            ch = float(valores.get("carga_horaria", antes["carga_horaria"]) or 0)
            valores.update(valor_total=round(vh * ch, 2), subsidio=round(vh * ch * 0.7, 2),
                           contrapartida=round(vh * ch * 0.3, 2))
        if valores:
            data.update("consultorias", row_id, valores)
        if novo_status and int(novo_status) != int(antes["status_id"] or 0):
            data.mudar_etapa(row_id, int(novo_status), "Alterado em Dados e cadastros")

    def inserir_consultoria(valores: dict) -> None:
        if not valores.get("valor_total") and valores.get("valor_hora") and valores.get("carga_horaria"):
            total = float(valores["valor_hora"]) * float(valores["carga_horaria"])
            valores.update(valor_total=round(total, 2), subsidio=round(total * 0.7, 2),
                           contrapartida=round(total * 0.3, 2))
        valores.setdefault("status_id", 1)
        data.criar_consultoria(valores)

    editor("consultorias", df, cols, {
        "cliente_id": SEL("Cliente", options=list(clientes), format_func=_fmt(clientes), required=True),
        "cidade_id": SEL("Cidade", options=list(cidades), format_func=_fmt(cidades), required=True),
        "fornecedor_id": SEL("Fornecedor", options=list(fornecedores), format_func=_fmt(fornecedores), required=True),
        "area": "Área",
        "ficha_tecnica": st.column_config.TextColumn("Solução (ficha técnica)", width="medium"),
        "valor_hora": st.column_config.NumberColumn("R$/hora", min_value=0, format="%.2f"),
        "carga_horaria": st.column_config.NumberColumn("Horas", min_value=0, format="%.0f"),
        "valor_total": st.column_config.NumberColumn("Valor total", min_value=0, format="%.2f",
                                                     help="Recalculado se mudar R$/hora ou horas"),
        "subsidio": st.column_config.NumberColumn("Subsídio", min_value=0, format="%.2f"),
        "contrapartida": st.column_config.NumberColumn("Contrapartida", min_value=0, format="%.2f"),
        "status_id": SEL("Etapa", options=list(etapas), format_func=_fmt(etapas), width="medium"),
        "inicio_processamento": st.column_config.DateColumn("Início processamento", format="DD/MM/YYYY"),
        "data_inicio": st.column_config.DateColumn("Início", format="DD/MM/YYYY"),
        "data_fim": st.column_config.DateColumn("Fim", format="DD/MM/YYYY"),
        "observacoes": st.column_config.TextColumn("Observações", width="large"),
    }, "ed_cons", "Edição de consultorias", obrigatorios=("cliente_id", "cidade_id", "fornecedor_id"),
        ao_editar=editar_consultoria, ao_inserir=inserir_consultoria)
    st.caption("Clientes e fornecedores novos são cadastrados nas seções ao lado. "
               "Excluir uma consultoria apaga também o histórico de etapas dela.")

elif secao == "Clientes":
    cols = ["nome", "categoria", "cidade_id", "documento", "contato", "email", "telefone"]
    editor("clientes", _tabela("clientes", cols), cols, {
        "nome": st.column_config.TextColumn("Nome", required=True),
        "categoria": SEL("Categoria", options=data.CATEGORIAS_CLIENTE),
        "cidade_id": SEL("Cidade", options=list(cidades), format_func=_fmt(cidades)),
        "documento": "CPF/CNPJ", "contato": "Contato", "email": "E-mail", "telefone": "Telefone",
    }, "ed_cli", "Cadastro de clientes")

elif secao == "Fornecedores":
    cols = ["nome", "cnpj", "contato", "email", "telefone"]
    editor("fornecedores", _tabela("fornecedores", cols), cols, {
        "nome": st.column_config.TextColumn("Nome", required=True), "cnpj": "CNPJ",
        "contato": "Contato", "email": "E-mail", "telefone": "Telefone",
    }, "ed_forn", "Cadastro de fornecedores")

elif secao == "Compromissos":
    cols = ["data", "hora", "titulo", "tipo", "local", "consultoria_id", "descricao"]
    editor("agenda", _tabela("agenda", cols, ("data",)), cols, {
        "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
        "hora": st.column_config.TextColumn("Hora", help="Ex.: 14:30", max_chars=5),
        "titulo": st.column_config.TextColumn("Título", required=True, width="medium"),
        "tipo": SEL("Tipo", options=data.TIPOS_EVENTO),
        "local": "Local",
        "consultoria_id": SEL("Consultoria", options=list(consultorias), format_func=_fmt(consultorias), width="medium"),
        "descricao": st.column_config.TextColumn("Descrição", width="large"),
    }, "ed_agenda", "Compromissos da agenda", obrigatorios=("titulo", "data"))

elif secao == "Lembretes":
    cols = ["data", "titulo", "prioridade", "concluido", "consultoria_id"]
    df = _tabela("lembretes", cols, ("data",))
    df["concluido"] = df["concluido"].fillna(False).astype(bool)
    editor("lembretes", df, cols, {
        "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
        "titulo": st.column_config.TextColumn("Lembrete", required=True, width="large"),
        "prioridade": SEL("Prioridade", options=data.PRIORIDADES),
        "concluido": st.column_config.CheckboxColumn("Concluído"),
        "consultoria_id": SEL("Consultoria", options=list(consultorias), format_func=_fmt(consultorias), width="medium"),
    }, "ed_lemb", "Lembretes", obrigatorios=("titulo", "data"))

elif secao == "Histórico de etapas":
    cols = ["consultoria_id", "status_id", "data", "usuario", "observacao"]
    df = _tabela("historico_status", cols, ("data",)).sort_values(["consultoria_id", "data"]).reset_index(drop=True)
    editor("historico_status", df, cols, {
        "consultoria_id": SEL("Consultoria", options=list(consultorias), format_func=_fmt(consultorias),
                              required=True, width="medium"),
        "status_id": SEL("Etapa", options=list(etapas), format_func=_fmt(etapas), required=True, width="medium"),
        "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
        "usuario": "Usuário", "observacao": st.column_config.TextColumn("Observação", width="large"),
    }, "ed_hist", "Histórico de mudanças de etapa", obrigatorios=("consultoria_id", "status_id", "data"))
    st.caption("Corrigir datas aqui ajusta o “tempo médio por etapa” das análises. A etapa atual de cada "
               "consultoria é alterada na seção Consultorias ou na ficha.")

elif secao == "Etapas do fluxo":
    cols = ["nome", "responsavel"]
    df = _tabela("etapas_status", cols).sort_values("id").reset_index(drop=True)
    df.insert(1, "n", df["id"].astype(int))
    editor("etapas_status", df, ["n", *cols], {
        "n": st.column_config.NumberColumn("Nº", disabled=True),
        "nome": st.column_config.TextColumn("Etapa", required=True, width="large"),
        "responsavel": SEL("Responsável", options=["Gestor", "Fornecedor", "Cliente", "Gerente", "UGAL", "Geral"]),
    }, "ed_etapas", "Nomes das etapas do fluxo", dinamico=False)
    st.caption("O fluxo tem 21 etapas fixas (a ordem define fases, risco e alertas); aqui você muda nome e responsável. "
               "Etapas com responsável “Gestor” aparecem como “Sua ação” no Painel.")

elif secao == "Importar planilha":
    st.markdown(
        "Envie a planilha no mesmo formato da planilha atual (colunas *Nome do Cliente*, *Cidade*, "
        "*Fornecedor*, *Valor Total*, *Status Atual*...). Clientes e fornecedores novos são criados "
        "automaticamente, e consultorias que já existem são ignoradas."
    )
    arquivo = st.file_uploader("Planilha (.xlsx)", type=["xlsx"])
    locais = sorted(ROOT.glob("*.xlsx"))
    if arquivo is None and locais:
        arquivo = st.selectbox("Ou use uma planilha da pasta do sistema", locais, index=None,
                               format_func=lambda p: p.name, placeholder="Escolha")
    if arquivo is not None:
        linhas, avisos = importer.ler_planilha(arquivo)
        for a in avisos:
            st.warning(a, icon=":material/warning:")
        if not linhas.empty and "cliente" in linhas:
            st.dataframe(
                linhas, hide_index=True,
                column_order=["cliente", "cidade", "fornecedor", "ficha_tecnica", "valor_total",
                              "carga_horaria", "status_id", "data_inicio", "data_fim"],
                column_config={"cliente": "Cliente", "cidade": "Cidade", "fornecedor": "Fornecedor",
                               "ficha_tecnica": "Solução",
                               "valor_total": st.column_config.NumberColumn("Valor (R$)", format="localized"),
                               "carga_horaria": "Horas", "status_id": "Etapa",
                               "data_inicio": st.column_config.DateColumn("Início", format="DD/MM/YYYY"),
                               "data_fim": st.column_config.DateColumn("Fim", format="DD/MM/YYYY")},
                alt="Prévia das consultorias a importar",
            )
            if st.button(f"Importar {len(linhas)} consultoria(s)", type="primary", icon=":material/upload:"):
                with st.spinner("Importando..."):
                    novos, repetidos = importer.importar(linhas)
                st.success(f"{novos} consultoria(s) importada(s). {repetidos} já existiam e foram ignoradas.",
                           icon=":material/check_circle:")

else:  # Exportar
    df = data.consultorias_view()
    if df.empty:
        st.caption("Nada para exportar ainda.")
    else:
        saida = df[["acao", "inicio_processamento", "area", "cliente", "cidade", "valor_total", "valor_hora",
                    "carga_horaria", "subsidio", "contrapartida", "fornecedor", "ficha_tecnica", "status",
                    "data_inicio", "data_fim", "categoria", "observacoes"]].rename(columns={
            "acao": "Ação", "inicio_processamento": "Início do Processamento", "area": "Área Sebrae NACIONAL",
            "cliente": "Nome do Cliente", "cidade": "Cidade", "valor_total": "Valor Total",
            "valor_hora": "Valor por Hora", "carga_horaria": "Carga Horária Total",
            "subsidio": "Subsídio - Sebrae (70%)", "contrapartida": "Contra partida do Cliente (30%)",
            "fornecedor": "Fornecedor", "ficha_tecnica": "Ficha Técnica", "status": "Status Atual",
            "data_inicio": "Data de Início (PROPOSTA)", "data_fim": "Data Do Fim (PROPOSTA)",
            "categoria": "Categoria do Cliente", "observacoes": "Observações"})
        buf = io.BytesIO()
        saida.to_excel(buf, index=False)
        st.download_button("Baixar planilha de consultorias (.xlsx)", buf.getvalue(),
                           file_name="consultorias_sebraetec.xlsx", icon=":material/download:", type="primary",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.caption("Mesmo formato da planilha original, com o status atualizado.")
