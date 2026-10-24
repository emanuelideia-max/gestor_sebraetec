from datetime import date

import pandas as pd
import streamlit as st

from core import data, insights, pdf
from core.ui import kpi_w, brl, data_br, is_phone, num

df = data.consultorias_view()
t = data.tables()


def _valores_unicos(col: str) -> list[str]:
    return sorted(v for v in df[col].unique() if v and v != "—") if not df.empty else []


def _idx(opts: list, value) -> int | None:
    return opts.index(value) if value in opts else None


def formulario(atual: pd.Series | None = None) -> None:
    """Campos de cadastro/edição. Sem st.form para recalcular totais ao digitar."""
    clientes = data.options("clientes")
    fornecedores = data.options("fornecedores")
    cidades = data.options("cidades")

    c1, c2 = st.columns(2)
    nomes_cli = sorted(clientes.values())
    cliente = c1.selectbox(
        "Cliente", nomes_cli, index=_idx(nomes_cli, None if atual is None else atual["cliente"]),
        accept_new_options=True, placeholder="Escolha ou digite um novo",
    )
    categoria = c2.selectbox(
        "Categoria do cliente", data.CATEGORIAS_CLIENTE,
        index=_idx(data.CATEGORIAS_CLIENTE, None if atual is None else atual["categoria"]),
        accept_new_options=True, placeholder="Escolha",
    )
    nomes_cid = sorted(cidades.values())
    cidade = c1.selectbox(
        "Cidade", nomes_cid, index=_idx(nomes_cid, None if atual is None else atual["cidade"]),
        placeholder="Escolha a cidade",
    )
    nomes_forn = sorted(fornecedores.values())
    fornecedor = c2.selectbox(
        "Fornecedor", nomes_forn, index=_idx(nomes_forn, None if atual is None else atual["fornecedor"]),
        accept_new_options=True, placeholder="Escolha ou digite um novo",
    )
    areas = _valores_unicos("area")
    area = c1.selectbox("Área Sebrae Nacional", areas, index=_idx(areas, None if atual is None else atual["area"]),
                        accept_new_options=True, placeholder="Escolha ou digite")
    fichas = _valores_unicos("ficha_tecnica")
    ficha = c2.selectbox("Ficha técnica (solução)", fichas,
                         index=_idx(fichas, None if atual is None else atual["ficha_tecnica"]),
                         accept_new_options=True, placeholder="Escolha ou digite")

    c1, c2, c3 = st.columns(3)
    valor_hora = c1.number_input("Valor por hora (R$)", min_value=0.0, step=1.0,
                                 value=70.0 if atual is None else float(atual["valor_hora"]))
    carga = c2.number_input("Carga horária total (h)", min_value=0.0, step=1.0,
                            value=0.0 if atual is None else float(atual["carga_horaria"]))
    pct = c3.number_input("Subsídio Sebrae (%)", min_value=0, max_value=100, value=70, step=5)
    total = valor_hora * carga
    subsidio = round(total * pct / 100, 2)
    st.caption(
        f"Valor total **{brl(total, 2)}** · subsídio **{brl(subsidio, 2)}** · "
        f"contrapartida do cliente **{brl(total - subsidio, 2)}**"
    )

    def _d(col):
        return None if atual is None or pd.isna(atual[col]) else atual[col].date()

    c1, c2, c3 = st.columns(3)
    inicio_proc = c1.date_input("Início do processamento", value=_d("inicio_processamento") or date.today(),
                                format="DD/MM/YYYY")
    data_ini = c2.date_input("Início (proposta)", value=_d("data_inicio"), format="DD/MM/YYYY")
    data_fim = c3.date_input("Fim (proposta)", value=_d("data_fim"), format="DD/MM/YYYY")

    status = None
    if atual is None:
        status = st.selectbox("Etapa atual", range(1, data.ETAPA_FINAL + 1),
                              format_func=lambda i: f"{i:02d}. {data.nomes_etapas()[i - 1]}")
    obs = st.text_area("Observações", value="" if atual is None or pd.isna(atual["observacoes"]) else atual["observacoes"], height=80)

    if st.button("Salvar", type="primary", icon=":material/save:"):
        if not (cliente and cidade and fornecedor):
            st.error("Preencha cliente, cidade e fornecedor.")
            return
        cid_id = data.cidade_id_por_nome(cidade)
        cli_id = data.get_or_create("clientes", cliente, {"categoria": categoria, "cidade_id": cid_id})
        if atual is not None or categoria:
            data.update("clientes", cli_id, {"categoria": categoria})
        valores = {
            "inicio_processamento": inicio_proc,
            "area": area,
            "cliente_id": cli_id,
            "cidade_id": cid_id,
            "fornecedor_id": data.get_or_create("fornecedores", fornecedor),
            "ficha_tecnica": ficha,
            "valor_hora": valor_hora,
            "carga_horaria": carga,
            "valor_total": round(total, 2),
            "subsidio": subsidio,
            "contrapartida": round(total - subsidio, 2),
            "data_inicio": data_ini,
            "data_fim": data_fim,
            "observacoes": obs or None,
        }
        if atual is None:
            novo = data.criar_consultoria({**valores, "status_id": status})
            st.session_state.consultoria_sel = novo
            st.toast("Consultoria cadastrada.", icon=":material/check_circle:")
        else:
            data.update("consultorias", int(atual["id"]), valores)
            st.toast("Alterações salvas.", icon=":material/check_circle:")
        st.rerun()


@st.dialog("Nova consultoria", width="large")
def nova():
    formulario()


@st.dialog("Editar consultoria", width="large")
def editar(row: pd.Series):
    formulario(row)


@st.dialog("Excluir consultoria")
def excluir(row: pd.Series):
    st.write(f"Excluir a consultoria de **{row['cliente']}** ({row['ficha_tecnica']})? Isso não pode ser desfeito.")
    if st.button("Excluir", type="primary", icon=":material/delete:"):
        data.delete("consultorias", int(row["id"]))
        st.session_state.pop("consultoria_sel", None)
        st.rerun()


@st.dialog("Mudar etapa")
def mudar(row: pd.Series):
    nova_etapa = st.selectbox(
        "Nova etapa", range(1, data.ETAPA_FINAL + 1), index=int(row["status_id"]) - 1,
        format_func=lambda i: f"{i:02d}. {data.nomes_etapas()[i - 1]}",
    )
    quando = st.date_input("Data da mudança", value=date.today(), format="DD/MM/YYYY")
    obs = st.text_input("Observação (opcional)")
    if st.button("Confirmar", type="primary"):
        data.mudar_etapa(int(row["id"]), nova_etapa, obs, quando)
        st.rerun()


# ---------------------------------------------------------------- lista
with st.container(horizontal=True, vertical_alignment="bottom"):
    busca = st.text_input("Buscar", placeholder="Cliente, cidade, fornecedor ou solução",
                          icon=":material/search:", key="cons_busca")
    situacao = st.segmented_control("Situação", ["Ativas", "Finalizadas", "Todas"], default="Ativas",
                                    key="cons_situacao", persist_state="session")
    visao = st.segmented_control("Visão", ["Lista", "Quadro"], default="Lista", key="cons_visao",
                                 persist_state="session")
    if st.button("Nova consultoria", type="primary", icon=":material/add:"):
        nova()

with st.container(horizontal=True, vertical_alignment="bottom"):
    if "cons_cidade" in st.session_state:  # descarta cidades que sumiram dos dados
        st.session_state.cons_cidade = [c for c in st.session_state.cons_cidade if c in set(df["cidade"])]
    cidades_sel = st.multiselect("Cidade", sorted(df["cidade"].unique()) if not df.empty else [],
                                 key="cons_cidade", placeholder="Todas", persist_state="session")
    fases_sel = st.multiselect("Fase", [f[0] for f in data.FASES], key="cons_fase", placeholder="Todas",
                               persist_state="session")

if df.empty:
    st.info("Nenhuma consultoria ainda. Clique em **Nova consultoria** ou importe a planilha em "
            "**Cadastros e importação**.", icon=":material/info:")
    st.stop()

lista = df
if situacao == "Ativas":
    lista = lista[~lista["finalizada"]]
elif situacao == "Finalizadas":
    lista = lista[lista["finalizada"]]
if cidades_sel:
    lista = lista[lista["cidade"].isin(cidades_sel)]
if fases_sel:
    lista = lista[lista["fase"].isin(fases_sel)]
if busca:
    alvo = data.norm(busca)
    texto = (lista["cliente"] + " " + lista["cidade"] + " " + lista["fornecedor"] + " " + lista["ficha_tecnica"]).map(data.norm)
    lista = lista[texto.str.contains(alvo, regex=False)]
lista = insights.risco(lista.sort_values(["data_fim", "cliente"]).reset_index(drop=True))

if cidades_sel:
    st.caption(f":material/location_on: {', '.join(cidades_sel)} · {len(lista)} consultoria(s) · "
               f"{brl(lista['valor_total'].sum())} · {num(lista['carga_horaria'].sum())} h")


def abrir(cid: int) -> None:
    st.session_state.consultoria_sel = cid


if visao == "Quadro":
    # Kanban: uma coluna por fase do fluxo
    colunas = st.columns(len(data.FASES), gap="small")
    for col, (fase, ini, fim) in zip(colunas, data.FASES):
        grupo = lista[lista["fase"] == fase].sort_values("risco", ascending=False)
        with col:
            st.markdown(f"**{fase}**")
            st.caption(f"Etapas {ini}–{fim} · {len(grupo)} · {brl(grupo['valor_total'].sum())}")
            for _, r in grupo.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{r['cliente']}**")
                    st.caption(f"{r['cidade']} · {r['fornecedor']}")
                    st.caption(f"{int(r['status_id']):02d}. {data.nome_curto_etapa(r['status'])}")
                    with st.container(horizontal=True, vertical_alignment="center"):
                        st.badge(f"Risco {r['nivel'].lower()}", color=insights.COR_NIVEL.get(r["nivel"], "gray"))
                        st.button("Abrir", key=f"kb_{r['id']}", type="tertiary", icon=":material/open_in_new:",
                                  on_click=abrir, args=(int(r["id"]),))
    linhas = []
else:
    sel = st.dataframe(
        lista,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="cons_tabela",
        column_order=(["cliente", "status", "data_fim"] if is_phone() else
                      ["cliente", "cidade", "fornecedor", "ficha_tecnica", "valor_total", "carga_horaria",
                       "progresso", "status", "data_fim", "dias_para_fim", "risco"]),
        column_config={
            "cliente": "Cliente",
            "cidade": "Cidade",
            "fornecedor": "Fornecedor",
            "ficha_tecnica": st.column_config.TextColumn("Solução", width="medium"),
            "valor_total": st.column_config.NumberColumn("Valor (R$)", format="localized"),
            "carga_horaria": st.column_config.NumberColumn("Horas", format="%.0f"),
            "progresso": st.column_config.ProgressColumn("Avanço", min_value=0, max_value=1, format="percent"),
            "status": "Etapa atual",
            "data_fim": st.column_config.DateColumn("Fim", format="DD/MM/YYYY"),
            "dias_para_fim": st.column_config.NumberColumn("Dias p/ fim"),
            "risco": st.column_config.ProgressColumn("Risco", min_value=0, max_value=100, format="%d",
                                                     help="0–100: prazo, tempo parado e atraso para iniciar"),
        },
        alt="Lista de consultorias",
    )
    st.caption(f"{len(lista)} consultoria(s). Clique numa linha para abrir a ficha.")
    linhas = sel.selection.rows
if linhas:
    st.session_state.consultoria_sel = int(lista.iloc[linhas[0]]["id"])
sel_id = st.session_state.get("consultoria_sel")
if sel_id is None or sel_id not in set(df["id"].astype(int)):
    st.stop()

# ---------------------------------------------------------------- ficha
row = df[df["id"].astype(int) == sel_id].iloc[0]
st.divider()
with st.container(horizontal=True, vertical_alignment="center"):
    st.subheader(row["cliente"], anchor=False)
    st.badge(row["categoria"], color="gray")
    st.badge(row["cidade"], icon=":material/location_on:", color="blue")
    if row["finalizada"]:
        st.badge("Finalizada", icon=":material/check:", color="green")
    else:
        rr = insights.risco(df[df["id"].astype(int) == sel_id]).iloc[0]
        st.badge(f"Risco {rr['nivel'].lower()} · {int(rr['risco'])}", icon=":material/speed:",
                 color=insights.COR_NIVEL.get(rr["nivel"], "gray"), help=rr["motivos"] or "Sem pontos de atenção")

with st.container(horizontal=True):
    st.metric("Valor total", brl(row["valor_total"], 2), border=True, width=kpi_w())
    st.metric("Subsídio / contrapartida", f"{brl(row['subsidio'])} / {brl(row['contrapartida'])}", border=True, width=kpi_w())
    st.metric("Carga horária", f"{num(row['carga_horaria'])} h · {brl(row['valor_hora'], 2)}/h", border=True, width=kpi_w())
    st.metric("Período (proposta)", f"{data_br(row['data_inicio'])} a {data_br(row['data_fim'])}", border=True, width=kpi_w())

col_info, col_linha = st.columns([2, 3])
with col_info:
    with st.container(border=True, height="stretch"):
        st.markdown(f"**Fornecedor:** {row['fornecedor']}")
        st.markdown(f"**Solução:** {row['ficha_tecnica']}")
        st.markdown(f"**Área:** {row['area']}")
        st.markdown(f"**Início do processamento:** {data_br(row['inicio_processamento'])}")
        st.markdown(f"**Na etapa atual desde:** {data_br(row['status_desde'])}"
                    + (f" ({int(row['dias_na_etapa'])} dias)" if pd.notna(row['dias_na_etapa']) else ""))
        if pd.notna(row["observacoes"]) and row["observacoes"]:
            st.markdown(f"**Observações:** {row['observacoes']}")
        with st.container(horizontal=True):
            if st.button("Editar", icon=":material/edit:"):
                editar(row)
            hist_pdf = data.historico_view()
            st.download_button(
                "Ficha em PDF",
                pdf.ficha_consultoria(row, hist_pdf[hist_pdf["consultoria_id"] == sel_id]),
                file_name=f"ficha_{data.norm(row['cliente']).replace(' ', '_')}.pdf",
                mime="application/pdf",
                icon=":material/print:",
                on_click="ignore",
            )
            if st.button("Excluir", icon=":material/delete:", type="tertiary"):
                excluir(row)

with col_linha:
    with st.container(border=True, height="stretch"):
        atual = int(row["status_id"])
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"**Etapa {atual} de {data.ETAPA_FINAL}**")
            if st.button("Voltar", icon=":material/undo:", disabled=atual <= 1, type="tertiary"):
                data.mudar_etapa(sel_id, atual - 1, "Etapa revertida")
                st.rerun()
            if st.button("Outra etapa", icon=":material/swap_vert:", type="tertiary"):
                mudar(row)
            if st.button("Avançar etapa", icon=":material/arrow_forward:", type="primary",
                         disabled=atual >= data.ETAPA_FINAL):
                data.mudar_etapa(sel_id, atual + 1)
                st.rerun()
        st.progress(atual / data.ETAPA_FINAL)

        hist = data.historico_view()
        hist = hist[hist["consultoria_id"] == sel_id]
        datas = hist.groupby("status_id")["data"].max().to_dict()
        linhas_tl = []
        for i, nome in enumerate(data.nomes_etapas(), start=1):
            quando = f" · {data_br(datas[i])}" if i in datas and pd.notna(datas[i]) else ""
            if i < atual:
                linhas_tl.append(f":green[:material/check_circle:] :gray[{i:02d}. {nome}{quando}]")
            elif i == atual:
                linhas_tl.append(f":blue[:material/radio_button_checked:] **{i:02d}. {nome}**{quando}")
            else:
                linhas_tl.append(f":gray[:material/radio_button_unchecked: {i:02d}. {nome}]")
        a, b = st.columns(2)
        a.markdown("  \n".join(linhas_tl[:11]))
        b.markdown("  \n".join(linhas_tl[11:]))

if not hist.empty:
    with st.expander("Histórico de mudanças", icon=":material/history:"):
        h = hist.copy()
        h["etapa"] = h["status_id"].map(lambda i: f"{int(i):02d}. {data.nomes_etapas()[int(i) - 1]}" if pd.notna(i) else "")
        st.dataframe(
            h.sort_values(["data", "id"], ascending=False),
            hide_index=True,
            column_order=["data", "etapa", "usuario", "observacao"],
            column_config={"data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                           "etapa": "Etapa", "usuario": "Usuário", "observacao": "Observação"},
            alt="Histórico de mudanças de etapa",
        )
